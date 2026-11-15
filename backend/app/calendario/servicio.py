"""Casos de uso de C-14: vínculo, push/pull y degradación con Google Calendar.

RN-IN-02: el sistema es fuente de verdad; un evento externo nunca cancela ni
reprograma un turno interno.
RN-IN-03: si GCal falla, la agenda sigue operando y los envíos se reintentan con
backoff hasta agotarse.
"""
from __future__ import annotations

import hmac
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.calendario.puertos import (
    CODIGO_LINK_DUPLICADO,
    CODIGO_LINK_INACTIVO,
    AccionEnvio,
    AuditoriaPort,
    CalendarLink,
    ColaCalendarioPort,
    ConflictoCalendario,
    EnvioCalendario,
    EstadoEnvio,
    EstadoEvento,
    EventoCalendario,
    EventoRepositorio,
    LinkRepositorio,
    PasarelaCalendarioPort,
    PasarelaNoDisponible,
    ResultadoPush,
    TokenRevocado,
    TurnoCalendario,
    TurnosCalendarioPort,
)
from app.turnos.servicio import Actor, Invalido, NoAutenticado, NoEncontrado, Prohibido

_ADMIN = frozenset({"ADMIN"})
_LECTURA = frozenset({"ADMIN", "RECEPCION", "ODONTOLOGO"})
_MAX_INTENTOS = 3
Reloj = Callable[[], datetime]


@dataclass(frozen=True)
class ResultadoCola:
    procesados: int
    pendientes: int
    agotados: int
    token_revocado: bool


class ServicioCalendario:
    def __init__(
        self,
        links: LinkRepositorio,
        eventos: EventoRepositorio,
        cola: ColaCalendarioPort,
        pasarela: PasarelaCalendarioPort,
        turnos: TurnosCalendarioPort,
        auditoria: AuditoriaPort,
        *,
        reloj: Reloj | None = None,
    ) -> None:
        self._links = links
        self._eventos = eventos
        self._cola = cola
        self._pasarela = pasarela
        self._turnos = turnos
        self._auditoria = auditoria
        self._reloj: Reloj = reloj or (lambda: datetime.now(UTC))

    # ------------------------------------------------------------------
    # Vínculo
    # ------------------------------------------------------------------

    def conectar(
        self,
        actor: Actor,
        *,
        profesional_id: str,
        gcal_calendar_id: str,
        oauth_ref: str,
    ) -> CalendarLink:
        self._exigir_config(actor, profesional_id)
        if not gcal_calendar_id.strip() or not oauth_ref.strip():
            raise Invalido("el calendario y la referencia OAuth son obligatorios")
        if self._links.por_profesional(
            tenant_id=actor.tenant_id, profesional_id=profesional_id
        ) is not None:
            raise ConflictoCalendario(
                CODIGO_LINK_DUPLICADO, "el profesional ya tiene un calendario conectado"
            )
        link = self._links.crear(
            tenant_id=actor.tenant_id,
            profesional_id=profesional_id,
            gcal_calendar_id=gcal_calendar_id,
            oauth_ref=oauth_ref,
            ahora=self._reloj(),
        )
        self._auditar(actor, "CALENDARIO_CONECTADO", "calendar_link", link.id)
        return link

    def listar_links(
        self, actor: Actor, *, profesional_id: str | None = None
    ) -> list[CalendarLink]:
        self._exigir_lectura(actor)
        if actor.rol == "ODONTOLOGO" and actor.profesional_id is not None:
            profesional_id = actor.profesional_id
        return self._links.listar(tenant_id=actor.tenant_id, profesional_id=profesional_id)

    def desconectar(self, actor: Actor, *, link_id: str) -> CalendarLink:
        link = self._links.obtener(tenant_id=actor.tenant_id, link_id=link_id)
        if link is None:
            raise NoEncontrado("vínculo de calendario no encontrado")
        self._exigir_dueno(actor, link)
        actualizado = self._links.actualizar_estado(
            tenant_id=actor.tenant_id,
            link_id=link_id,
            estado="DESCONECTADO",
            ahora=self._reloj(),
        )
        self._auditar(actor, "CALENDARIO_DESCONECTADO", "calendar_link", link_id)
        return actualizado

    # ------------------------------------------------------------------
    # Push
    # ------------------------------------------------------------------

    def push_turno(self, *, tenant_id: str, turno: TurnoCalendario) -> ResultadoPush:
        link = self._links.por_profesional(
            tenant_id=tenant_id, profesional_id=turno.profesional_id
        )
        if link is None or link.estado != "CONECTADO":
            return ResultadoPush(estado="SIN_LINK")
        if turno.estado in ("CANCELADO", "REPROGRAMADO"):
            return self._cancelar(link, turno)

        existente = self._eventos.por_turno(
            tenant_id=tenant_id, link_id=link.id, turno_id=turno.turno_id
        )
        try:
            if existente is not None and existente.gcal_event_id is not None:
                self._pasarela.actualizar_evento(
                    calendar_id=link.gcal_calendar_id,
                    event_id=existente.gcal_event_id,
                    inicio=turno.inicio,
                    fin=turno.fin,
                    resumen=turno.resumen,
                )
                gcal_event_id = existente.gcal_event_id
            else:
                gcal_event_id = self._pasarela.crear_evento(
                    calendar_id=link.gcal_calendar_id,
                    turno_id=turno.turno_id,
                    inicio=turno.inicio,
                    fin=turno.fin,
                    resumen=turno.resumen,
                )
        except TokenRevocado:
            return self._degradar(link, turno, existente, "TOKEN_REVOCADO")
        except PasarelaNoDisponible:
            return self._degradar(link, turno, existente, "PENDIENTE")

        evento = self._eventos.upsert(
            tenant_id=tenant_id,
            link_id=link.id,
            turno_id=turno.turno_id,
            gcal_event_id=gcal_event_id,
            origen="SISTEMA",
            estado="SINCRONIZADO",
            inicio=turno.inicio,
            fin=turno.fin,
            resumen=turno.resumen,
            ahora=self._reloj(),
        )
        self._auditar_tenant(tenant_id, "CALENDARIO_PUSH", "evento", evento.id)
        return ResultadoPush(estado="SINCRONIZADO", evento=evento)

    def _cancelar(self, link: CalendarLink, turno: TurnoCalendario) -> ResultadoPush:
        existente = self._eventos.por_turno(
            tenant_id=link.tenant_id, link_id=link.id, turno_id=turno.turno_id
        )
        if existente is None:
            return ResultadoPush(estado="SINCRONIZADO")
        if existente.gcal_event_id is not None:
            try:
                self._pasarela.eliminar_evento(
                    calendar_id=link.gcal_calendar_id, event_id=existente.gcal_event_id
                )
            except TokenRevocado:
                return self._degradar(link, turno, existente, "TOKEN_REVOCADO", accion="DELETE")
            except PasarelaNoDisponible:
                return self._degradar(link, turno, existente, "PENDIENTE", accion="DELETE")
        cancelado = self._eventos.upsert(
            tenant_id=link.tenant_id,
            link_id=link.id,
            turno_id=turno.turno_id,
            gcal_event_id=None,
            origen="SISTEMA",
            estado="CANCELADO",
            inicio=turno.inicio,
            fin=turno.fin,
            resumen=turno.resumen,
            ahora=self._reloj(),
        )
        self._auditar_tenant(link.tenant_id, "CALENDARIO_DELETE", "evento", cancelado.id)
        return ResultadoPush(estado="SINCRONIZADO", evento=cancelado)

    def _degradar(
        self,
        link: CalendarLink,
        turno: TurnoCalendario,
        existente: EventoCalendario | None,
        resultado: str,
        *,
        accion: AccionEnvio = "PUSH",
    ) -> ResultadoPush:
        if resultado == "TOKEN_REVOCADO":
            link = self._links.actualizar_estado(
                tenant_id=link.tenant_id,
                link_id=link.id,
                estado="TOKEN_REVOCADO",
                ahora=self._reloj(),
            )
        evento = self._eventos.upsert(
            tenant_id=link.tenant_id,
            link_id=link.id,
            turno_id=turno.turno_id,
            gcal_event_id=None if existente is None else existente.gcal_event_id,
            origen="SISTEMA",
            estado="PENDIENTE",
            inicio=turno.inicio,
            fin=turno.fin,
            resumen=turno.resumen,
            ahora=self._reloj(),
        )
        self._cola.encolar(
            tenant_id=link.tenant_id,
            link_id=link.id,
            evento_id=evento.id,
            accion=accion,
            ahora=self._reloj(),
        )
        self._auditar_tenant(
            link.tenant_id,
            "CALENDARIO_DEGRADADO",
            "evento",
            evento.id,
            despues={"motivo": resultado, "accion": accion},
        )
        return ResultadoPush(estado="PENDIENTE", evento=evento)

    # ------------------------------------------------------------------
    # Pull / webhook
    # ------------------------------------------------------------------

    def recibir_externo(
        self,
        *,
        link_id: str,
        token: str,
        event_id: str,
        inicio: datetime,
        fin: datetime,
        resumen: str = "Evento externo",
    ) -> EventoCalendario:
        link = self._links.obtener_publico(link_id=link_id)
        if link is None:
            raise NoEncontrado("vínculo de calendario no encontrado")
        if not hmac.compare_digest(token, link.oauth_ref):
            raise NoAutenticado("token de calendario inválido")
        if link.estado != "CONECTADO":
            raise ConflictoCalendario(CODIGO_LINK_INACTIVO, "el calendario no está conectado")
        if fin <= inicio:
            raise Invalido("el evento externo termina antes de empezar")

        solapados = self._turnos.solapados(
            tenant_id=link.tenant_id,
            profesional_id=link.profesional_id,
            inicio=inicio,
            fin=fin,
        )
        estado: EstadoEvento = "CONFLICTO_SISTEMA" if solapados else "BLOQUEADO"
        evento = self._eventos.upsert(
            tenant_id=link.tenant_id,
            link_id=link.id,
            turno_id=None,
            gcal_event_id=event_id,
            origen="EXTERNO",
            estado=estado,
            inicio=inicio,
            fin=fin,
            resumen=resumen,
            ahora=self._reloj(),
        )
        self._auditar_tenant(
            link.tenant_id,
            "CALENDARIO_EXTERNO",
            "evento",
            evento.id,
            despues={"estado": estado, "solapados": len(solapados)},
        )
        return evento

    def bloqueos(
        self, actor: Actor, *, desde: datetime, hasta: datetime
    ) -> list[EventoCalendario]:
        self._exigir_lectura(actor)
        return self._eventos.listar_bloqueos(
            tenant_id=actor.tenant_id, desde=desde, hasta=hasta
        )

    # ------------------------------------------------------------------
    # Cola
    # ------------------------------------------------------------------

    def procesar_pendientes(self, actor: Actor) -> ResultadoCola:
        if actor.rol == "PACIENTE":
            raise NoAutenticado("sesión interna requerida")
        if actor.rol not in _ADMIN:
            raise Prohibido("sólo un administrador procesa la cola del calendario")
        tenant_id = actor.tenant_id
        procesados = agotados = 0
        token_revocado = False
        for envio in self._cola.pendientes(tenant_id=tenant_id):
            link = self._links.obtener(tenant_id=tenant_id, link_id=envio.link_id)
            if link is None or link.estado == "TOKEN_REVOCADO":
                if link is not None and link.estado == "TOKEN_REVOCADO":
                    token_revocado = True
                self._cola.actualizar(
                    tenant_id=tenant_id,
                    envio_id=envio.id,
                    estado="AGOTADO",
                    intentos=envio.intentos,
                    proximo_intento=self._reloj(),
                )
                agotados += 1
                continue
            evento = (
                self._eventos.obtener(tenant_id=tenant_id, evento_id=envio.evento_id)
                if envio.evento_id is not None
                else None
            )
            try:
                self._reintentar(link, envio, evento)
            except TokenRevocado:
                self._links.actualizar_estado(
                    tenant_id=tenant_id,
                    link_id=link.id,
                    estado="TOKEN_REVOCADO",
                    ahora=self._reloj(),
                )
                self._cola.actualizar(
                    tenant_id=tenant_id,
                    envio_id=envio.id,
                    estado="AGOTADO",
                    intentos=envio.intentos,
                    proximo_intento=self._reloj(),
                )
                agotados += 1
                token_revocado = True
                continue
            except PasarelaNoDisponible:
                intentos = envio.intentos + 1
                estado: EstadoEnvio = "AGOTADO" if intentos >= _MAX_INTENTOS else "PENDIENTE"
                proximo = self._reloj() + timedelta(minutes=2 ** (intentos - 1))
                self._cola.actualizar(
                    tenant_id=tenant_id,
                    envio_id=envio.id,
                    estado=estado,
                    intentos=intentos,
                    proximo_intento=proximo,
                )
                if estado == "AGOTADO":
                    agotados += 1
                continue
            self._cola.actualizar(
                tenant_id=tenant_id,
                envio_id=envio.id,
                estado="PROCESADO",
                intentos=envio.intentos,
                proximo_intento=self._reloj(),
            )
            procesados += 1
        pendientes = len(self._cola.pendientes(tenant_id=tenant_id))
        return ResultadoCola(
            procesados=procesados,
            pendientes=pendientes,
            agotados=agotados,
            token_revocado=token_revocado,
        )

    def _reintentar(
        self, link: CalendarLink, envio: EnvioCalendario, evento: EventoCalendario | None
    ) -> None:
        if evento is None:
            return
        if envio.accion == "DELETE":
            if evento.gcal_event_id is not None:
                self._pasarela.eliminar_evento(
                    calendar_id=link.gcal_calendar_id, event_id=evento.gcal_event_id
                )
            self._eventos.upsert(
                tenant_id=link.tenant_id,
                link_id=link.id,
                turno_id=evento.turno_id,
                gcal_event_id=None,
                origen=evento.origen,
                estado="CANCELADO",
                inicio=evento.inicio,
                fin=evento.fin,
                resumen=evento.resumen,
                ahora=self._reloj(),
            )
            return
        if evento.gcal_event_id is not None:
            self._pasarela.actualizar_evento(
                calendar_id=link.gcal_calendar_id,
                event_id=evento.gcal_event_id,
                inicio=evento.inicio,
                fin=evento.fin,
                resumen=evento.resumen,
            )
            gcal_event_id = evento.gcal_event_id
        else:
            gcal_event_id = self._pasarela.crear_evento(
                calendar_id=link.gcal_calendar_id,
                turno_id=evento.turno_id or evento.id,
                inicio=evento.inicio,
                fin=evento.fin,
                resumen=evento.resumen,
            )
        self._eventos.upsert(
            tenant_id=link.tenant_id,
            link_id=link.id,
            turno_id=evento.turno_id,
            gcal_event_id=gcal_event_id,
            origen=evento.origen,
            estado="SINCRONIZADO",
            inicio=evento.inicio,
            fin=evento.fin,
            resumen=evento.resumen,
            ahora=self._reloj(),
        )

    # ------------------------------------------------------------------
    # RBAC / auditoría
    # ------------------------------------------------------------------

    @staticmethod
    def _exigir_config(actor: Actor, profesional_id: str) -> None:
        if actor.rol == "PACIENTE":
            raise NoAutenticado("sesión interna requerida")
        if actor.rol == "ADMIN":
            return
        if actor.rol == "ODONTOLOGO" and actor.profesional_id == profesional_id:
            return
        raise Prohibido("sólo admin o el propio odontólogo conectan el calendario")

    @staticmethod
    def _exigir_lectura(actor: Actor) -> None:
        if actor.rol == "PACIENTE":
            raise NoAutenticado("sesión interna requerida")
        if actor.rol not in _LECTURA:
            raise Prohibido("rol sin permiso para leer el calendario")

    @staticmethod
    def _exigir_dueno(actor: Actor, link: CalendarLink) -> None:
        if actor.rol == "ADMIN":
            return
        if actor.rol == "ODONTOLOGO" and actor.profesional_id == link.profesional_id:
            return
        raise Prohibido("sólo admin o el propio odontólogo desconectan el calendario")

    def _auditar(
        self, actor: Actor, accion: str, entidad: str, entidad_id: str
    ) -> None:
        self._auditar_tenant(actor.tenant_id, accion, entidad, entidad_id, actor=actor.user_id)

    def _auditar_tenant(
        self,
        tenant_id: str,
        accion: str,
        entidad: str,
        entidad_id: str,
        *,
        actor: str = "sistema",
        antes: dict[str, object] | None = None,
        despues: dict[str, object] | None = None,
    ) -> None:
        self._auditoria.registrar(
            tenant_id=tenant_id,
            accion=accion,
            actor=actor,
            entidad=entidad,
            entidad_id=entidad_id,
            antes=antes,
            despues=despues,
        )
