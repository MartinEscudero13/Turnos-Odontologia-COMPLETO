"""Tasks 2.2–2.4 y 6.1–6.5 — dominio de ficha clínica (ficha 1—1 + RBAC clínico)."""
from __future__ import annotations

import pytest
from _ficha_clinica_helpers import HarnessClinica, actor, d3
from conftest import P1, T1

from app.ficha_clinica.servicio import Conflicto
from app.turnos.servicio import NoEncontrado, Prohibido


def test_crear_ficha_ligada_1_a_1():
    h = HarnessClinica()
    h.seed_paciente("paciente-1")
    h.dar_consentimiento("paciente-1")
    ficha = h.svc.crear_ficha(actor("RECEPCION"), paciente_id="paciente-1", ahora=d3())
    assert ficha.paciente_id == "paciente-1"
    assert ficha.tenant_id == T1
    assert ficha.creado_en == d3()
    assert h.fichas.por_paciente(tenant_id=T1, paciente_id="paciente-1") == ficha


def test_segunda_ficha_responde_409():
    h = HarnessClinica()
    h.seed_paciente("paciente-1")
    h.dar_consentimiento("paciente-1")
    h.svc.crear_ficha(actor("RECEPCION"), paciente_id="paciente-1")
    with pytest.raises(Conflicto):
        h.svc.crear_ficha(actor("RECEPCION"), paciente_id="paciente-1")
    assert h.fichas.total(T1) == 1


def test_ficha_paciente_otro_tenant_responde_404():
    h = HarnessClinica()
    h.seed_paciente("paciente-1", tenant=T1)
    h.seed_paciente("paciente-2", tenant=T1)
    h.dar_consentimiento("paciente-1")
    # paciente ajeno a T1 (no sembrado) → 404
    with pytest.raises(NoEncontrado):
        h.svc.crear_ficha(actor("RECEPCION"), paciente_id="paciente-999")
    with pytest.raises(NoEncontrado):
        h.svc.obtener_ficha(actor("RECEPCION"), paciente_id="paciente-999")
    assert h.fichas.total(T1) == 0


def test_odontologo_escribe_paciente_que_atiende():
    h = HarnessClinica()
    h.seed_paciente("paciente-1")
    h.seed_profesional(P1)
    h.seed_atiende(P1, "paciente-1")
    h.dar_consentimiento("paciente-1")
    ev = h.svc.registrar_evolucion(
        actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1),
        paciente_id="paciente-1",
        profesional_id=P1,
        fecha=d3(),
        texto="evolución demo",
    )
    assert ev.profesional_id == P1
    assert ev.paciente_id == "paciente-1"
    assert ev.fecha == d3()
    assert ev.texto == "evolución demo"


def test_odontologo_paciente_ajeno_403():
    h = HarnessClinica()
    h.seed_paciente("paciente-1")
    h.seed_paciente("paciente-2")
    h.seed_profesional(P1)
    h.seed_atiende(P1, "paciente-1")  # P1 NO atiende a paciente-2
    h.dar_consentimiento("paciente-2")
    with pytest.raises(Prohibido):
        h.svc.registrar_evolucion(
            actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1),
            paciente_id="paciente-2",
            profesional_id=P1,
            fecha=d3(),
            texto="evolución demo",
        )


def test_recepcion_no_registra_evolucion():
    h = HarnessClinica()
    h.seed_paciente("paciente-1")
    h.seed_profesional(P1)
    h.dar_consentimiento("paciente-1")
    with pytest.raises(Prohibido):
        h.svc.registrar_evolucion(
            actor("RECEPCION"),
            paciente_id="paciente-1",
            profesional_id=P1,
            fecha=d3(),
            texto="evolución demo",
        )


def test_paciente_lee_su_ficha_no_la_ajena():
    h = HarnessClinica()
    for p in ("paciente-1", "paciente-2"):
        h.seed_paciente(p)
        h.dar_consentimiento(p)
        h.svc.crear_ficha(actor("RECEPCION"), paciente_id=p)
    propia = h.svc.obtener_ficha(actor("PACIENTE", user_id="paciente-1"), paciente_id="paciente-1")
    assert propia.paciente_id == "paciente-1"
    with pytest.raises(NoEncontrado):
        h.svc.obtener_ficha(actor("PACIENTE", user_id="paciente-1"), paciente_id="paciente-2")


def test_paciente_lee_su_evolucion_adjunto_no_los_ajenos():
    h = HarnessClinica()
    h.seed_profesional(P1)
    for p in ("paciente-1", "paciente-2"):
        h.seed_paciente(p)
        h.seed_atiende(P1, p)
        h.dar_consentimiento(p)
        h.svc.crear_ficha(actor("RECEPCION"), paciente_id=p)
    odonto = actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1)
    ev1 = h.svc.registrar_evolucion(
        odonto, paciente_id="paciente-1", profesional_id=P1, fecha=d3(), texto="a"
    )
    f1 = h.fichas.por_paciente(tenant_id=T1, paciente_id="paciente-1")
    adj1 = h.svc.registrar_adjunto(odonto, ficha_id=f1.id, tipo="RX", storage_ref="obj/a")

    paciente = actor("PACIENTE", user_id="paciente-1")
    assert h.svc.listar_evoluciones(paciente, paciente_id="paciente-1") == [ev1]
    assert h.svc.listar_adjuntos(paciente, ficha_id=f1.id) == [adj1]

    f2 = h.fichas.por_paciente(tenant_id=T1, paciente_id="paciente-2")
    with pytest.raises(NoEncontrado):
        h.svc.listar_evoluciones(paciente, paciente_id="paciente-2")
    with pytest.raises(NoEncontrado):
        h.svc.listar_adjuntos(paciente, ficha_id=f2.id)


def test_recepcion_crea_ficha_y_consentimiento():
    h = HarnessClinica()
    h.seed_paciente("paciente-1")
    cons = h.svc.registrar_consentimiento(
        actor("RECEPCION"), paciente_id="paciente-1", timestamp=d3(), canal="móvil"
    )
    assert cons.timestamp == d3()
    assert cons.canal == "móvil"
    ficha = h.svc.crear_ficha(actor("RECEPCION"), paciente_id="paciente-1")
    assert ficha.paciente_id == "paciente-1"
