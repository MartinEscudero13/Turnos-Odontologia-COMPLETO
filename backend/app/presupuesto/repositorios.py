"""Repositorios SQLAlchemy de presupuesto — C-09 sobre PostgreSQL, C-10 §5 (M4).

Adaptadores de persistencia de `app/presupuesto/puertos.py` sobre una `Session`
compartida con la caja. Existen para probar la atomicidad real de M4: la
aceptación de C-09 y la escritura de caja viven en la **misma** transacción, así
que un fallo de caja revierte `aceptaciones`, el estado del presupuesto y las
líneas (D6.7). **No se modifica** el servicio ni los puertos de C-09.

`aceptaciones` no tiene columna `medio` (M7/D8): el medio vive sólo en
`movimientos_caja`. La lectura devuelve `medio=None`; el objeto devuelto por
`registrar` conserva el medio recibido para que la respuesta del caso de uso sea
fiel sin agregar DDL a la 008.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.transaccion import TransaccionSQL
from app.models.presupuesto import (
    Aceptacion as AceptacionModel,
)
from app.models.presupuesto import (
    Presupuesto as PresupuestoModel,
)
from app.models.presupuesto import (
    PresupuestoLinea,
)
from app.presupuesto.puertos import (
    Aceptacion,
    EstadoPresupuesto,
    IdempotencyKeyDuplicada,
    Linea,
    MedioPago,
    OrigenCobertura,
    Presupuesto,
)
from app.turnos.servicio import NoEncontrado

__all__ = [
    "AceptacionesSQL",
    "LineasSQL",
    "PresupuestosSQL",
    "UnidadDeTrabajoPresupuestoSQL",
]

_UNIQUE_IDEMPOTENCY = "presupuesto_lineas_tenant_idempotency_key_unique"
# RLS fail-closed: la fila se busca con el tenant fijado en la sesión.
_FIJAR_TENANT = text("SELECT set_config('app.tenant_id', :tenant, true)")


def _ahora(ahora: datetime | None) -> datetime:
    return ahora if ahora is not None else datetime.now(UTC)


def _uuid(valor: str) -> uuid.UUID:
    return uuid.UUID(valor)


def _presupuesto(fila: PresupuestoModel) -> Presupuesto:
    return Presupuesto(
        id=str(fila.id),
        tenant_id=str(fila.tenant_id),
        paciente_id=str(fila.paciente_id),
        estado=cast(EstadoPresupuesto, fila.estado),
        vence_en=fila.vence_en,
        creado_en=fila.creado_en,
        actualizado_en=fila.actualizado_en,
    )


def _linea(fila: PresupuestoLinea) -> Linea:
    return Linea(
        id=str(fila.id),
        tenant_id=str(fila.tenant_id),
        presupuesto_id=str(fila.presupuesto_id),
        hallazgo_id=str(fila.hallazgo_id) if fila.hallazgo_id is not None else None,
        pieza_fdi=fila.pieza_fdi,
        prestacion_id=str(fila.prestacion_id),
        monto=fila.monto,
        cobertura_os=fila.cobertura_os,
        a_cargo_paciente=fila.a_cargo_paciente,
        origen_cobertura=cast(OrigenCobertura, fila.origen_cobertura),
        validada_en_vivo=fila.validada_en_vivo,
        idempotency_key=(
            str(fila.idempotency_key) if fila.idempotency_key is not None else None
        ),
        creado_en=fila.creado_en,
    )


def _aceptacion(fila: AceptacionModel, *, medio: MedioPago | None = None) -> Aceptacion:
    return Aceptacion(
        id=str(fila.id),
        tenant_id=str(fila.tenant_id),
        linea_id=str(fila.linea_id),
        acepta=fila.acepta,
        fecha=fila.fecha,
        canal=fila.canal,
        medio=medio,
        creado_en=fila.creado_en,
    )


class PresupuestosSQL:
    """`PresupuestoRepositorio` sobre `presupuestos`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def crear(
        self, *, tenant_id: str, paciente_id: str, ahora: datetime | None = None
    ) -> Presupuesto:
        momento = _ahora(ahora)
        fila = PresupuestoModel(
            tenant_id=_uuid(tenant_id),
            paciente_id=_uuid(paciente_id),
            estado="BORRADOR",
            creado_en=momento,
            actualizado_en=momento,
        )
        self._session.add(fila)
        self._session.flush()
        return _presupuesto(fila)

    def obtener(self, *, tenant_id: str, presupuesto_id: str) -> Presupuesto | None:
        fila = self._session.get(PresupuestoModel, _uuid(presupuesto_id))
        if fila is None or str(fila.tenant_id) != tenant_id:
            return None
        return _presupuesto(fila)

    def listar(self, *, tenant_id: str, paciente_id: str) -> list[Presupuesto]:
        filas = self._session.scalars(
            select(PresupuestoModel)
            .where(
                PresupuestoModel.tenant_id == _uuid(tenant_id),
                PresupuestoModel.paciente_id == _uuid(paciente_id),
            )
            .order_by(PresupuestoModel.creado_en, PresupuestoModel.id)
        ).all()
        return [_presupuesto(fila) for fila in filas]

    def borrador_de_paciente(
        self, *, tenant_id: str, paciente_id: str
    ) -> Presupuesto | None:
        fila = self._session.scalars(
            select(PresupuestoModel)
            .where(
                PresupuestoModel.tenant_id == _uuid(tenant_id),
                PresupuestoModel.paciente_id == _uuid(paciente_id),
                PresupuestoModel.estado == "BORRADOR",
            )
            .order_by(PresupuestoModel.creado_en.desc(), PresupuestoModel.id.desc())
        ).first()
        return None if fila is None else _presupuesto(fila)

    def actualizar_estado(
        self,
        *,
        tenant_id: str,
        presupuesto_id: str,
        estado: EstadoPresupuesto,
        ahora: datetime | None = None,
    ) -> Presupuesto:
        fila = self._session.get(PresupuestoModel, _uuid(presupuesto_id))
        if fila is None or str(fila.tenant_id) != tenant_id:
            raise NoEncontrado("presupuesto no encontrado")
        fila.estado = estado
        fila.actualizado_en = _ahora(ahora)
        self._session.flush()
        return _presupuesto(fila)

    def emitir(
        self,
        *,
        tenant_id: str,
        presupuesto_id: str,
        vence_en: datetime | None,
        ahora: datetime | None = None,
    ) -> Presupuesto:
        fila = self._session.get(PresupuestoModel, _uuid(presupuesto_id))
        if fila is None or str(fila.tenant_id) != tenant_id:
            raise NoEncontrado("presupuesto no encontrado")
        fila.estado = "VIGENTE"
        fila.vence_en = vence_en
        fila.actualizado_en = _ahora(ahora)
        self._session.flush()
        return _presupuesto(fila)


class LineasSQL:
    """`LineaRepositorio` sobre `presupuesto_lineas` (sin UPDATE ni DELETE, D8.1)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def agregar(
        self,
        *,
        tenant_id: str,
        presupuesto_id: str,
        prestacion_id: str,
        monto: int,
        cobertura_os: int,
        a_cargo_paciente: int,
        origen_cobertura: OrigenCobertura,
        validada_en_vivo: bool,
        pieza_fdi: int | None = None,
        hallazgo_id: str | None = None,
        idempotency_key: str | None = None,
        ahora: datetime | None = None,
    ) -> Linea:
        fila = PresupuestoLinea(
            tenant_id=_uuid(tenant_id),
            presupuesto_id=_uuid(presupuesto_id),
            prestacion_id=_uuid(prestacion_id),
            monto=monto,
            cobertura_os=cobertura_os,
            a_cargo_paciente=a_cargo_paciente,
            origen_cobertura=origen_cobertura,
            validada_en_vivo=validada_en_vivo,
            pieza_fdi=pieza_fdi,
            hallazgo_id=_uuid(hallazgo_id) if hallazgo_id is not None else None,
            idempotency_key=(
                _uuid(idempotency_key) if idempotency_key is not None else None
            ),
            creado_en=_ahora(ahora),
        )
        self._session.add(fila)
        try:
            self._session.flush()
        except IntegrityError as exc:
            if _UNIQUE_IDEMPOTENCY in str(getattr(exc, "orig", exc)):
                raise IdempotencyKeyDuplicada(idempotency_key or "") from exc
            raise
        return _linea(fila)

    def listar(self, *, tenant_id: str, presupuesto_id: str) -> list[Linea]:
        filas = self._session.scalars(
            select(PresupuestoLinea)
            .where(
                PresupuestoLinea.tenant_id == _uuid(tenant_id),
                PresupuestoLinea.presupuesto_id == _uuid(presupuesto_id),
            )
            .order_by(PresupuestoLinea.creado_en, PresupuestoLinea.id)
        ).all()
        return [_linea(fila) for fila in filas]

    def por_idempotency_key(
        self, *, tenant_id: str, idempotency_key: str
    ) -> Linea | None:
        fila = self._session.scalars(
            select(PresupuestoLinea).where(
                PresupuestoLinea.tenant_id == _uuid(tenant_id),
                PresupuestoLinea.idempotency_key == _uuid(idempotency_key),
            )
        ).first()
        return None if fila is None else _linea(fila)

    def bloquear(self, *, tenant_id: str, linea_id: str) -> Linea:
        fila = self._session.get(
            PresupuestoLinea, _uuid(linea_id), with_for_update=True
        )
        if fila is None or str(fila.tenant_id) != tenant_id:
            raise NoEncontrado("línea de presupuesto no encontrada")
        return _linea(fila)


class AceptacionesSQL:
    """`AceptacionRepositorio`: ledger append-only en `aceptaciones` (RN-CL-02)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def registrar(
        self,
        *,
        tenant_id: str,
        linea_id: str,
        acepta: bool,
        fecha: datetime,
        canal: str,
        medio: MedioPago | None = None,
        ahora: datetime | None = None,
    ) -> Aceptacion:
        fila = AceptacionModel(
            tenant_id=_uuid(tenant_id),
            linea_id=_uuid(linea_id),
            acepta=acepta,
            fecha=fecha,
            canal=canal,
            creado_en=_ahora(ahora),
        )
        self._session.add(fila)
        self._session.flush()
        # El medio no tiene columna en `aceptaciones` (M7): se conserva en el
        # objeto devuelto para no perderlo en la respuesta del caso de uso.
        return _aceptacion(fila, medio=medio)

    def ultima_por_linea(self, *, tenant_id: str, linea_id: str) -> Aceptacion | None:
        fila = self._session.scalars(
            select(AceptacionModel)
            .where(
                AceptacionModel.tenant_id == _uuid(tenant_id),
                AceptacionModel.linea_id == _uuid(linea_id),
            )
            .order_by(AceptacionModel.creado_en.desc(), AceptacionModel.id.desc())
        ).first()
        return None if fila is None else _aceptacion(fila)

    def listar_por_linea(self, *, tenant_id: str, linea_id: str) -> list[Aceptacion]:
        filas = self._session.scalars(
            select(AceptacionModel)
            .where(
                AceptacionModel.tenant_id == _uuid(tenant_id),
                AceptacionModel.linea_id == _uuid(linea_id),
            )
            .order_by(AceptacionModel.creado_en, AceptacionModel.id)
        ).all()
        return [_aceptacion(fila) for fila in filas]


class UnidadDeTrabajoPresupuestoSQL(TransaccionSQL):
    """UoW de presupuesto: lock de la línea antes de revalidar (D4/B1)."""

    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self._lineas = LineasSQL(session)

    def bloquear_linea(self, *, tenant_id: str, linea_id: str) -> Linea:
        self.session.execute(_FIJAR_TENANT, {"tenant": tenant_id})
        return self._lineas.bloquear(tenant_id=tenant_id, linea_id=linea_id)
