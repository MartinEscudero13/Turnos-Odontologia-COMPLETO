"""Repositorios SQLAlchemy de C-14 (links, eventos, cola y solapamientos)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.calendario.puertos import (
    CODIGO_LINK_DUPLICADO,
    AccionEnvio,
    CalendarLink,
    ConflictoCalendario,
    EnvioCalendario,
    EstadoEnvio,
    EstadoEvento,
    EstadoLink,
    EventoCalendario,
    OrigenEvento,
)
from app.models.calendario import CalendarEnvio as EnvioModel
from app.models.calendario import CalendarEvento as EventoModel
from app.models.calendario import CalendarLink as LinkModel
from app.models.turno import Turno

__all__ = ["ColaCalendarioSQL", "EventoSQL", "LinkSQL", "TurnosSolapadosSQL"]


def _uuid(valor: str) -> uuid.UUID:
    return uuid.UUID(valor)


def _fijar_tenant(session: Session, tenant_id: str) -> None:
    session.execute(
        text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": tenant_id}
    )


def _a_link(modelo: LinkModel) -> CalendarLink:
    return CalendarLink(
        id=str(modelo.id),
        tenant_id=str(modelo.tenant_id),
        profesional_id=str(modelo.profesional_id),
        gcal_calendar_id=modelo.gcal_calendar_id,
        oauth_ref=modelo.oauth_ref,
        estado=modelo.estado,  # type: ignore[arg-type]
        ultima_sync=modelo.ultima_sync,
        creado_en=modelo.creado_en,
    )


def _a_evento(modelo: EventoModel) -> EventoCalendario:
    return EventoCalendario(
        id=str(modelo.id),
        tenant_id=str(modelo.tenant_id),
        link_id=str(modelo.link_id),
        turno_id=None if modelo.turno_id is None else str(modelo.turno_id),
        gcal_event_id=modelo.gcal_event_id,
        origen=modelo.origen,  # type: ignore[arg-type]
        estado=modelo.estado,  # type: ignore[arg-type]
        inicio=modelo.inicio,
        fin=modelo.fin,
        resumen=modelo.resumen,
        creado_en=modelo.creado_en,
    )


def _a_envio(modelo: EnvioModel) -> EnvioCalendario:
    return EnvioCalendario(
        id=str(modelo.id),
        tenant_id=str(modelo.tenant_id),
        link_id=str(modelo.link_id),
        evento_id=None if modelo.evento_id is None else str(modelo.evento_id),
        accion=modelo.accion,  # type: ignore[arg-type]
        intentos=modelo.intentos,
        proximo_intento=modelo.proximo_intento,
        estado=modelo.estado,  # type: ignore[arg-type]
        creado_en=modelo.creado_en,
    )


class LinkSQL:
    def __init__(self, session: Session) -> None:
        self._session = session

    def crear(
        self,
        *,
        tenant_id: str,
        profesional_id: str,
        gcal_calendar_id: str,
        oauth_ref: str,
        ahora: datetime,
    ) -> CalendarLink:
        _fijar_tenant(self._session, tenant_id)
        modelo = LinkModel(
            tenant_id=_uuid(tenant_id),
            profesional_id=_uuid(profesional_id),
            gcal_calendar_id=gcal_calendar_id,
            oauth_ref=oauth_ref,
            estado="CONECTADO",
            ultima_sync=ahora,
            creado_en=ahora,
            actualizado_en=ahora,
        )
        try:
            with self._session.begin_nested():
                self._session.add(modelo)
                self._session.flush()
        except IntegrityError as exc:
            raise ConflictoCalendario(
                CODIGO_LINK_DUPLICADO, "el profesional ya tiene un calendario conectado"
            ) from exc
        return _a_link(modelo)

    def obtener(self, *, tenant_id: str, link_id: str) -> CalendarLink | None:
        _fijar_tenant(self._session, tenant_id)
        modelo = self._session.scalar(
            select(LinkModel).where(
                LinkModel.id == _uuid(link_id), LinkModel.tenant_id == _uuid(tenant_id)
            )
        )
        return None if modelo is None else _a_link(modelo)

    def obtener_publico(self, *, link_id: str) -> CalendarLink | None:
        modelo = self._session.scalar(select(LinkModel).where(LinkModel.id == _uuid(link_id)))
        return None if modelo is None else _a_link(modelo)

    def por_profesional(self, *, tenant_id: str, profesional_id: str) -> CalendarLink | None:
        _fijar_tenant(self._session, tenant_id)
        modelo = self._session.scalar(
            select(LinkModel).where(
                LinkModel.tenant_id == _uuid(tenant_id),
                LinkModel.profesional_id == _uuid(profesional_id),
            )
        )
        return None if modelo is None else _a_link(modelo)

    def listar(self, *, tenant_id: str, profesional_id: str | None = None) -> list[CalendarLink]:
        _fijar_tenant(self._session, tenant_id)
        consulta = select(LinkModel).where(LinkModel.tenant_id == _uuid(tenant_id))
        if profesional_id is not None:
            consulta = consulta.where(LinkModel.profesional_id == _uuid(profesional_id))
        return [_a_link(modelo) for modelo in self._session.scalars(consulta)]

    def actualizar_estado(
        self, *, tenant_id: str, link_id: str, estado: EstadoLink, ahora: datetime
    ) -> CalendarLink:
        _fijar_tenant(self._session, tenant_id)
        modelo = self._session.scalar(
            select(LinkModel).where(
                LinkModel.id == _uuid(link_id), LinkModel.tenant_id == _uuid(tenant_id)
            )
        )
        if modelo is None:
            raise KeyError(link_id)
        modelo.estado = estado
        modelo.ultima_sync = ahora
        modelo.actualizado_en = ahora
        self._session.flush()
        return _a_link(modelo)


class EventoSQL:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(
        self,
        *,
        tenant_id: str,
        link_id: str,
        turno_id: str | None,
        gcal_event_id: str | None,
        origen: OrigenEvento,
        estado: EstadoEvento,
        inicio: datetime,
        fin: datetime,
        resumen: str,
        ahora: datetime,
    ) -> EventoCalendario:
        _fijar_tenant(self._session, tenant_id)
        modelo: EventoModel | None = None
        if turno_id is not None:
            modelo = self._session.scalar(
                select(EventoModel).where(
                    EventoModel.tenant_id == _uuid(tenant_id),
                    EventoModel.link_id == _uuid(link_id),
                    EventoModel.turno_id == _uuid(turno_id),
                )
            )
        if modelo is None and gcal_event_id is not None:
            modelo = self._session.scalar(
                select(EventoModel).where(
                    EventoModel.tenant_id == _uuid(tenant_id),
                    EventoModel.link_id == _uuid(link_id),
                    EventoModel.gcal_event_id == gcal_event_id,
                )
            )
        if modelo is None:
            modelo = EventoModel(
                tenant_id=_uuid(tenant_id),
                link_id=_uuid(link_id),
                turno_id=None if turno_id is None else _uuid(turno_id),
                gcal_event_id=gcal_event_id,
                origen=origen,
                estado=estado,
                inicio=inicio,
                fin=fin,
                resumen=resumen,
                creado_en=ahora,
                actualizado_en=ahora,
            )
            self._session.add(modelo)
        else:
            modelo.gcal_event_id = gcal_event_id
            modelo.estado = estado
            modelo.inicio = inicio
            modelo.fin = fin
            modelo.resumen = resumen
            modelo.actualizado_en = ahora
        self._session.flush()
        return _a_evento(modelo)

    def por_turno(self, *, tenant_id: str, link_id: str, turno_id: str) -> EventoCalendario | None:
        _fijar_tenant(self._session, tenant_id)
        modelo = self._session.scalar(
            select(EventoModel).where(
                EventoModel.tenant_id == _uuid(tenant_id),
                EventoModel.link_id == _uuid(link_id),
                EventoModel.turno_id == _uuid(turno_id),
            )
        )
        return None if modelo is None else _a_evento(modelo)

    def por_gcal(
        self, *, tenant_id: str, link_id: str, gcal_event_id: str
    ) -> EventoCalendario | None:
        _fijar_tenant(self._session, tenant_id)
        modelo = self._session.scalar(
            select(EventoModel).where(
                EventoModel.tenant_id == _uuid(tenant_id),
                EventoModel.link_id == _uuid(link_id),
                EventoModel.gcal_event_id == gcal_event_id,
            )
        )
        return None if modelo is None else _a_evento(modelo)

    def obtener(self, *, tenant_id: str, evento_id: str) -> EventoCalendario | None:
        _fijar_tenant(self._session, tenant_id)
        modelo = self._session.scalar(
            select(EventoModel).where(
                EventoModel.id == _uuid(evento_id), EventoModel.tenant_id == _uuid(tenant_id)
            )
        )
        return None if modelo is None else _a_evento(modelo)

    def listar_bloqueos(
        self, *, tenant_id: str, desde: datetime, hasta: datetime
    ) -> list[EventoCalendario]:
        _fijar_tenant(self._session, tenant_id)
        return [
            _a_evento(modelo)
            for modelo in self._session.scalars(
                select(EventoModel)
                .where(
                    EventoModel.tenant_id == _uuid(tenant_id),
                    EventoModel.origen == "EXTERNO",
                    EventoModel.estado.in_(("BLOQUEADO", "CONFLICTO_SISTEMA")),
                    EventoModel.inicio < hasta,
                    EventoModel.fin > desde,
                )
                .order_by(EventoModel.inicio)
            )
        ]


class ColaCalendarioSQL:
    def __init__(self, session: Session) -> None:
        self._session = session

    def encolar(
        self,
        *,
        tenant_id: str,
        link_id: str,
        evento_id: str | None,
        accion: AccionEnvio,
        ahora: datetime,
    ) -> EnvioCalendario:
        _fijar_tenant(self._session, tenant_id)
        modelo = EnvioModel(
            tenant_id=_uuid(tenant_id),
            link_id=_uuid(link_id),
            evento_id=None if evento_id is None else _uuid(evento_id),
            accion=accion,
            intentos=0,
            proximo_intento=ahora,
            estado="PENDIENTE",
            creado_en=ahora,
        )
        self._session.add(modelo)
        self._session.flush()
        return _a_envio(modelo)

    def pendientes(self, *, tenant_id: str) -> list[EnvioCalendario]:
        _fijar_tenant(self._session, tenant_id)
        return [
            _a_envio(modelo)
            for modelo in self._session.scalars(
                select(EnvioModel)
                .where(
                    EnvioModel.tenant_id == _uuid(tenant_id),
                    EnvioModel.estado == "PENDIENTE",
                )
                .order_by(EnvioModel.proximo_intento)
            )
        ]

    def actualizar(
        self,
        *,
        tenant_id: str,
        envio_id: str,
        estado: EstadoEnvio,
        intentos: int,
        proximo_intento: datetime,
    ) -> EnvioCalendario:
        _fijar_tenant(self._session, tenant_id)
        modelo = self._session.scalar(
            select(EnvioModel).where(
                EnvioModel.id == _uuid(envio_id), EnvioModel.tenant_id == _uuid(tenant_id)
            )
        )
        if modelo is None:
            raise KeyError(envio_id)
        modelo.estado = estado
        modelo.intentos = intentos
        modelo.proximo_intento = proximo_intento
        self._session.flush()
        return _a_envio(modelo)


class TurnosSolapadosSQL:
    def __init__(self, session: Session) -> None:
        self._session = session

    def solapados(
        self, *, tenant_id: str, profesional_id: str, inicio: datetime, fin: datetime
    ) -> list[str]:
        _fijar_tenant(self._session, tenant_id)
        return [
            str(turno_id)
            for turno_id in self._session.scalars(
                select(Turno.id).where(
                    Turno.tenant_id == _uuid(tenant_id),
                    Turno.profesional_id == _uuid(profesional_id),
                    Turno.inicio < fin,
                    Turno.fin > inicio,
                    Turno.estado.notin_(("CANCELADO", "REPROGRAMADO")),
                )
            )
        ]
