"""Repositorios SQLAlchemy de C-12 (obras sociales, coberturas y liquidación).

Traducen entre las entidades de `puertos.py` y los modelos de
`models/obras_sociales.py`. Cada método fija `app.tenant_id` para que la RLS de
la 010 aplique con el rol de la app y filtra explícitamente por `tenant_id`.

Las violaciones de los UNIQUE se convierten en las señales de repositorio que el
servicio ya conoce (`ObraSocialDuplicada`, `LiquidacionDuplicada`).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.catalogos import Paciente, Prestacion
from app.models.obras_sociales import Cobertura as CoberturaModel
from app.models.obras_sociales import Liquidacion as LiquidacionModel
from app.models.obras_sociales import LiquidacionLinea as LiquidacionLineaModel
from app.models.obras_sociales import ObraSocial as ObraSocialModel
from app.models.turno import Turno
from app.obras_sociales.puertos import (
    Cobertura,
    LineaLiquidacion,
    Liquidacion,
    LiquidacionDuplicada,
    ModoCobertura,
    ObraSocial,
    ObraSocialDuplicada,
    TurnoAtendido,
)

__all__ = [
    "CoberturaSQL",
    "LiquidacionSQL",
    "ObraSocialSQL",
    "PacienteObraSocialSQL",
    "PrestacionPrecioSQL",
    "TurnosAtendidosSQL",
]

TZ_OPERATIVA = timezone(timedelta(hours=-3))


def _uuid(valor: str) -> uuid.UUID:
    return uuid.UUID(valor)


def _fijar_tenant(session: Session, tenant_id: str) -> None:
    session.execute(
        text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": tenant_id}
    )


def _a_obra_social(modelo: ObraSocialModel) -> ObraSocial:
    return ObraSocial(
        id=str(modelo.id),
        tenant_id=str(modelo.tenant_id),
        nombre=modelo.nombre,
        activa=modelo.activa,
        creado_en=modelo.creado_en,
    )


def _a_cobertura(modelo: CoberturaModel) -> Cobertura:
    return Cobertura(
        id=str(modelo.id),
        tenant_id=str(modelo.tenant_id),
        obra_social_id=str(modelo.obra_social_id),
        prestacion_id=str(modelo.prestacion_id),
        modo=modelo.modo,  # type: ignore[arg-type]
        valor=modelo.valor,
        tope_centavos=modelo.tope_centavos,
        creado_en=modelo.creado_en,
    )


def _a_linea(modelo: LiquidacionLineaModel) -> LineaLiquidacion:
    return LineaLiquidacion(
        id=str(modelo.id),
        turno_id=str(modelo.turno_id),
        paciente_id=str(modelo.paciente_id),
        prestacion_id=str(modelo.prestacion_id),
        fecha=modelo.fecha,
        monto_centavos=modelo.monto_centavos,
    )


def _a_liquidacion(
    modelo: LiquidacionModel, lineas: list[LiquidacionLineaModel]
) -> Liquidacion:
    return Liquidacion(
        id=str(modelo.id),
        tenant_id=str(modelo.tenant_id),
        obra_social_id=str(modelo.obra_social_id),
        periodo_desde=modelo.periodo_desde,
        periodo_hasta=modelo.periodo_hasta,
        estado=modelo.estado,  # type: ignore[arg-type]
        total_centavos=modelo.total_centavos,
        creado_en=modelo.creado_en,
        cerrada_en=modelo.cerrada_en,
        lineas=tuple(_a_linea(linea) for linea in lineas),
    )


class ObraSocialSQL:
    def __init__(self, session: Session) -> None:
        self._session = session

    def crear(self, *, tenant_id: str, nombre: str, ahora: datetime) -> ObraSocial:
        _fijar_tenant(self._session, tenant_id)
        modelo = ObraSocialModel(
            tenant_id=_uuid(tenant_id),
            nombre=nombre,
            activa=True,
            creado_en=ahora,
            actualizado_en=ahora,
        )
        try:
            with self._session.begin_nested():
                self._session.add(modelo)
                self._session.flush()
        except IntegrityError as exc:
            raise ObraSocialDuplicada(nombre) from exc
        return _a_obra_social(modelo)

    def obtener(self, *, tenant_id: str, obra_social_id: str) -> ObraSocial | None:
        _fijar_tenant(self._session, tenant_id)
        modelo = self._session.scalar(
            select(ObraSocialModel).where(
                ObraSocialModel.id == _uuid(obra_social_id),
                ObraSocialModel.tenant_id == _uuid(tenant_id),
            )
        )
        return None if modelo is None else _a_obra_social(modelo)

    def por_nombre(self, *, tenant_id: str, nombre: str) -> ObraSocial | None:
        _fijar_tenant(self._session, tenant_id)
        modelo = self._session.scalar(
            select(ObraSocialModel).where(
                ObraSocialModel.tenant_id == _uuid(tenant_id),
                ObraSocialModel.nombre == nombre,
            )
        )
        return None if modelo is None else _a_obra_social(modelo)

    def listar(self, *, tenant_id: str, solo_activas: bool = False) -> list[ObraSocial]:
        _fijar_tenant(self._session, tenant_id)
        consulta = select(ObraSocialModel).where(
            ObraSocialModel.tenant_id == _uuid(tenant_id)
        )
        if solo_activas:
            consulta = consulta.where(ObraSocialModel.activa.is_(True))
        return [
            _a_obra_social(modelo)
            for modelo in self._session.scalars(
                consulta.order_by(ObraSocialModel.nombre)
            )
        ]

    def cambiar_estado(
        self, *, tenant_id: str, obra_social_id: str, activa: bool, ahora: datetime
    ) -> ObraSocial:
        _fijar_tenant(self._session, tenant_id)
        modelo = self._session.scalar(
            select(ObraSocialModel).where(
                ObraSocialModel.id == _uuid(obra_social_id),
                ObraSocialModel.tenant_id == _uuid(tenant_id),
            )
        )
        if modelo is None:
            raise KeyError(obra_social_id)
        modelo.activa = activa
        modelo.actualizado_en = ahora
        self._session.flush()
        return _a_obra_social(modelo)


class CoberturaSQL:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(
        self,
        *,
        tenant_id: str,
        obra_social_id: str,
        prestacion_id: str,
        modo: ModoCobertura,
        valor: int,
        tope_centavos: int | None,
        ahora: datetime,
    ) -> Cobertura:
        _fijar_tenant(self._session, tenant_id)
        modelo = self._session.scalar(
            select(CoberturaModel).where(
                CoberturaModel.tenant_id == _uuid(tenant_id),
                CoberturaModel.obra_social_id == _uuid(obra_social_id),
                CoberturaModel.prestacion_id == _uuid(prestacion_id),
            )
        )
        if modelo is None:
            modelo = CoberturaModel(
                tenant_id=_uuid(tenant_id),
                obra_social_id=_uuid(obra_social_id),
                prestacion_id=_uuid(prestacion_id),
                modo=modo,
                valor=valor,
                tope_centavos=tope_centavos,
                creado_en=ahora,
                actualizado_en=ahora,
            )
            self._session.add(modelo)
        else:
            modelo.modo = modo
            modelo.valor = valor
            modelo.tope_centavos = tope_centavos
            modelo.actualizado_en = ahora
        self._session.flush()
        return _a_cobertura(modelo)

    def obtener(
        self, *, tenant_id: str, obra_social_id: str, prestacion_id: str
    ) -> Cobertura | None:
        _fijar_tenant(self._session, tenant_id)
        modelo = self._session.scalar(
            select(CoberturaModel).where(
                CoberturaModel.tenant_id == _uuid(tenant_id),
                CoberturaModel.obra_social_id == _uuid(obra_social_id),
                CoberturaModel.prestacion_id == _uuid(prestacion_id),
            )
        )
        return None if modelo is None else _a_cobertura(modelo)

    def listar(self, *, tenant_id: str, obra_social_id: str | None = None) -> list[Cobertura]:
        _fijar_tenant(self._session, tenant_id)
        consulta = select(CoberturaModel).where(CoberturaModel.tenant_id == _uuid(tenant_id))
        if obra_social_id is not None:
            consulta = consulta.where(CoberturaModel.obra_social_id == _uuid(obra_social_id))
        return [
            _a_cobertura(modelo)
            for modelo in self._session.scalars(
                consulta.order_by(CoberturaModel.obra_social_id, CoberturaModel.prestacion_id)
            )
        ]


class LiquidacionSQL:
    def __init__(self, session: Session) -> None:
        self._session = session

    def obtener(self, *, tenant_id: str, liquidacion_id: str) -> Liquidacion | None:
        _fijar_tenant(self._session, tenant_id)
        modelo = self._session.scalar(
            select(LiquidacionModel).where(
                LiquidacionModel.id == _uuid(liquidacion_id),
                LiquidacionModel.tenant_id == _uuid(tenant_id),
            )
        )
        if modelo is None:
            return None
        lineas = list(
            self._session.scalars(
                select(LiquidacionLineaModel)
                .where(
                    LiquidacionLineaModel.tenant_id == _uuid(tenant_id),
                    LiquidacionLineaModel.liquidacion_id == modelo.id,
                )
                .order_by(LiquidacionLineaModel.fecha, LiquidacionLineaModel.id)
            )
        )
        return _a_liquidacion(modelo, lineas)

    def buscar(
        self, *, tenant_id: str, obra_social_id: str, desde: date, hasta: date
    ) -> Liquidacion | None:
        _fijar_tenant(self._session, tenant_id)
        modelo = self._session.scalar(
            select(LiquidacionModel).where(
                LiquidacionModel.tenant_id == _uuid(tenant_id),
                LiquidacionModel.obra_social_id == _uuid(obra_social_id),
                LiquidacionModel.periodo_desde == desde,
                LiquidacionModel.periodo_hasta == hasta,
            )
        )
        return None if modelo is None else self.obtener(
            tenant_id=tenant_id, liquidacion_id=str(modelo.id)
        )

    def listar(
        self,
        *,
        tenant_id: str,
        obra_social_id: str | None = None,
        desde: date | None = None,
        hasta: date | None = None,
    ) -> list[Liquidacion]:
        _fijar_tenant(self._session, tenant_id)
        consulta = select(LiquidacionModel).where(
            LiquidacionModel.tenant_id == _uuid(tenant_id)
        )
        if obra_social_id is not None:
            consulta = consulta.where(LiquidacionModel.obra_social_id == _uuid(obra_social_id))
        if desde is not None:
            consulta = consulta.where(LiquidacionModel.periodo_hasta >= desde)
        if hasta is not None:
            consulta = consulta.where(LiquidacionModel.periodo_desde <= hasta)
        return [
            _a_liquidacion(modelo, [])
            for modelo in self._session.scalars(
                consulta.order_by(LiquidacionModel.periodo_desde, LiquidacionModel.id)
            )
        ]

    def crear(
        self,
        *,
        tenant_id: str,
        obra_social_id: str,
        desde: date,
        hasta: date,
        ahora: datetime,
    ) -> Liquidacion:
        _fijar_tenant(self._session, tenant_id)
        modelo = LiquidacionModel(
            tenant_id=_uuid(tenant_id),
            obra_social_id=_uuid(obra_social_id),
            periodo_desde=desde,
            periodo_hasta=hasta,
            estado="BORRADOR",
            total_centavos=0,
            creado_en=ahora,
        )
        try:
            with self._session.begin_nested():
                self._session.add(modelo)
                self._session.flush()
        except IntegrityError as exc:
            raise LiquidacionDuplicada(f"{obra_social_id}:{desde}:{hasta}") from exc
        return _a_liquidacion(modelo, [])

    def reemplazar_lineas(
        self,
        *,
        tenant_id: str,
        liquidacion_id: str,
        lineas: list[tuple[TurnoAtendido, int]],
    ) -> Liquidacion:
        _fijar_tenant(self._session, tenant_id)
        modelo = self._session.scalar(
            select(LiquidacionModel).where(
                LiquidacionModel.id == _uuid(liquidacion_id),
                LiquidacionModel.tenant_id == _uuid(tenant_id),
            )
        )
        if modelo is None:
            raise KeyError(liquidacion_id)
        self._session.execute(
            delete(LiquidacionLineaModel).where(
                LiquidacionLineaModel.tenant_id == _uuid(tenant_id),
                LiquidacionLineaModel.liquidacion_id == modelo.id,
            )
        )
        for turno, monto in lineas:
            self._session.add(
                LiquidacionLineaModel(
                    tenant_id=_uuid(tenant_id),
                    liquidacion_id=modelo.id,
                    turno_id=_uuid(turno.turno_id),
                    paciente_id=_uuid(turno.paciente_id),
                    prestacion_id=_uuid(turno.prestacion_id),
                    fecha=turno.inicio,
                    monto_centavos=monto,
                )
            )
        modelo.total_centavos = sum(monto for _, monto in lineas)
        self._session.flush()
        return self.obtener(tenant_id=tenant_id, liquidacion_id=liquidacion_id) or _a_liquidacion(
            modelo, []
        )

    def cerrar(
        self, *, tenant_id: str, liquidacion_id: str, ahora: datetime
    ) -> Liquidacion:
        _fijar_tenant(self._session, tenant_id)
        modelo = self._session.scalar(
            select(LiquidacionModel).where(
                LiquidacionModel.id == _uuid(liquidacion_id),
                LiquidacionModel.tenant_id == _uuid(tenant_id),
            )
        )
        if modelo is None:
            raise KeyError(liquidacion_id)
        modelo.estado = "CERRADA"
        modelo.cerrada_en = ahora
        self._session.flush()
        return self.obtener(tenant_id=tenant_id, liquidacion_id=liquidacion_id) or _a_liquidacion(
            modelo, []
        )


class TurnosAtendidosSQL:
    def __init__(self, session: Session) -> None:
        self._session = session

    def atendidos(
        self, *, tenant_id: str, obra_social_id: str, desde: date, hasta: date
    ) -> list[TurnoAtendido]:
        _fijar_tenant(self._session, tenant_id)
        inicio = datetime.combine(desde, time.min, tzinfo=TZ_OPERATIVA)
        fin = datetime.combine(hasta, time.min, tzinfo=TZ_OPERATIVA)
        filas = self._session.execute(
            select(
                Turno.id,
                Turno.paciente_id,
                Turno.prestacion_id,
                Turno.inicio,
                Prestacion.precio_base,
            )
            .join(Paciente, Paciente.id == Turno.paciente_id)
            .join(Prestacion, Prestacion.id == Turno.prestacion_id)
            .where(
                Turno.tenant_id == _uuid(tenant_id),
                Turno.estado == "PRESENTE",
                Turno.inicio >= inicio,
                Turno.inicio < fin,
                Paciente.tenant_id == _uuid(tenant_id),
                Paciente.obra_social_id == _uuid(obra_social_id),
            )
            .order_by(Turno.inicio)
        ).all()
        return [
            TurnoAtendido(
                turno_id=str(fila[0]),
                paciente_id=str(fila[1]),
                prestacion_id=str(fila[2]),
                inicio=fila[3],
                precio_base_centavos=fila[4],
            )
            for fila in filas
        ]


class PacienteObraSocialSQL:
    def __init__(self, session: Session) -> None:
        self._session = session

    def existe(self, *, tenant_id: str, paciente_id: str) -> bool:
        _fijar_tenant(self._session, tenant_id)
        return (
            self._session.scalar(
                select(Paciente.id).where(
                    Paciente.id == _uuid(paciente_id),
                    Paciente.tenant_id == _uuid(tenant_id),
                )
            )
            is not None
        )

    def obra_social(self, *, tenant_id: str, paciente_id: str) -> str | None:
        _fijar_tenant(self._session, tenant_id)
        valor = self._session.scalar(
            select(Paciente.obra_social_id).where(
                Paciente.id == _uuid(paciente_id),
                Paciente.tenant_id == _uuid(tenant_id),
            )
        )
        return None if valor is None else str(valor)


class PrestacionPrecioSQL:
    def __init__(self, session: Session) -> None:
        self._session = session

    def precio_base(self, *, tenant_id: str, prestacion_id: str) -> int | None:
        _fijar_tenant(self._session, tenant_id)
        return self._session.scalar(
            select(Prestacion.precio_base).where(
                Prestacion.id == _uuid(prestacion_id),
                Prestacion.tenant_id == _uuid(tenant_id),
            )
        )
