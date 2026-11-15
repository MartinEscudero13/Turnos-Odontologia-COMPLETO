"""Puertos y adaptadores en memoria de C-14 (Google Calendar).

El dominio no conoce OAuth ni HTTP: recibe un repositorio de links, uno de
eventos, una cola de envíos y una pasarela. El adaptador fake permite probar
push, conflictos, revocación y backoff sin red.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal, Protocol

from app.turnos.servicio import TurnoError

EstadoLink = Literal["CONECTADO", "DESCONECTADO", "TOKEN_REVOCADO"]
OrigenEvento = Literal["SISTEMA", "EXTERNO"]
EstadoEvento = Literal["PENDIENTE", "SINCRONIZADO", "BLOQUEADO", "CONFLICTO_SISTEMA", "CANCELADO"]
AccionEnvio = Literal["PUSH", "DELETE"]
EstadoEnvio = Literal["PENDIENTE", "PROCESADO", "AGOTADO"]

Reloj = Callable[[], datetime]

CODIGO_LINK_DUPLICADO = "LINK_DUPLICADO"
CODIGO_LINK_INACTIVO = "LINK_INACTIVO"

__all__ = [
    "CODIGO_LINK_DUPLICADO",
    "CODIGO_LINK_INACTIVO",
    "AccionEnvio",
    "AuditoriaMemoria",
    "AuditoriaPort",
    "CalendarLink",
    "ColaCalendarioMemoria",
    "ColaCalendarioPort",
    "ConflictoCalendario",
    "EnvioCalendario",
    "EstadoEnvio",
    "EstadoEvento",
    "EstadoLink",
    "EventoCalendario",
    "EventoMemoria",
    "LinkMemoria",
    "LinkRepositorio",
    "OrigenEvento",
    "PasarelaCalendarioPort",
    "PasarelaNoDisponible",
    "PasarelaGoogleFake",
    "TokenRevocado",
    "TurnoCalendario",
    "TurnosCalendarioMemoria",
    "TurnosCalendarioPort",
]


class ConflictoCalendario(TurnoError):
    """`409` de calendario con código de dominio."""

    codigo = 409

    def __init__(self, codigo_dominio: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.codigo_dominio: str = codigo_dominio


class PasarelaNoDisponible(Exception):
    """Google Calendar no responde: se reintenta con backoff (RN-IN-03)."""


class TokenRevocado(Exception):
    """El OAuth del profesional ya no es válido."""


# ---------------------------------------------------------------------------
# Entidades
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CalendarLink:
    id: str
    tenant_id: str
    profesional_id: str
    gcal_calendar_id: str
    oauth_ref: str
    estado: EstadoLink
    ultima_sync: datetime | None
    creado_en: datetime


@dataclass(frozen=True)
class EventoCalendario:
    id: str
    tenant_id: str
    link_id: str
    turno_id: str | None
    gcal_event_id: str | None
    origen: OrigenEvento
    estado: EstadoEvento
    inicio: datetime
    fin: datetime
    resumen: str
    creado_en: datetime


@dataclass(frozen=True)
class EnvioCalendario:
    id: str
    tenant_id: str
    link_id: str
    evento_id: str | None
    accion: AccionEnvio
    intentos: int
    proximo_intento: datetime
    estado: EstadoEnvio
    creado_en: datetime


@dataclass(frozen=True)
class TurnoCalendario:
    turno_id: str
    profesional_id: str
    inicio: datetime
    fin: datetime
    estado: str
    resumen: str = "Turno"


@dataclass(frozen=True)
class ResultadoPush:
    estado: Literal["SIN_LINK", "SINCRONIZADO", "PENDIENTE"]
    evento: EventoCalendario | None = None


# ---------------------------------------------------------------------------
# Puertos
# ---------------------------------------------------------------------------


class LinkRepositorio(Protocol):
    def crear(
        self,
        *,
        tenant_id: str,
        profesional_id: str,
        gcal_calendar_id: str,
        oauth_ref: str,
        ahora: datetime,
    ) -> CalendarLink: ...

    def obtener(self, *, tenant_id: str, link_id: str) -> CalendarLink | None: ...

    def obtener_publico(self, *, link_id: str) -> CalendarLink | None: ...

    def por_profesional(self, *, tenant_id: str, profesional_id: str) -> CalendarLink | None: ...

    def listar(self, *, tenant_id: str, profesional_id: str | None = None) -> list[CalendarLink]: ...

    def actualizar_estado(
        self, *, tenant_id: str, link_id: str, estado: EstadoLink, ahora: datetime
    ) -> CalendarLink: ...


class EventoRepositorio(Protocol):
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
    ) -> EventoCalendario: ...

    def por_turno(self, *, tenant_id: str, link_id: str, turno_id: str) -> EventoCalendario | None: ...

    def por_gcal(
        self, *, tenant_id: str, link_id: str, gcal_event_id: str
    ) -> EventoCalendario | None: ...

    def obtener(self, *, tenant_id: str, evento_id: str) -> EventoCalendario | None: ...

    def listar_bloqueos(
        self, *, tenant_id: str, desde: datetime, hasta: datetime
    ) -> list[EventoCalendario]: ...


class ColaCalendarioPort(Protocol):
    def encolar(
        self,
        *,
        tenant_id: str,
        link_id: str,
        evento_id: str | None,
        accion: AccionEnvio,
        ahora: datetime,
    ) -> EnvioCalendario: ...

    def pendientes(self, *, tenant_id: str) -> list[EnvioCalendario]: ...

    def actualizar(
        self,
        *,
        tenant_id: str,
        envio_id: str,
        estado: EstadoEnvio,
        intentos: int,
        proximo_intento: datetime,
    ) -> EnvioCalendario: ...


class PasarelaCalendarioPort(Protocol):
    def crear_evento(
        self, *, calendar_id: str, turno_id: str, inicio: datetime, fin: datetime, resumen: str
    ) -> str: ...

    def actualizar_evento(
        self, *, calendar_id: str, event_id: str, inicio: datetime, fin: datetime, resumen: str
    ) -> None: ...

    def eliminar_evento(self, *, calendar_id: str, event_id: str) -> None: ...


class TurnosCalendarioPort(Protocol):
    def solapados(
        self, *, tenant_id: str, profesional_id: str, inicio: datetime, fin: datetime
    ) -> list[str]: ...


class AuditoriaPort(Protocol):
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
    ) -> None: ...


# ---------------------------------------------------------------------------
# Adaptadores en memoria
# ---------------------------------------------------------------------------


class LinkMemoria:
    def __init__(self) -> None:
        self._items: dict[str, CalendarLink] = {}
        self._secuencia = 0

    def crear(
        self,
        *,
        tenant_id: str,
        profesional_id: str,
        gcal_calendar_id: str,
        oauth_ref: str,
        ahora: datetime,
    ) -> CalendarLink:
        if self.por_profesional(tenant_id=tenant_id, profesional_id=profesional_id) is not None:
            raise ConflictoCalendario(CODIGO_LINK_DUPLICADO, "el profesional ya tiene un calendario")
        self._secuencia += 1
        link = CalendarLink(
            id=f"link-{self._secuencia}",
            tenant_id=tenant_id,
            profesional_id=profesional_id,
            gcal_calendar_id=gcal_calendar_id,
            oauth_ref=oauth_ref,
            estado="CONECTADO",
            ultima_sync=ahora,
            creado_en=ahora,
        )
        self._items[link.id] = link
        return link

    def obtener(self, *, tenant_id: str, link_id: str) -> CalendarLink | None:
        link = self._items.get(link_id)
        return link if link is not None and link.tenant_id == tenant_id else None

    def obtener_publico(self, *, link_id: str) -> CalendarLink | None:
        return self._items.get(link_id)

    def por_profesional(self, *, tenant_id: str, profesional_id: str) -> CalendarLink | None:
        for link in self._items.values():
            if link.tenant_id == tenant_id and link.profesional_id == profesional_id:
                return link
        return None

    def listar(self, *, tenant_id: str, profesional_id: str | None = None) -> list[CalendarLink]:
        return [
            link
            for link in self._items.values()
            if link.tenant_id == tenant_id
            and (profesional_id is None or link.profesional_id == profesional_id)
        ]

    def actualizar_estado(
        self, *, tenant_id: str, link_id: str, estado: EstadoLink, ahora: datetime
    ) -> CalendarLink:
        link = self.obtener(tenant_id=tenant_id, link_id=link_id)
        if link is None:
            raise KeyError(link_id)
        actualizado = replace(link, estado=estado, ultima_sync=ahora)
        self._items[link_id] = actualizado
        return actualizado


class EventoMemoria:
    def __init__(self) -> None:
        self._items: dict[str, EventoCalendario] = {}
        self._secuencia = 0

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
        existente = (
            self.por_turno(tenant_id=tenant_id, link_id=link_id, turno_id=turno_id)
            if turno_id is not None
            else None
        )
        if existente is None and gcal_event_id is not None:
            existente = self.por_gcal(
                tenant_id=tenant_id, link_id=link_id, gcal_event_id=gcal_event_id
            )
        if existente is not None:
            actualizado = replace(
                existente,
                gcal_event_id=gcal_event_id,
                estado=estado,
                inicio=inicio,
                fin=fin,
                resumen=resumen,
            )
            self._items[existente.id] = actualizado
            return actualizado
        self._secuencia += 1
        evento = EventoCalendario(
            id=f"evento-{self._secuencia}",
            tenant_id=tenant_id,
            link_id=link_id,
            turno_id=turno_id,
            gcal_event_id=gcal_event_id,
            origen=origen,
            estado=estado,
            inicio=inicio,
            fin=fin,
            resumen=resumen,
            creado_en=ahora,
        )
        self._items[evento.id] = evento
        return evento

    def por_turno(self, *, tenant_id: str, link_id: str, turno_id: str) -> EventoCalendario | None:
        for evento in self._items.values():
            if (
                evento.tenant_id == tenant_id
                and evento.link_id == link_id
                and evento.turno_id == turno_id
            ):
                return evento
        return None

    def por_gcal(
        self, *, tenant_id: str, link_id: str, gcal_event_id: str
    ) -> EventoCalendario | None:
        for evento in self._items.values():
            if (
                evento.tenant_id == tenant_id
                and evento.link_id == link_id
                and evento.gcal_event_id == gcal_event_id
            ):
                return evento
        return None

    def obtener(self, *, tenant_id: str, evento_id: str) -> EventoCalendario | None:
        evento = self._items.get(evento_id)
        return evento if evento is not None and evento.tenant_id == tenant_id else None

    def listar_bloqueos(
        self, *, tenant_id: str, desde: datetime, hasta: datetime
    ) -> list[EventoCalendario]:
        return sorted(
            (
                evento
                for evento in self._items.values()
                if evento.tenant_id == tenant_id
                and evento.origen == "EXTERNO"
                and evento.estado in ("BLOQUEADO", "CONFLICTO_SISTEMA")
                and evento.inicio < hasta
                and evento.fin > desde
            ),
            key=lambda evento: evento.inicio,
        )


class ColaCalendarioMemoria:
    def __init__(self) -> None:
        self._items: dict[str, EnvioCalendario] = {}
        self._secuencia = 0

    def encolar(
        self,
        *,
        tenant_id: str,
        link_id: str,
        evento_id: str | None,
        accion: AccionEnvio,
        ahora: datetime,
    ) -> EnvioCalendario:
        self._secuencia += 1
        envio = EnvioCalendario(
            id=f"envio-{self._secuencia}",
            tenant_id=tenant_id,
            link_id=link_id,
            evento_id=evento_id,
            accion=accion,
            intentos=0,
            proximo_intento=ahora,
            estado="PENDIENTE",
            creado_en=ahora,
        )
        self._items[envio.id] = envio
        return envio

    def pendientes(self, *, tenant_id: str) -> list[EnvioCalendario]:
        return sorted(
            (
                envio
                for envio in self._items.values()
                if envio.tenant_id == tenant_id and envio.estado == "PENDIENTE"
            ),
            key=lambda envio: envio.proximo_intento,
        )

    def actualizar(
        self,
        *,
        tenant_id: str,
        envio_id: str,
        estado: EstadoEnvio,
        intentos: int,
        proximo_intento: datetime,
    ) -> EnvioCalendario:
        envio = self._items.get(envio_id)
        if envio is None or envio.tenant_id != tenant_id:
            raise KeyError(envio_id)
        actualizado = replace(
            envio, estado=estado, intentos=intentos, proximo_intento=proximo_intento
        )
        self._items[envio_id] = actualizado
        return actualizado


class TurnosCalendarioMemoria:
    def __init__(self) -> None:
        self._turnos: list[tuple[str, TurnoCalendario]] = []

    def agregar(self, tenant_id: str, turno: TurnoCalendario) -> None:
        self._turnos.append((tenant_id, turno))

    def solapados(
        self, *, tenant_id: str, profesional_id: str, inicio: datetime, fin: datetime
    ) -> list[str]:
        return [
            turno.turno_id
            for dueno, turno in self._turnos
            if dueno == tenant_id
            and turno.profesional_id == profesional_id
            and turno.inicio < fin
            and turno.fin > inicio
            and turno.estado not in ("CANCELADO", "REPROGRAMADO")
        ]


class PasarelaGoogleFake:
    """Pasarela en memoria: `fallar=True` simula GCal caído y `revocado=True` OAuth vencido."""

    def __init__(self) -> None:
        self.eventos: dict[str, dict[str, object]] = {}
        self.fallar = False
        self.revocado = False
        self._secuencia = 0

    def _exigir_disponible(self) -> None:
        if self.revocado:
            raise TokenRevocado("token revocado")
        if self.fallar:
            raise PasarelaNoDisponible("google calendar no disponible")

    def crear_evento(
        self, *, calendar_id: str, turno_id: str, inicio: datetime, fin: datetime, resumen: str
    ) -> str:
        self._exigir_disponible()
        self._secuencia += 1
        event_id = f"gcal-{self._secuencia}"
        self.eventos[event_id] = {
            "calendar_id": calendar_id,
            "turno_id": turno_id,
            "inicio": inicio,
            "fin": fin,
            "resumen": resumen,
        }
        return event_id

    def actualizar_evento(
        self, *, calendar_id: str, event_id: str, inicio: datetime, fin: datetime, resumen: str
    ) -> None:
        self._exigir_disponible()
        self.eventos[event_id] = {
            **self.eventos.get(event_id, {}),
            "calendar_id": calendar_id,
            "inicio": inicio,
            "fin": fin,
            "resumen": resumen,
        }

    def eliminar_evento(self, *, calendar_id: str, event_id: str) -> None:
        del calendar_id  # el fake no modela calendarios múltiples
        self._exigir_disponible()
        self.eventos.pop(event_id, None)


class AuditoriaMemoria:
    def __init__(self) -> None:
        self.entradas: list[dict[str, object]] = []

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
        self.entradas.append(
            {
                "tenant_id": tenant_id,
                "accion": accion,
                "actor": actor,
                "entidad": entidad,
                "entidad_id": entidad_id,
                "antes": antes,
                "despues": despues,
            }
        )
