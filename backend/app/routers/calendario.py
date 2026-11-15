"""Router FastAPI de Google Calendar — C-14.

RBAC: `ADMIN` administra; `ODONTOLOGO` sólo su propio link; `RECEPCION` lee.
Los errores de dominio los mapea el handler global de `TurnoError`.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.calendario.puertos import (
    CalendarLink,
    EventoCalendario,
    ResultadoPush,
    TurnoCalendario,
)
from app.calendario.servicio import ResultadoCola, ServicioCalendario
from app.routers.turnos import actor_desde_headers
from app.schemas.calendario import (
    ColaOut,
    EventoOut,
    LinkIn,
    LinkOut,
    PushIn,
    PushOut,
    WebhookIn,
)
from app.turnos.servicio import Actor

__all__ = ["crear_router"]


def _link_out(link: CalendarLink) -> LinkOut:
    return LinkOut(
        id=link.id,
        profesional_id=link.profesional_id,
        gcal_calendar_id=link.gcal_calendar_id,
        estado=link.estado,
        ultima_sync=link.ultima_sync,
        creado_en=link.creado_en,
    )


def _evento_out(evento: EventoCalendario) -> EventoOut:
    return EventoOut(
        id=evento.id,
        link_id=evento.link_id,
        turno_id=evento.turno_id,
        gcal_event_id=evento.gcal_event_id,
        origen=evento.origen,
        estado=evento.estado,
        inicio=evento.inicio,
        fin=evento.fin,
        resumen=evento.resumen,
    )


def _push_out(resultado: ResultadoPush) -> PushOut:
    return PushOut(
        estado=resultado.estado,
        evento=None if resultado.evento is None else _evento_out(resultado.evento),
    )


def _cola_out(resultado: ResultadoCola) -> ColaOut:
    return ColaOut(
        procesados=resultado.procesados,
        pendientes=resultado.pendientes,
        agotados=resultado.agotados,
        token_revocado=resultado.token_revocado,
    )


def crear_router(svc: ServicioCalendario) -> APIRouter:
    r = APIRouter()

    @r.post("/api/calendar/oauth", status_code=201, response_model=LinkOut)
    def conectar(body: LinkIn, actor: Actor = Depends(actor_desde_headers)) -> LinkOut:
        return _link_out(
            svc.conectar(
                actor,
                profesional_id=body.profesional_id,
                gcal_calendar_id=body.gcal_calendar_id,
                oauth_ref=body.oauth_ref,
            )
        )

    @r.get("/api/calendar/links", response_model=list[LinkOut])
    def listar_links(
        profesional_id: str | None = None, actor: Actor = Depends(actor_desde_headers)
    ) -> list[LinkOut]:
        return [
            _link_out(link)
            for link in svc.listar_links(actor, profesional_id=profesional_id)
        ]

    @r.delete("/api/calendar/links/{link_id}", response_model=LinkOut)
    def desconectar(link_id: str, actor: Actor = Depends(actor_desde_headers)) -> LinkOut:
        return _link_out(svc.desconectar(actor, link_id=link_id))

    @r.post("/api/calendar/push", response_model=PushOut)
    def push(body: PushIn, actor: Actor = Depends(actor_desde_headers)) -> PushOut:
        # La lectura valida RBAC y tenant; el push interno no necesita actor.
        svc.listar_links(actor)
        return _push_out(
            svc.push_turno(
                tenant_id=actor.tenant_id,
                turno=TurnoCalendario(
                    turno_id=body.turno_id,
                    profesional_id=body.profesional_id,
                    inicio=body.inicio,
                    fin=body.fin,
                    estado=body.estado,
                    resumen=body.resumen,
                ),
            )
        )

    @r.post("/api/calendar/webhook", response_model=EventoOut)
    def webhook(body: WebhookIn) -> EventoOut:
        return _evento_out(
            svc.recibir_externo(
                link_id=body.link_id,
                token=body.token,
                event_id=body.event_id,
                inicio=body.inicio,
                fin=body.fin,
                resumen=body.resumen,
            )
        )

    @r.get("/api/calendar/bloqueos", response_model=list[EventoOut])
    def bloqueos(
        desde: datetime = Query(),
        hasta: datetime = Query(),
        actor: Actor = Depends(actor_desde_headers),
    ) -> list[EventoOut]:
        return [
            _evento_out(evento)
            for evento in svc.bloqueos(actor, desde=desde, hasta=hasta)
        ]

    @r.post("/api/calendar/cola/procesar", response_model=ColaOut)
    def procesar_cola(actor: Actor = Depends(actor_desde_headers)) -> ColaOut:
        return _cola_out(svc.procesar_pendientes(actor))

    return r
