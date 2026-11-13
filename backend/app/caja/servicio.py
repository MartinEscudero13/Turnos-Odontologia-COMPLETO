"""Servicio de caja — C-10 §2–§4 (movimientos, anulación, compensación y pendientes).

Dominio puro: programa contra los puertos de `puertos.py` y no toca DB ni red.
Reglas duras aplicadas:

- RN-CJ-01: `medio` ∈ {EFECTIVO, TRANSFERENCIA, MP, OS} y `tipo` ∈
  {INGRESO, EGRESO}; todo movimiento lleva usuario y fecha operativa.
- Montos enteros positivos en centavos; un `float`, un `string`, 0 o negativo
  son `422` (`Invalido`).
- La fecha es un día operativo (`YYYY-MM-DD`); sin fecha se usa el día del
  reloj en el offset fijo `-03:00` (C10-OQ-8, D1).
- D14: toda escritura de caja toma el advisory lock del día **antes** de
  validar el estado del día y de insertar.
- RN-CJ-03/D2: nunca hay borrado físico; la anulación exige motivo, actor e
  instante y ocurre una sola vez (`409 ANULADO`).
- D3: si la fecha del original tiene cierre, además de anular se crea un
  compensatorio inverso fechado el día del registro y una fila en
  `ajustes_post_cierre`; el cierre **nunca** se edita ni se recalcula. Si el
  día del registro también está cerrado ⇒ `409 CIERRE_CERRADO`.
- D5/H1: `medio=NULL` de C-09 crea un cobro pendiente (uno por línea, sin
  condición de resolución); cobrarlo crea el `INGRESO` y, si la fecha del
  pendiente está cerrada, asienta un ajuste `COBRO_PENDIENTE`.
- RN-AU-02: toda mutación deja auditoría append-only con ids y montos, sin PHI.

Fuera de esta tanda (capas siguientes): adaptador de imputación (§5), cierre
(§6), consultas y reportes (§7), RBAC de borde (§8), auditoría HTTP (§10).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from app.caja.puertos import (
    AccionCaja,
    Ajuste,
    AjustePostCierreRepositorio,
    AuditoriaPort,
    CierreRepositorio,
    CobroPendiente,
    CobroPendienteRepositorio,
    CuentaPorCobrarOSRepositorio,
    MedioPago,
    Movimiento,
    MovimientoRepositorio,
    Reloj,
    TipoMovimiento,
    TurnoPort,
    UnidadDeTrabajo,
)
from app.core.logging import get_logger
from app.presupuesto.servicio import Conflicto
from app.turnos.servicio import Actor, Invalido, NoAutenticado, NoEncontrado, Prohibido

logger = get_logger("app.caja")

__all__ = [
    "TZ_OPERATIVA",
    "ConflictoCaja",
    "InvalidoCaja",
    "ResultadoCobro",
    "ServicioCaja",
    "dia_operativo",
]

# C10-OQ-8 (fijada): el día operativo del consultorio se calcula en -03:00.
TZ_OPERATIVA = timezone(timedelta(hours=-3))

_REGISTRA_MOVIMIENTO: frozenset[str] = frozenset({"ADMIN", "RECEPCION"})
_ANULA: frozenset[str] = frozenset({"ADMIN"})
_COBRA: frozenset[str] = frozenset({"ADMIN", "RECEPCION"})
_LEE_CAJA: frozenset[str] = frozenset({"ADMIN", "ODONTOLOGO", "RECEPCION"})
_MEDIOS: frozenset[str] = frozenset({"EFECTIVO", "TRANSFERENCIA", "MP", "OS"})
_TIPOS: frozenset[str] = frozenset({"INGRESO", "EGRESO"})


class ConflictoCaja(Conflicto):
    """`409` de caja con el código de dominio observable por el borde API.

    Los códigos son los del design (D9): `CIERRE_CERRADO`, `ANULADO`,
    `IMPUTACION_DUPLICADA` y `COBRO_YA_RESUELTO`. El borde de §9 los expone;
    el dominio los hace verificables sin acoplarse al transporte.
    """

    def __init__(self, codigo_dominio: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.codigo_dominio: str = codigo_dominio


class InvalidoCaja(Invalido):
    """`422` de caja con el código de dominio (`MEDIO_OS_RESERVADO`, …).

    C10-OQ-5: el copago del paciente con medio `OS` no existe en v1 y se
    observa como `422 MEDIO_OS_RESERVADO` al invocar el adaptador directo.
    """

    def __init__(self, codigo_dominio: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.codigo_dominio: str = codigo_dominio


@dataclass(frozen=True)
class ResultadoCobro:
    """Cobro de un pendiente: el movimiento creado, el pendiente resuelto y el ajuste."""

    pendiente: CobroPendiente
    movimiento: Movimiento
    ajuste: Ajuste | None



def dia_operativo(ahora: datetime) -> date:
    """Día calendario del consultorio en `-03:00` (C10-OQ-8).

    El reloj inyectado debe ser aware: una fecha operativa derivada de un
    instante sin zona no tiene un día único.
    """
    if ahora.tzinfo is None:
        raise Invalido("el reloj debe ser aware para calcular el día operativo")
    return ahora.astimezone(TZ_OPERATIVA).date()


def _validar_monto(monto: object) -> int:
    # `bool` es subclase de `int`: `True` no es un monto.
    if isinstance(monto, bool) or not isinstance(monto, int) or monto <= 0:
        raise Invalido("monto inválido: debe ser un entero positivo en centavos")
    return monto


def _validar_medio(medio: object) -> MedioPago:
    if not isinstance(medio, str) or medio not in _MEDIOS:
        raise Invalido("medio inválido")
    return medio  # type: ignore[return-value]  # acotado por el frozenset


def _validar_tipo(tipo: object) -> TipoMovimiento:
    if not isinstance(tipo, str) or tipo not in _TIPOS:
        raise Invalido("tipo inválido")
    return tipo  # type: ignore[return-value]  # acotado por el frozenset


def _validar_fecha(fecha: object, ahora: datetime) -> date:
    if fecha is None:
        return dia_operativo(ahora)
    if isinstance(fecha, datetime):
        raise Invalido("fecha inválida: la fecha operativa es YYYY-MM-DD")
    if isinstance(fecha, date):
        return fecha
    if isinstance(fecha, str):
        try:
            return date.fromisoformat(fecha)
        except ValueError:
            raise Invalido("fecha inválida: la fecha operativa es YYYY-MM-DD") from None
    raise Invalido("fecha inválida: la fecha operativa es YYYY-MM-DD")


def _validar_motivo(motivo: object) -> str:
    """RN-CJ-03: la anulación exige un motivo no vacío."""
    if not isinstance(motivo, str) or not motivo.strip():
        raise Invalido("motivo de anulación inválido: no puede estar vacío")
    return motivo.strip()


def _validar_monto_tramo(monto: object) -> int | None:
    """Tramo del paciente: `<= 0` no genera hecho de caja (ni pendiente)."""
    if isinstance(monto, bool) or not isinstance(monto, int):
        raise Invalido("monto inválido: debe ser un entero en centavos")
    return monto if monto > 0 else None


def _tipo_inverso(tipo: TipoMovimiento) -> TipoMovimiento:
    """El compensatorio invierte el tipo: INGRESO↔EGRESO (D3)."""
    return "EGRESO" if tipo == "INGRESO" else "INGRESO"


class ServicioCaja:
    """Casos de uso de caja implementados en esta capa: alta y lectura."""

    def __init__(
        self,
        movimientos: MovimientoRepositorio,
        cierres: CierreRepositorio,
        cobros: CobroPendienteRepositorio,
        ajustes: AjustePostCierreRepositorio,
        cuentas: CuentaPorCobrarOSRepositorio,
        turnos: TurnoPort,
        auditoria: AuditoriaPort,
        *,
        uow_factory: Callable[[], UnidadDeTrabajo],
        reloj: Reloj | None = None,
    ) -> None:
        self._movimientos = movimientos
        self._cierres = cierres
        self._cobros = cobros
        self._ajustes = ajustes
        self._cuentas = cuentas
        self._turnos = turnos
        self._auditoria = auditoria
        self._uow_factory = uow_factory
        self._reloj: Reloj = reloj if reloj is not None else lambda: datetime.now(TZ_OPERATIVA)

    # ------------------------------------------------------------------
    # Movimientos (§2)
    # ------------------------------------------------------------------

    def registrar_movimiento(
        self,
        actor: Actor,
        *,
        monto: int,
        medio: MedioPago,
        tipo: TipoMovimiento = "INGRESO",
        fecha: str | date | None = None,
        turno_id: str | None = None,
    ) -> Movimiento:
        """Registra un hecho de caja del día operativo (RN-CJ-01)."""
        self._exigir_escritura(actor)
        monto_validado = _validar_monto(monto)
        medio_validado = _validar_medio(medio)
        tipo_validado = _validar_tipo(tipo)
        momento = self._reloj()
        fecha_validada = _validar_fecha(fecha, momento)

        with self._uow_factory() as uow:
            # D14: el lock por (tenant, día) se toma antes de escribir.
            uow.bloquear_dia(tenant_id=actor.tenant_id, fecha=fecha_validada)
            if self._cierres.obtener(tenant_id=actor.tenant_id, fecha=fecha_validada) is not None:
                # RN-CJ-02/D3: un día cerrado no admite altas; la corrección va
                # por anulación o cobro de pendiente, nunca por un alta nueva.
                raise ConflictoCaja(
                    "CIERRE_CERRADO",
                    f"el día {fecha_validada.isoformat()} está cerrado",
                )
            if turno_id is not None and not self._turnos.existe(
                tenant_id=actor.tenant_id, turno_id=turno_id
            ):
                raise NoEncontrado("turno no encontrado")
            movimiento = self._movimientos.registrar(
                tenant_id=actor.tenant_id,
                fecha=fecha_validada,
                medio=medio_validado,
                monto=monto_validado,
                tipo=tipo_validado,
                usuario_id=actor.user_id,
                turno_id=turno_id,
                origen="MANUAL",
                ahora=momento,
            )
            self._auditar(
                tenant_id=actor.tenant_id,
                accion="MOVIMIENTO_CAJA_REGISTRADO",
                actor_id=actor.user_id,
                movimiento=movimiento,
            )

        # Sin PHI: sólo ids, fecha, medio y monto.
        logger.info(
            "movimiento_caja_registrado tenant_id=%s movimiento_id=%s fecha=%s"
            " medio=%s tipo=%s monto=%s",
            movimiento.tenant_id,
            movimiento.id,
            movimiento.fecha.isoformat(),
            movimiento.medio,
            movimiento.tipo,
            movimiento.monto,
        )
        return movimiento

    def obtener_movimiento(self, actor: Actor, *, movimiento_id: str) -> Movimiento:
        self._exigir_lectura(actor)
        movimiento = self._movimientos.obtener(
            tenant_id=actor.tenant_id, movimiento_id=movimiento_id
        )
        if movimiento is None:
            raise NoEncontrado("movimiento de caja no encontrado")
        return movimiento

    def totales_del_dia(self, actor: Actor, *, fecha: date) -> dict[MedioPago, int]:
        self._exigir_lectura(actor)
        totales: dict[MedioPago, int] = {
            "EFECTIVO": 0,
            "TRANSFERENCIA": 0,
            "MP": 0,
            "OS": 0,
        }
        for movimiento in self._movimientos.listar_por_fecha(
            tenant_id=actor.tenant_id, fecha=fecha
        ):
            if movimiento.anulado:
                continue
            signo = 1 if movimiento.tipo == "INGRESO" else -1
            totales[movimiento.medio] += signo * movimiento.monto
        return totales

    # ------------------------------------------------------------------
    # Anulación y compensación (§3)
    # ------------------------------------------------------------------

    def anular_movimiento(
        self, actor: Actor, *, movimiento_id: str, motivo: str
    ) -> Movimiento:
        """Anula sin borrar (RN-CJ-03) y compensa si el día ya tiene cierre (D3).

        Única transición `vigente → anulado` (D2). Si la fecha del original
        tiene cierre: además del compensatorio inverso fechado hoy, se asienta
        el ajuste `AJUSTE_ANULACION` contra ese cierre, que no se toca. Si el
        día del registro también está cerrado no hay dónde materializar la
        corrección ⇒ `409 CIERRE_CERRADO` sin marcar la anulación.
        """
        self._exigir_anulacion(actor)
        motivo_validado = _validar_motivo(motivo)
        momento = self._reloj()
        hoy = dia_operativo(momento)

        with self._uow_factory() as uow:
            # D14: el lock de la fila y del día se toman antes de validar el estado.
            original = uow.bloquear_movimiento(
                tenant_id=actor.tenant_id, movimiento_id=movimiento_id
            )
            if original.anulado:
                raise ConflictoCaja("ANULADO", "el movimiento ya está anulado")
            uow.bloquear_dia(tenant_id=actor.tenant_id, fecha=original.fecha)
            cierre_origen = self._cierres.obtener(
                tenant_id=actor.tenant_id, fecha=original.fecha
            )
            if cierre_origen is not None:
                if hoy != original.fecha:
                    uow.bloquear_dia(tenant_id=actor.tenant_id, fecha=hoy)
                if self._cierres.obtener(tenant_id=actor.tenant_id, fecha=hoy) is not None:
                    # No hay día abierto donde materializar el compensatorio.
                    raise ConflictoCaja(
                        "CIERRE_CERRADO",
                        "no hay un día abierto para asentar la corrección",
                    )

            anulado = self._movimientos.anular(
                tenant_id=actor.tenant_id,
                movimiento_id=original.id,
                motivo=motivo_validado,
                actor_id=actor.user_id,
                ahora=momento,
            )

            compensatorio: Movimiento | None = None
            ajuste: Ajuste | None = None
            if cierre_origen is not None:
                # D3: tipo inverso, mismo medio y monto, fechado el día del
                # registro (nunca en la fecha cerrada) y trazable al original.
                compensatorio = self._movimientos.registrar(
                    tenant_id=actor.tenant_id,
                    fecha=hoy,
                    medio=anulado.medio,
                    monto=anulado.monto,
                    tipo=_tipo_inverso(anulado.tipo),
                    usuario_id=actor.user_id,
                    origen="COMPENSACION",
                    compensa_a_id=anulado.id,
                    motivo_anulacion=motivo_validado,
                    ahora=momento,
                )
                ajuste = self._ajustes.registrar(
                    tenant_id=actor.tenant_id,
                    cierre_id=cierre_origen.id,
                    tipo="AJUSTE_ANULACION",
                    monto=anulado.monto,
                    medio=anulado.medio,
                    actor_id=actor.user_id,
                    compensatorio_id=compensatorio.id,
                    movimiento_original_id=anulado.id,
                    motivo=motivo_validado,
                    ahora=momento,
                )

            self._auditoria.registrar(
                tenant_id=actor.tenant_id,
                accion="MOVIMIENTO_CAJA_ANULADO",
                actor=actor.user_id,
                entidad="movimiento_caja",
                entidad_id=anulado.id,
                antes={"anulado": False},
                despues={
                    "anulado": True,
                    "motivo_anulacion": motivo_validado,
                    "compensatorio_id": (
                        compensatorio.id if compensatorio is not None else None
                    ),
                },
            )
            if compensatorio is not None:
                self._auditar_compensatorio(
                    tenant_id=actor.tenant_id,
                    actor_id=actor.user_id,
                    movimiento=compensatorio,
                )
            if ajuste is not None:
                self._auditar_ajuste(
                    tenant_id=actor.tenant_id,
                    actor_id=actor.user_id,
                    ajuste=ajuste,
                )

        logger.info(
            "movimiento_caja_anulado tenant_id=%s movimiento_id=%s fecha=%s"
            " compensatorio_id=%s",
            anulado.tenant_id,
            anulado.id,
            anulado.fecha.isoformat(),
            compensatorio.id if compensatorio is not None else "-",
        )
        return anulado

    # ------------------------------------------------------------------
    # Cobros pendientes e imputación del tramo del paciente (§4)
    # ------------------------------------------------------------------

    def imputar_tramo_paciente(
        self,
        *,
        tenant_id: str,
        presupuesto_id: str,
        linea_id: str,
        paciente_id: str,
        monto_paciente_centavos: int,
        actor_id: str,
        medio: MedioPago | None,
        turno_id: str | None = None,
        fecha: date | None = None,
    ) -> Movimiento | CobroPendiente | None:
        """Tramo del paciente de la imputación de C-09 (D5/D6, §4).

        `medio=None` crea un cobro pendiente y ningún movimiento; con medio se
        crea el `INGRESO` idempotente por `(línea, tramo PACIENTE)`. Un replay
        es no-op (mismo medio y monto) o `409 IMPUTACION_DUPLICADA` (otro medio
        o monto): el medio no integra la clave (H1). Un tramo en 0 no genera
        nada. El adaptador real del puerto llega en §5 y delega acá.
        """
        monto = _validar_monto_tramo(monto_paciente_centavos)
        if monto is None:
            return None
        medio_validado: MedioPago | None = (
            None if medio is None else _validar_medio(medio)
        )
        momento = self._reloj()
        fecha_operativa = dia_operativo(momento) if fecha is None else fecha
        if turno_id is not None and not self._turnos.existe(
            tenant_id=tenant_id, turno_id=turno_id
        ):
            raise NoEncontrado("turno no encontrado")

        with self._uow_factory() as uow:
            # D14: el lock del día se toma antes de validar el estado y escribir.
            uow.bloquear_dia(tenant_id=tenant_id, fecha=fecha_operativa)
            movimiento_existente = self._movimientos.buscar_imputacion(
                tenant_id=tenant_id, linea_id=linea_id, tramo="PACIENTE"
            )
            pendiente_existente = self._cobros.buscar_por_linea(
                tenant_id=tenant_id, linea_id=linea_id
            )
            # H1: el replay nunca falla por un cierre posterior al hecho.
            if medio_validado is None:
                if movimiento_existente is not None:
                    return movimiento_existente
                if pendiente_existente is not None:
                    return pendiente_existente
            else:
                if movimiento_existente is not None:
                    if (
                        movimiento_existente.medio == medio_validado
                        and movimiento_existente.monto == monto
                    ):
                        return movimiento_existente
                    raise ConflictoCaja(
                        "IMPUTACION_DUPLICADA",
                        f"la línea {linea_id} ya está imputada con otro medio o monto",
                    )
                if pendiente_existente is not None:
                    raise ConflictoCaja(
                        "IMPUTACION_DUPLICADA",
                        f"la línea {linea_id} ya tiene un cobro pendiente",
                    )

            if self._cierres.obtener(tenant_id=tenant_id, fecha=fecha_operativa) is not None:
                raise ConflictoCaja(
                    "CIERRE_CERRADO",
                    f"el día {fecha_operativa.isoformat()} está cerrado",
                )

            if medio_validado is None:
                pendiente = self._cobros.registrar(
                    tenant_id=tenant_id,
                    fecha=fecha_operativa,
                    presupuesto_id=presupuesto_id,
                    linea_id=linea_id,
                    paciente_id=paciente_id,
                    monto_centavos=monto,
                    actor_id=actor_id,
                    turno_id=turno_id,
                    ahora=momento,
                )
                self._auditoria.registrar(
                    tenant_id=tenant_id,
                    accion="COBRO_PENDIENTE_REGISTRADO",
                    actor=actor_id,
                    entidad="cobro_pendiente",
                    entidad_id=pendiente.id,
                    antes=None,
                    despues={
                        "linea_id": pendiente.linea_id,
                        "fecha": pendiente.fecha.isoformat(),
                        "monto": pendiente.monto_centavos,
                    },
                )
                return pendiente

            movimiento = self._movimientos.registrar(
                tenant_id=tenant_id,
                fecha=fecha_operativa,
                medio=medio_validado,
                monto=monto,
                tipo="INGRESO",
                usuario_id=actor_id,
                tramo="PACIENTE",
                turno_id=turno_id,
                presupuesto_id=presupuesto_id,
                linea_id=linea_id,
                paciente_id=paciente_id,
                origen="IMPUTACION",
                ahora=momento,
            )
            self._auditar(
                tenant_id=tenant_id,
                accion="MOVIMIENTO_CAJA_REGISTRADO",
                actor_id=actor_id,
                movimiento=movimiento,
            )

        return movimiento

    def cobrar_pendiente(
        self, actor: Actor, *, pendiente_id: str, medio: MedioPago
    ) -> ResultadoCobro:
        """Cobra un pendiente con un medio válido (D5/H4, §4).

        Si la fecha del pendiente está abierta, el `INGRESO` se fecha ahí. Si
        está cerrada, se fecha el día del registro y se asienta el ajuste
        `COBRO_PENDIENTE` contra el cierre de la fecha del pendiente. Si el día
        del registro también está cerrado ⇒ `409 CIERRE_CERRADO` y el pendiente
        queda sin resolver. Un pendiente resuelto ⇒ `409 COBRO_YA_RESUELTO`.
        """
        self._exigir_cobro(actor)
        medio_validado = _validar_medio(medio)
        momento = self._reloj()
        hoy = dia_operativo(momento)

        with self._uow_factory() as uow:
            pendiente = self._cobros.obtener(
                tenant_id=actor.tenant_id, pendiente_id=pendiente_id
            )
            if pendiente is None:
                raise NoEncontrado("cobro pendiente no encontrado")
            # D14: lock de la fecha objetivo antes de validar el estado del día.
            uow.bloquear_dia(tenant_id=actor.tenant_id, fecha=pendiente.fecha)
            actual = self._cobros.obtener(
                tenant_id=actor.tenant_id, pendiente_id=pendiente_id
            )
            if actual is None:
                raise NoEncontrado("cobro pendiente no encontrado")
            if actual.resuelto_en is not None:
                raise ConflictoCaja(
                    "COBRO_YA_RESUELTO", "el cobro pendiente ya fue resuelto"
                )

            cierre_origen = self._cierres.obtener(
                tenant_id=actor.tenant_id, fecha=actual.fecha
            )
            fecha_movimiento = actual.fecha
            if cierre_origen is not None:
                if hoy != actual.fecha:
                    uow.bloquear_dia(tenant_id=actor.tenant_id, fecha=hoy)
                if self._cierres.obtener(tenant_id=actor.tenant_id, fecha=hoy) is not None:
                    raise ConflictoCaja(
                        "CIERRE_CERRADO",
                        "no hay un día abierto para asentar el cobro",
                    )
                fecha_movimiento = hoy

            if (
                self._movimientos.buscar_imputacion(
                    tenant_id=actor.tenant_id,
                    linea_id=actual.linea_id,
                    tramo="PACIENTE",
                )
                is not None
            ):
                raise ConflictoCaja(
                    "IMPUTACION_DUPLICADA",
                    f"la línea {actual.linea_id} ya tiene un movimiento imputado",
                )

            movimiento = self._movimientos.registrar(
                tenant_id=actor.tenant_id,
                fecha=fecha_movimiento,
                medio=medio_validado,
                monto=actual.monto_centavos,
                tipo="INGRESO",
                usuario_id=actor.user_id,
                tramo="PACIENTE",
                turno_id=actual.turno_id,
                presupuesto_id=actual.presupuesto_id,
                linea_id=actual.linea_id,
                paciente_id=actual.paciente_id,
                origen="IMPUTACION",
                ahora=momento,
            )
            self._auditar(
                tenant_id=actor.tenant_id,
                accion="MOVIMIENTO_CAJA_REGISTRADO",
                actor_id=actor.user_id,
                movimiento=movimiento,
            )
            resuelto = self._cobros.resolver(
                tenant_id=actor.tenant_id,
                pendiente_id=actual.id,
                movimiento_id=movimiento.id,
                ahora=momento,
            )

            ajuste: Ajuste | None = None
            if cierre_origen is not None:
                ajuste = self._ajustes.registrar(
                    tenant_id=actor.tenant_id,
                    cierre_id=cierre_origen.id,
                    tipo="COBRO_PENDIENTE",
                    monto=actual.monto_centavos,
                    medio=medio_validado,
                    actor_id=actor.user_id,
                    compensatorio_id=movimiento.id,
                    cobro_pendiente_id=actual.id,
                    ahora=momento,
                )
                self._auditar_ajuste(
                    tenant_id=actor.tenant_id,
                    actor_id=actor.user_id,
                    ajuste=ajuste,
                )

            self._auditoria.registrar(
                tenant_id=actor.tenant_id,
                accion="COBRO_PENDIENTE_RESUELTO",
                actor=actor.user_id,
                entidad="cobro_pendiente",
                entidad_id=resuelto.id,
                antes={"resuelto": False},
                despues={
                    "resuelto": True,
                    "movimiento_id": movimiento.id,
                    "medio": medio_validado,
                    "ajuste_id": ajuste.id if ajuste is not None else None,
                },
            )

        logger.info(
            "cobro_pendiente_resuelto tenant_id=%s pendiente_id=%s movimiento_id=%s"
            " fecha=%s medio=%s monto=%s",
            resuelto.tenant_id,
            resuelto.id,
            movimiento.id,
            movimiento.fecha.isoformat(),
            movimiento.medio,
            movimiento.monto,
        )
        return ResultadoCobro(pendiente=resuelto, movimiento=movimiento, ajuste=ajuste)

    # ------------------------------------------------------------------
    # RBAC mínimo (§2–§4; el RBAC de borde es §8)
    # ------------------------------------------------------------------

    def _exigir_interno(self, actor: Actor) -> None:
        if actor.rol == "PACIENTE":
            # v1 no tiene sesión de paciente (DD-06/DD-07): 401, nunca 403.
            raise NoAutenticado("la caja requiere una sesión interna")

    def _exigir_escritura(self, actor: Actor) -> None:
        self._exigir_interno(actor)
        if actor.rol not in _REGISTRA_MOVIMIENTO:
            raise Prohibido("el rol no puede registrar movimientos de caja")

    def _exigir_lectura(self, actor: Actor) -> None:
        self._exigir_interno(actor)
        if actor.rol not in _LEE_CAJA:
            raise Prohibido("el rol no puede leer la caja")

    def _exigir_anulacion(self, actor: Actor) -> None:
        # D10/C10-OQ-9: anular es exclusivo de ADMIN, nunca de recepcion.
        self._exigir_interno(actor)
        if actor.rol not in _ANULA:
            raise Prohibido("el rol no puede anular movimientos de caja")

    def _exigir_cobro(self, actor: Actor) -> None:
        self._exigir_interno(actor)
        if actor.rol not in _COBRA:
            raise Prohibido("el rol no puede cobrar pendientes de caja")

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _auditar(
        self,
        *,
        tenant_id: str,
        accion: AccionCaja,
        actor_id: str,
        movimiento: Movimiento,
    ) -> None:
        self._auditoria.registrar(
            tenant_id=tenant_id,
            accion=accion,
            actor=actor_id,
            entidad="movimiento_caja",
            entidad_id=movimiento.id,
            antes=None,
            despues={
                "fecha": movimiento.fecha.isoformat(),
                "medio": movimiento.medio,
                "tipo": movimiento.tipo,
                "monto": movimiento.monto,
                "usuario_id": movimiento.usuario_id,
                "turno_id": movimiento.turno_id,
                "origen": movimiento.origen,
            },
        )

    def _auditar_compensatorio(
        self,
        *,
        tenant_id: str,
        actor_id: str,
        movimiento: Movimiento,
    ) -> None:
        """D11: el compensatorio deja auditoría con referencia al original."""
        self._auditoria.registrar(
            tenant_id=tenant_id,
            accion="MOVIMIENTO_COMPENSATORIO_REGISTRADO",
            actor=actor_id,
            entidad="movimiento_caja",
            entidad_id=movimiento.id,
            antes=None,
            despues={
                "compensa_a_id": movimiento.compensa_a_id,
                "fecha": movimiento.fecha.isoformat(),
                "medio": movimiento.medio,
                "tipo": movimiento.tipo,
                "monto": movimiento.monto,
            },
        )

    def _auditar_ajuste(
        self,
        *,
        tenant_id: str,
        actor_id: str,
        ajuste: Ajuste,
    ) -> None:
        """D11: el ajuste post-cierre deja auditoría sin PHI."""
        self._auditoria.registrar(
            tenant_id=tenant_id,
            accion="AJUSTE_POST_CIERRE_REGISTRADO",
            actor=actor_id,
            entidad="ajuste_post_cierre",
            entidad_id=ajuste.id,
            antes=None,
            despues={
                "cierre_id": ajuste.cierre_id,
                "tipo": ajuste.tipo,
                "monto": ajuste.monto,
                "medio": ajuste.medio,
                "compensatorio_id": ajuste.compensatorio_id,
                "movimiento_original_id": ajuste.movimiento_original_id,
                "cobro_pendiente_id": ajuste.cobro_pendiente_id,
            },
        )
