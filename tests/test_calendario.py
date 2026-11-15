"""Tests de dominio de C-14 con adaptadores en memoria (sin DB ni red)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from app.calendario.puertos import (
    CODIGO_LINK_DUPLICADO,
    AuditoriaMemoria,
    ColaCalendarioMemoria,
    ConflictoCalendario,
    EventoMemoria,
    LinkMemoria,
    PasarelaGoogleFake,
    TurnoCalendario,
    TurnosCalendarioMemoria,
)
from app.calendario.servicio import ServicioCalendario
from app.turnos.servicio import Actor, NoAutenticado, NoEncontrado, Prohibido

TZ = timezone(timedelta(hours=-3))
AHORA = datetime(2026, 11, 15, 9, 0, tzinfo=TZ)
T1 = "a0000000-0000-4000-8000-000000000001"
T2 = "a0000000-0000-4000-8000-000000000002"
PRO1 = "profesional-1"
PRO2 = "profesional-2"
INICIO = datetime(2026, 11, 20, 10, 0, tzinfo=TZ)
FIN = INICIO + timedelta(minutes=30)


def actor(rol: str = "ADMIN", tenant: str = T1, profesional_id: str | None = None) -> Actor:
    return Actor(tenant_id=tenant, rol=rol, user_id="usuario-1", profesional_id=profesional_id)


@dataclass
class Harness:
    svc: ServicioCalendario
    links: LinkMemoria
    eventos: EventoMemoria
    cola: ColaCalendarioMemoria
    pasarela: PasarelaGoogleFake
    turnos: TurnosCalendarioMemoria
    auditoria: AuditoriaMemoria


def nuevo_harness() -> Harness:
    links = LinkMemoria()
    eventos = EventoMemoria()
    cola = ColaCalendarioMemoria()
    pasarela = PasarelaGoogleFake()
    turnos = TurnosCalendarioMemoria()
    auditoria = AuditoriaMemoria()
    svc = ServicioCalendario(
        links, eventos, cola, pasarela, turnos, auditoria, reloj=lambda: AHORA
    )
    return Harness(svc, links, eventos, cola, pasarela, turnos, auditoria)


def conectar(h: Harness, profesional_id: str = PRO1) -> str:
    link = h.svc.conectar(
        actor(), profesional_id=profesional_id, gcal_calendar_id="cal@test", oauth_ref="ref-1"
    )
    return link.id


def turno(
    *, turno_id: str = "turno-1", estado: str = "PENDIENTE", inicio: datetime = INICIO
) -> TurnoCalendario:
    return TurnoCalendario(
        turno_id=turno_id,
        profesional_id=PRO1,
        inicio=inicio,
        fin=inicio + timedelta(minutes=30),
        estado=estado,
        resumen="Turno demo",
    )


# ---------------------------------------------------------------------------
# Vínculo
# ---------------------------------------------------------------------------


def test_conectar_y_listar_link() -> None:
    h = nuevo_harness()

    link = h.svc.conectar(
        actor(), profesional_id=PRO1, gcal_calendar_id="cal@test", oauth_ref="ref-1"
    )

    assert link.estado == "CONECTADO"
    assert [item.id for item in h.svc.listar_links(actor())] == [link.id]
    assert [e["accion"] for e in h.auditoria.entradas] == ["CALENDARIO_CONECTADO"]


def test_link_duplicado_es_conflicto() -> None:
    h = nuevo_harness()
    conectar(h)

    with pytest.raises(ConflictoCalendario) as excinfo:
        h.svc.conectar(
            actor(), profesional_id=PRO1, gcal_calendar_id="otro@test", oauth_ref="ref-2"
        )

    assert excinfo.value.codigo_dominio == CODIGO_LINK_DUPLICADO
    assert len(h.svc.listar_links(actor())) == 1


def test_odontologo_solo_conecta_su_calendario() -> None:
    h = nuevo_harness()

    with pytest.raises(Prohibido):
        h.svc.conectar(
            actor("ODONTOLOGO", profesional_id=PRO2),
            profesional_id=PRO1,
            gcal_calendar_id="cal@test",
            oauth_ref="ref-1",
        )

    link = h.svc.conectar(
        actor("ODONTOLOGO", profesional_id=PRO2),
        profesional_id=PRO2,
        gcal_calendar_id="cal2@test",
        oauth_ref="ref-2",
    )
    assert link.profesional_id == PRO2


def test_desconectar_cambia_estado() -> None:
    h = nuevo_harness()
    link_id = conectar(h)

    link = h.svc.desconectar(actor(), link_id=link_id)

    assert link.estado == "DESCONECTADO"
    assert h.svc.push_turno(tenant_id=T1, turno=turno()).estado == "SIN_LINK"


# ---------------------------------------------------------------------------
# Push
# ---------------------------------------------------------------------------


def test_push_crea_evento_y_audita() -> None:
    h = nuevo_harness()
    conectar(h)

    resultado = h.svc.push_turno(tenant_id=T1, turno=turno())

    assert resultado.estado == "SINCRONIZADO"
    assert resultado.evento is not None
    assert resultado.evento.estado == "SINCRONIZADO"
    assert len(h.pasarela.eventos) == 1
    assert "CALENDARIO_PUSH" in [e["accion"] for e in h.auditoria.entradas]


def test_push_es_idempotente_por_turno() -> None:
    h = nuevo_harness()
    conectar(h)

    primero = h.svc.push_turno(tenant_id=T1, turno=turno())
    segundo = h.svc.push_turno(
        tenant_id=T1, turno=turno(inicio=INICIO + timedelta(hours=1))
    )

    assert primero.evento is not None and segundo.evento is not None
    assert primero.evento.gcal_event_id == segundo.evento.gcal_event_id
    assert len(h.pasarela.eventos) == 1
    assert segundo.evento.inicio == INICIO + timedelta(hours=1)


def test_push_sin_link_es_no_op() -> None:
    h = nuevo_harness()

    resultado = h.svc.push_turno(tenant_id=T1, turno=turno())

    assert resultado.estado == "SIN_LINK"
    assert h.pasarela.eventos == {}


def test_cancelacion_elimina_el_evento() -> None:
    h = nuevo_harness()
    conectar(h)
    h.svc.push_turno(tenant_id=T1, turno=turno())

    resultado = h.svc.push_turno(tenant_id=T1, turno=turno(estado="CANCELADO"))

    assert resultado.estado == "SINCRONIZADO"
    assert h.pasarela.eventos == {}
    assert resultado.evento is not None and resultado.evento.estado == "CANCELADO"


# ---------------------------------------------------------------------------
# Degradación
# ---------------------------------------------------------------------------


def test_pasarela_caida_encola_sin_romper_agenda() -> None:
    h = nuevo_harness()
    conectar(h)
    h.pasarela.fallar = True

    resultado = h.svc.push_turno(tenant_id=T1, turno=turno())

    assert resultado.estado == "PENDIENTE"
    assert resultado.evento is not None and resultado.evento.estado == "PENDIENTE"
    assert len(h.cola.pendientes(tenant_id=T1)) == 1
    assert h.pasarela.eventos == {}


def test_reintento_exitoso_procesa_la_cola() -> None:
    h = nuevo_harness()
    conectar(h)
    h.pasarela.fallar = True
    h.svc.push_turno(tenant_id=T1, turno=turno())
    h.pasarela.fallar = False

    resultado = h.svc.procesar_pendientes(actor())

    assert resultado.procesados == 1
    assert resultado.pendientes == 0
    assert len(h.pasarela.eventos) == 1
    assert [evento.estado for evento in h.eventos._items.values()] == ["SINCRONIZADO"]


def test_reintentos_agotados() -> None:
    h = nuevo_harness()
    conectar(h)
    h.pasarela.fallar = True
    h.svc.push_turno(tenant_id=T1, turno=turno())

    for _ in range(3):
        resultado = h.svc.procesar_pendientes(actor())

    assert resultado.pendientes == 0
    assert resultado.agotados == 1
    assert [envio.estado for envio in h.cola._items.values()] == ["AGOTADO"]


def test_token_revocado_marca_link_y_conserva_envio() -> None:
    h = nuevo_harness()
    link_id = conectar(h)
    h.pasarela.revocado = True

    resultado = h.svc.push_turno(tenant_id=T1, turno=turno())

    assert resultado.estado == "PENDIENTE"
    assert h.links.obtener(tenant_id=T1, link_id=link_id).estado == "TOKEN_REVOCADO"

    procesado = h.svc.procesar_pendientes(actor())
    assert procesado.token_revocado is True
    assert procesado.agotados == 1


# ---------------------------------------------------------------------------
# Eventos externos
# ---------------------------------------------------------------------------


def test_evento_externo_sin_solape_es_bloqueo() -> None:
    h = nuevo_harness()
    link_id = conectar(h)
    inicio = INICIO + timedelta(days=1)

    evento = h.svc.recibir_externo(
        link_id=link_id,
        token="ref-1",
        event_id="gcal-externo-1",
        inicio=inicio,
        fin=inicio + timedelta(minutes=30),
        resumen="Reunión externa",
    )

    assert evento.estado == "BLOQUEADO"
    bloqueos = h.svc.bloqueos(actor(), desde=inicio - timedelta(days=1), hasta=inicio + timedelta(days=1))
    assert [b.id for b in bloqueos] == [evento.id]


def test_evento_externo_con_solape_gana_el_sistema() -> None:
    h = nuevo_harness()
    link_id = conectar(h)
    h.turnos.agregar(T1, turno(turno_id="turno-interno"))

    evento = h.svc.recibir_externo(
        link_id=link_id,
        token="ref-1",
        event_id="gcal-externo-2",
        inicio=INICIO + timedelta(minutes=10),
        fin=INICIO + timedelta(minutes=40),
    )

    assert evento.estado == "CONFLICTO_SISTEMA"
    assert h.turnos.solapados(
        tenant_id=T1, profesional_id=PRO1, inicio=INICIO, fin=FIN
    ) == ["turno-interno"]


def test_token_de_webhook_invalido() -> None:
    h = nuevo_harness()
    link_id = conectar(h)

    with pytest.raises(NoAutenticado):
        h.svc.recibir_externo(
            link_id=link_id, token="otro", event_id="gcal-x", inicio=INICIO, fin=FIN
        )

    assert h.eventos._items == {}


def test_link_inexistente_en_webhook() -> None:
    h = nuevo_harness()

    with pytest.raises(NoEncontrado):
        h.svc.recibir_externo(
            link_id="link-fantasma", token="ref-1", event_id="gcal-x", inicio=INICIO, fin=FIN
        )


def test_aislamiento_entre_tenants() -> None:
    h = nuevo_harness()
    conectar(h, PRO1)

    assert h.svc.listar_links(actor(tenant=T2)) == []
    assert h.svc.bloqueos(
        actor(tenant=T2), desde=INICIO, hasta=FIN
    ) == []
