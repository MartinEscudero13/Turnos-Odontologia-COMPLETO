"""Repositorios SQLAlchemy de caja — C-10 §5 (wiring real, D14/M4).

Adaptadores de persistencia de los puertos de `puertos.py` sobre una `Session`
compartida. La unidad de trabajo (`UnidadDeTrabajoCajaSQL`) toma el advisory lock
por `(tenant, fecha)` **antes** de cualquier lectura de estado o escritura (D14)
y fija `app.tenant_id` para que la RLS de la 008 aplique con el rol de la app.

Estos repositorios no reimplementan el dominio: traducen entre las entidades de
`puertos.py` y los modelos de `models/caja.py`, y convierten las violaciones de
los UNIQUE de la 008 en los errores de repositorio que el servicio ya conoce
(`ImputacionDuplicada`, `CuentaPorCobrarDuplicada`, `CierreDuplicado`,
`CobroYaResuelto`, `AjusteDuplicado`).
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import cast

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.caja.puertos import (
    MEDIOS,
    Ajuste,
    AjusteDuplicado,
    Cierre,
    CierreDuplicado,
    CobroPendiente,
    CobroYaResuelto,
    CuentaPorCobrarDuplicada,
    CuentaPorCobrarOS,
    ImputacionDuplicada,
    MedioPago,
    Movimiento,
    OrigenMovimiento,
    TipoAjuste,
    TipoMovimiento,
    TramoCaja,
    YaAnulado,
)
from app.core.transaccion import TransaccionSQL
from app.models.auditoria import Auditoria
from app.models.caja import (
    AjustePostCierre,
    CierreDiario,
    MovimientoCaja,
)
from app.models.caja import (
    CobroPendiente as CobroPendienteModel,
)
from app.models.caja import (
    CuentaPorCobrarOS as CuentaPorCobrarOSModel,
)
from app.models.presupuesto import PresupuestoLinea
from app.models.turno import Turno
from app.turnos.servicio import NoEncontrado

__all__ = [
    "AjustesSQL",
    "AuditoriaSQL",
    "CierresSQL",
    "CobrosSQL",
    "CuentasOSSQL",
    "LineasPresupuestoSQL",
    "MovimientosSQL",
    "TurnosSQL",
    "UnidadDeTrabajoCajaSQL",
]

_UNIQUE_LINEA_TRAMO = "movimientos_caja_tenant_linea_tramo_unique"
_UNIQUE_CUENTA_LINEA = "cuentas_por_cobrar_os_tenant_linea_unique"
_UNIQUE_PENDIENTE_LINEA = "cobros_pendientes_tenant_linea_unique"
_UNIQUE_CIERRE_FECHA = "cierres_diarios_tenant_fecha_unique"
_UNIQUE_AJUSTE_MOVIMIENTO = "ajustes_post_cierre_tenant_movimiento_unique"
_UNIQUE_AJUSTE_PENDIENTE = "ajustes_post_cierre_tenant_pendiente_unique"


def _ahora(ahora: datetime | None) -> datetime:
    return ahora if ahora is not None else datetime.now(UTC)


def _uuid(valor: str) -> uuid.UUID:
    """Los ids del dominio viajan como `str`; en DB son `UUID`."""
    return uuid.UUID(valor)


def _es_unico(exc: IntegrityError, indice: str) -> bool:
    return indice in str(getattr(exc, "orig", exc))


# ---------------------------------------------------------------------------
# Movimientos
# ---------------------------------------------------------------------------


def _movimiento(fila: MovimientoCaja) -> Movimiento:
    return Movimiento(
        id=str(fila.id),
        tenant_id=str(fila.tenant_id),
        fecha=fila.fecha,
        medio=cast(MedioPago, fila.medio),
        monto=fila.monto,
        tipo=cast(TipoMovimiento, fila.tipo),
        usuario_id=str(fila.usuario_id),
        tramo=cast(TramoCaja | None, fila.tramo),
        turno_id=str(fila.turno_id) if fila.turno_id is not None else None,
        presupuesto_id=str(fila.presupuesto_id) if fila.presupuesto_id is not None else None,
        linea_id=str(fila.linea_id) if fila.linea_id is not None else None,
        paciente_id=str(fila.paciente_id) if fila.paciente_id is not None else None,
        origen=cast(OrigenMovimiento, fila.origen),
        compensa_a_id=str(fila.compensa_a_id) if fila.compensa_a_id is not None else None,
        anulado=fila.anulado,
        motivo_anulacion=fila.motivo_anulacion,
        anulado_por=str(fila.anulado_por) if fila.anulado_por is not None else None,
        anulado_en=fila.anulado_en,
        creado_en=fila.creado_en,
    )


class MovimientosSQL:
    """`MovimientoRepositorio` sobre `movimientos_caja` (append-only salvo anulación)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def registrar(
        self,
        *,
        tenant_id: str,
        fecha: date,
        medio: MedioPago,
        monto: int,
        tipo: TipoMovimiento,
        usuario_id: str,
        tramo: TramoCaja | None = None,
        turno_id: str | None = None,
        presupuesto_id: str | None = None,
        linea_id: str | None = None,
        paciente_id: str | None = None,
        origen: OrigenMovimiento = "MANUAL",
        compensa_a_id: str | None = None,
        motivo_anulacion: str | None = None,
        ahora: datetime | None = None,
    ) -> Movimiento:
        fila = MovimientoCaja(
            tenant_id=_uuid(tenant_id),
            fecha=fecha,
            medio=medio,
            monto=monto,
            tipo=tipo,
            usuario_id=_uuid(usuario_id),
            tramo=tramo,
            turno_id=_uuid(turno_id) if turno_id is not None else None,
            presupuesto_id=_uuid(presupuesto_id) if presupuesto_id is not None else None,
            linea_id=_uuid(linea_id) if linea_id is not None else None,
            paciente_id=_uuid(paciente_id) if paciente_id is not None else None,
            origen=origen,
            compensa_a_id=_uuid(compensa_a_id) if compensa_a_id is not None else None,
            anulado=False,
            motivo_anulacion=motivo_anulacion,
            creado_en=_ahora(ahora),
        )
        self._session.add(fila)
        try:
            self._session.flush()
        except IntegrityError as exc:
            # H1: el UNIQUE parcial por `(tenant, línea, tramo)` no incluye el medio.
            if _es_unico(exc, _UNIQUE_LINEA_TRAMO):
                raise ImputacionDuplicada(
                    f"línea {linea_id} ya imputada en el tramo {tramo}"
                ) from exc
            raise
        return _movimiento(fila)

    def obtener(self, *, tenant_id: str, movimiento_id: str) -> Movimiento | None:
        fila = self._session.get(MovimientoCaja, _uuid(movimiento_id))
        if fila is None or str(fila.tenant_id) != tenant_id:
            return None
        return _movimiento(fila)

    def listar_por_fecha(self, *, tenant_id: str, fecha: date) -> list[Movimiento]:
        filas = self._session.scalars(
            select(MovimientoCaja)
            .where(MovimientoCaja.tenant_id == _uuid(tenant_id), MovimientoCaja.fecha == fecha)
            .order_by(MovimientoCaja.creado_en, MovimientoCaja.id)
        ).all()
        return [_movimiento(fila) for fila in filas]

    def buscar_imputacion(
        self, *, tenant_id: str, linea_id: str, tramo: TramoCaja
    ) -> Movimiento | None:
        fila = self._session.scalars(
            select(MovimientoCaja).where(
                MovimientoCaja.tenant_id == _uuid(tenant_id),
                MovimientoCaja.linea_id == _uuid(linea_id),
                MovimientoCaja.tramo == tramo,
                MovimientoCaja.origen == "IMPUTACION",
            )
        ).first()
        return None if fila is None else _movimiento(fila)

    def anular(
        self,
        *,
        tenant_id: str,
        movimiento_id: str,
        motivo: str,
        actor_id: str,
        ahora: datetime | None = None,
    ) -> Movimiento:
        fila = self._session.get(MovimientoCaja, _uuid(movimiento_id), with_for_update=True)
        if fila is None or str(fila.tenant_id) != tenant_id:
            raise NoEncontrado("movimiento de caja no encontrado")
        if fila.anulado:
            raise YaAnulado("el movimiento ya está anulado")
        fila.anulado = True
        fila.motivo_anulacion = motivo
        fila.anulado_por = _uuid(actor_id)
        fila.anulado_en = _ahora(ahora)
        self._session.flush()
        return _movimiento(fila)

    def totales_por_medio(self, *, tenant_id: str, fecha: date) -> dict[MedioPago, int]:
        totales: dict[MedioPago, int] = {medio: 0 for medio in MEDIOS}
        filas = self._session.execute(
            select(MovimientoCaja.medio, MovimientoCaja.tipo, func.sum(MovimientoCaja.monto))
            .where(
                MovimientoCaja.tenant_id == _uuid(tenant_id),
                MovimientoCaja.fecha == fecha,
                MovimientoCaja.anulado.is_(False),
            )
            .group_by(MovimientoCaja.medio, MovimientoCaja.tipo)
        ).all()
        for medio, tipo, suma in filas:
            signo = 1 if tipo == "INGRESO" else -1
            totales[cast(MedioPago, medio)] += signo * int(suma)
        return totales


# ---------------------------------------------------------------------------
# Cierres
# ---------------------------------------------------------------------------


def _cierre(fila: CierreDiario) -> Cierre:
    return Cierre(
        id=str(fila.id),
        tenant_id=str(fila.tenant_id),
        fecha=fila.fecha,
        total_efectivo=fila.total_efectivo,
        total_transferencia=fila.total_transferencia,
        total_mp=fila.total_mp,
        total_os_cobrado=fila.total_os_cobrado,
        total_os=fila.total_os,
        efectivo_contado=fila.efectivo_contado,
        diferencia=fila.diferencia,
        responsable_id=str(fila.responsable_id),
        motivo_diferencia=fila.motivo_diferencia,
        observacion=fila.observacion,
        cerrado_at=fila.cerrado_at,
        creado_en=fila.creado_en,
    )


class CierresSQL:
    """`CierreRepositorio` sobre `cierres_diarios` (snapshot inmutable, D4).

    `cerrar` es la contraparte transaccional de `CierreMemoria`: calcula los
    totales del día dentro de la misma unidad de trabajo que ya tomó el lock
    (D14) y persiste el snapshot. Los casos de uso del cierre son §6.
    """

    def __init__(self, session: Session, movimientos: MovimientosSQL, cuentas: CuentasOSSQL) -> None:
        self._session = session
        self._movimientos = movimientos
        self._cuentas = cuentas

    def cerrar(
        self,
        *,
        tenant_id: str,
        fecha: date,
        efectivo_contado: int,
        responsable_id: str,
        motivo_diferencia: str | None = None,
        observacion: str | None = None,
        ahora: datetime | None = None,
    ) -> Cierre:
        totales = self._movimientos.totales_por_medio(tenant_id=tenant_id, fecha=fecha)
        momento = _ahora(ahora)
        fila = CierreDiario(
            tenant_id=_uuid(tenant_id),
            fecha=fecha,
            total_efectivo=totales["EFECTIVO"],
            total_transferencia=totales["TRANSFERENCIA"],
            total_mp=totales["MP"],
            total_os_cobrado=totales["OS"],
            total_os=self._cuentas.total_devengado(tenant_id=tenant_id, fecha=fecha),
            efectivo_contado=efectivo_contado,
            diferencia=efectivo_contado - totales["EFECTIVO"],
            responsable_id=_uuid(responsable_id),
            motivo_diferencia=motivo_diferencia,
            observacion=observacion,
            cerrado_at=momento,
            creado_en=momento,
        )
        self._session.add(fila)
        try:
            self._session.flush()
        except IntegrityError as exc:
            if _es_unico(exc, _UNIQUE_CIERRE_FECHA):
                raise CierreDuplicado(f"el día {fecha} ya tiene cierre") from exc
            raise
        return _cierre(fila)

    def obtener(self, *, tenant_id: str, fecha: date) -> Cierre | None:
        fila = self._session.scalars(
            select(CierreDiario).where(
                CierreDiario.tenant_id == _uuid(tenant_id), CierreDiario.fecha == fecha
            )
        ).first()
        return None if fila is None else _cierre(fila)

    def listar(self, *, tenant_id: str, desde: date, hasta: date) -> list[Cierre]:
        filas = self._session.scalars(
            select(CierreDiario)
            .where(
                CierreDiario.tenant_id == _uuid(tenant_id),
                CierreDiario.fecha >= desde,
                CierreDiario.fecha <= hasta,
            )
            .order_by(CierreDiario.fecha, CierreDiario.id)
        ).all()
        return [_cierre(fila) for fila in filas]


# ---------------------------------------------------------------------------
# Cobros pendientes
# ---------------------------------------------------------------------------


def _pendiente(fila: CobroPendienteModel) -> CobroPendiente:
    return CobroPendiente(
        id=str(fila.id),
        tenant_id=str(fila.tenant_id),
        fecha=fila.fecha,
        presupuesto_id=str(fila.presupuesto_id),
        linea_id=str(fila.linea_id),
        paciente_id=str(fila.paciente_id),
        monto_centavos=fila.monto_centavos,
        actor_id=str(fila.actor_id),
        turno_id=str(fila.turno_id) if fila.turno_id is not None else None,
        creado_en=fila.creado_en,
        resuelto_en=fila.resuelto_en,
        movimiento_id=str(fila.movimiento_id) if fila.movimiento_id is not None else None,
    )


class CobrosSQL:
    """`CobroPendienteRepositorio` sobre `cobros_pendientes` (uno por línea, H1)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def registrar(
        self,
        *,
        tenant_id: str,
        fecha: date,
        presupuesto_id: str,
        linea_id: str,
        paciente_id: str,
        monto_centavos: int,
        actor_id: str,
        turno_id: str | None = None,
        ahora: datetime | None = None,
    ) -> CobroPendiente:
        fila = CobroPendienteModel(
            tenant_id=_uuid(tenant_id),
            fecha=fecha,
            presupuesto_id=_uuid(presupuesto_id),
            linea_id=_uuid(linea_id),
            paciente_id=_uuid(paciente_id),
            monto_centavos=monto_centavos,
            actor_id=_uuid(actor_id),
            turno_id=_uuid(turno_id) if turno_id is not None else None,
            creado_en=_ahora(ahora),
        )
        self._session.add(fila)
        try:
            self._session.flush()
        except IntegrityError as exc:
            if _es_unico(exc, _UNIQUE_PENDIENTE_LINEA):
                raise ImputacionDuplicada(
                    f"la línea {linea_id} ya tiene un cobro pendiente"
                ) from exc
            raise
        return _pendiente(fila)

    def obtener(self, *, tenant_id: str, pendiente_id: str) -> CobroPendiente | None:
        fila = self._session.get(CobroPendienteModel, _uuid(pendiente_id))
        if fila is None or str(fila.tenant_id) != tenant_id:
            return None
        return _pendiente(fila)

    def buscar_por_linea(self, *, tenant_id: str, linea_id: str) -> CobroPendiente | None:
        fila = self._session.scalars(
            select(CobroPendienteModel).where(
                CobroPendienteModel.tenant_id == _uuid(tenant_id),
                CobroPendienteModel.linea_id == _uuid(linea_id),
            )
        ).first()
        return None if fila is None else _pendiente(fila)

    def listar(self, *, tenant_id: str, fecha: date | None = None) -> list[CobroPendiente]:
        consulta = select(CobroPendienteModel).where(
            CobroPendienteModel.tenant_id == _uuid(tenant_id)
        )
        if fecha is not None:
            consulta = consulta.where(CobroPendienteModel.fecha == fecha)
        filas = self._session.scalars(
            consulta.order_by(CobroPendienteModel.creado_en, CobroPendienteModel.id)
        ).all()
        return [_pendiente(fila) for fila in filas]

    def resolver(
        self,
        *,
        tenant_id: str,
        pendiente_id: str,
        movimiento_id: str,
        ahora: datetime | None = None,
    ) -> CobroPendiente:
        fila = self._session.get(
            CobroPendienteModel, _uuid(pendiente_id), with_for_update=True
        )
        if fila is None or str(fila.tenant_id) != tenant_id:
            raise NoEncontrado("cobro pendiente no encontrado")
        if fila.resuelto_en is not None:
            raise CobroYaResuelto("el cobro pendiente ya fue resuelto")
        fila.resuelto_en = _ahora(ahora)
        fila.movimiento_id = _uuid(movimiento_id)
        self._session.flush()
        return _pendiente(fila)


# ---------------------------------------------------------------------------
# Ajustes post-cierre
# ---------------------------------------------------------------------------


def _ajuste(fila: AjustePostCierre) -> Ajuste:
    return Ajuste(
        id=str(fila.id),
        tenant_id=str(fila.tenant_id),
        cierre_id=str(fila.cierre_id),
        tipo=cast(TipoAjuste, fila.tipo),
        movimiento_original_id=(
            str(fila.movimiento_original_id) if fila.movimiento_original_id is not None else None
        ),
        cobro_pendiente_id=(
            str(fila.cobro_pendiente_id) if fila.cobro_pendiente_id is not None else None
        ),
        monto=fila.monto,
        medio=cast(MedioPago, fila.medio),
        motivo=fila.motivo,
        actor_id=str(fila.actor_id),
        compensatorio_id=str(fila.compensatorio_id),
        creado_en=fila.creado_en,
    )


class AjustesSQL:
    """`AjustePostCierreRepositorio`: ledger append-only, único por hecho (D1)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def registrar(
        self,
        *,
        tenant_id: str,
        cierre_id: str,
        tipo: TipoAjuste,
        monto: int,
        medio: MedioPago,
        actor_id: str,
        compensatorio_id: str,
        movimiento_original_id: str | None = None,
        cobro_pendiente_id: str | None = None,
        motivo: str | None = None,
        ahora: datetime | None = None,
    ) -> Ajuste:
        fila = AjustePostCierre(
            tenant_id=_uuid(tenant_id),
            cierre_id=_uuid(cierre_id),
            tipo=tipo,
            movimiento_original_id=(
                _uuid(movimiento_original_id) if movimiento_original_id is not None else None
            ),
            cobro_pendiente_id=(
                _uuid(cobro_pendiente_id) if cobro_pendiente_id is not None else None
            ),
            monto=monto,
            medio=medio,
            motivo=motivo,
            actor_id=_uuid(actor_id),
            compensatorio_id=_uuid(compensatorio_id),
            creado_en=_ahora(ahora),
        )
        self._session.add(fila)
        try:
            self._session.flush()
        except IntegrityError as exc:
            # D1: un ajuste por hecho corregido (dos UNIQUE parciales).
            mensaje = str(getattr(exc, "orig", exc))
            if _UNIQUE_AJUSTE_MOVIMIENTO in mensaje or _UNIQUE_AJUSTE_PENDIENTE in mensaje:
                raise AjusteDuplicado("ya existe un ajuste para ese hecho") from exc
            raise
        return _ajuste(fila)

    def listar_por_cierre(self, *, tenant_id: str, cierre_id: str) -> list[Ajuste]:
        filas = self._session.scalars(
            select(AjustePostCierre)
            .where(
                AjustePostCierre.tenant_id == _uuid(tenant_id),
                AjustePostCierre.cierre_id == _uuid(cierre_id),
            )
            .order_by(AjustePostCierre.creado_en, AjustePostCierre.id)
        ).all()
        return [_ajuste(fila) for fila in filas]


# ---------------------------------------------------------------------------
# Cuentas por cobrar OS
# ---------------------------------------------------------------------------


def _cuenta(fila: CuentaPorCobrarOSModel) -> CuentaPorCobrarOS:
    return CuentaPorCobrarOS(
        id=str(fila.id),
        tenant_id=str(fila.tenant_id),
        fecha=fila.fecha,
        presupuesto_id=str(fila.presupuesto_id),
        linea_id=str(fila.linea_id),
        paciente_id=str(fila.paciente_id),
        monto_centavos=fila.monto_centavos,
        creado_en=fila.creado_en,
    )


class CuentasOSSQL:
    """`CuentaPorCobrarOSRepositorio`: devengado informativo, nunca caja (D4)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def registrar(
        self,
        *,
        tenant_id: str,
        fecha: date,
        presupuesto_id: str,
        linea_id: str,
        paciente_id: str,
        monto_centavos: int,
        ahora: datetime | None = None,
    ) -> CuentaPorCobrarOS:
        fila = CuentaPorCobrarOSModel(
            tenant_id=_uuid(tenant_id),
            fecha=fecha,
            presupuesto_id=_uuid(presupuesto_id),
            linea_id=_uuid(linea_id),
            paciente_id=_uuid(paciente_id),
            monto_centavos=monto_centavos,
            creado_en=_ahora(ahora),
        )
        self._session.add(fila)
        try:
            self._session.flush()
        except IntegrityError as exc:
            if _es_unico(exc, _UNIQUE_CUENTA_LINEA):
                raise CuentaPorCobrarDuplicada(
                    f"la línea {linea_id} ya tiene devengado OS"
                ) from exc
            raise
        return _cuenta(fila)

    def buscar_por_linea(
        self, *, tenant_id: str, linea_id: str
    ) -> CuentaPorCobrarOS | None:
        fila = self._session.scalars(
            select(CuentaPorCobrarOSModel).where(
                CuentaPorCobrarOSModel.tenant_id == _uuid(tenant_id),
                CuentaPorCobrarOSModel.linea_id == _uuid(linea_id),
            )
        ).first()
        return None if fila is None else _cuenta(fila)

    def total_devengado(self, *, tenant_id: str, fecha: date) -> int:
        total = self._session.scalar(
            select(func.sum(CuentaPorCobrarOSModel.monto_centavos)).where(
                CuentaPorCobrarOSModel.tenant_id == _uuid(tenant_id),
                CuentaPorCobrarOSModel.fecha == fecha,
            )
        )
        return int(total or 0)


# ---------------------------------------------------------------------------
# Puertos de apoyo
# ---------------------------------------------------------------------------


class TurnosSQL:
    """`TurnoPort`: existencia del turno dentro del tenant."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def existe(self, *, tenant_id: str, turno_id: str) -> bool:
        turno = self._session.get(Turno, _uuid(turno_id))
        return turno is not None and str(turno.tenant_id) == tenant_id


class LineasPresupuestoSQL:
    """`LineaPresupuestoPort`: la línea pertenece al tenant y al presupuesto."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def pertenece(self, *, tenant_id: str, presupuesto_id: str, linea_id: str) -> bool:
        encontrada = self._session.scalar(
            select(PresupuestoLinea.id).where(
                PresupuestoLinea.tenant_id == _uuid(tenant_id),
                PresupuestoLinea.presupuesto_id == _uuid(presupuesto_id),
                PresupuestoLinea.id == _uuid(linea_id),
            )
        )
        return encontrada is not None


class AuditoriaSQL:
    """Auditoría append-only compartida por caja y presupuesto (RN-AU-02).

    `accion` se declara `str` para aceptar los códigos de ambos contextos: es
    supertipo de `AccionCaja` y de `AccionPresupuesto`.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def registrar(
        self,
        *,
        tenant_id: str,
        accion: str,
        actor: str,
        entidad: str,
        entidad_id: str,
        antes: dict[str, object] | None = None,
        despues: dict[str, object] | None = None,
    ) -> None:
        self._session.add(
            Auditoria(
                tenant_id=_uuid(tenant_id),
                actor_id=actor,
                accion=accion,
                entidad=entidad,
                entidad_id=entidad_id,
                antes=antes,
                despues=despues,
            )
        )
        self._session.flush()


# ---------------------------------------------------------------------------
# Unidad de trabajo
# ---------------------------------------------------------------------------


class UnidadDeTrabajoCajaSQL(TransaccionSQL):
    """UoW de caja: advisory lock por `(tenant, fecha)` y lock de movimiento (D14)."""

    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self._movimientos = MovimientosSQL(session)

    def _fijar_tenant(self, tenant_id: str) -> None:
        # RLS fail-closed de la 008: sin `app.tenant_id` no hay filas visibles.
        self.session.execute(
            text("SELECT set_config('app.tenant_id', :tenant, true)"),
            {"tenant": tenant_id},
        )

    def bloquear_dia(self, *, tenant_id: str, fecha: date) -> None:
        self._fijar_tenant(tenant_id)
        # Mismo predicado que el resto del proyecto: hashtext(tenant || ':' || fecha).
        self.session.execute(
            text(
                "SELECT pg_advisory_xact_lock("
                "hashtext(CAST(:tenant AS text) || ':' || CAST(:fecha AS text)))"
            ),
            {"tenant": tenant_id, "fecha": fecha.isoformat()},
        )

    def bloquear_movimiento(self, *, tenant_id: str, movimiento_id: str) -> Movimiento:
        self._fijar_tenant(tenant_id)
        fila = self.session.get(
            MovimientoCaja, _uuid(movimiento_id), with_for_update=True
        )
        if fila is None or str(fila.tenant_id) != tenant_id:
            raise NoEncontrado("movimiento de caja no encontrado")
        return _movimiento(fila)
