"""Task 8 — aislamiento multi-tenant de la clínica."""
from __future__ import annotations

import pytest
from _ficha_clinica_helpers import HarnessClinica, actor, d3
from conftest import P1, T1, T2

from app.ficha_clinica.servicio import ConsentimientoRequerido
from app.turnos.servicio import NoEncontrado


def test_operaciones_de_a_no_tocan_b():
    h = HarnessClinica()
    h.seed_paciente("paciente-1", tenant=T1)
    h.seed_profesional(P1, tenant=T1)
    h.seed_atiende(P1, "paciente-1", tenant=T1)
    h.dar_consentimiento("paciente-1", tenant=T1)
    ficha = h.svc.crear_ficha(actor("RECEPCION", tenant=T1), paciente_id="paciente-1")
    h.svc.registrar_evolucion(
        actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1, tenant=T1),
        paciente_id="paciente-1",
        profesional_id=P1,
        fecha=d3(),
        texto="evolución de T1",
    )
    assert ficha.tenant_id == T1
    # T2 no ve la ficha ni las evoluciones de T1.
    with pytest.raises(NoEncontrado):
        h.svc.obtener_ficha(actor("RECEPCION", tenant=T2), paciente_id="paciente-1")
    assert h.svc.listar_evoluciones(actor("RECEPCION", tenant=T2), paciente_id="paciente-1") == []


def test_consentimiento_de_a_no_aplica_en_b():
    h = HarnessClinica()
    h.seed_paciente("paciente-1", tenant=T1)
    h.seed_paciente("paciente-1", tenant=T2)  # mismo id, distinto tenant
    h.dar_consentimiento("paciente-1", tenant=T1)
    assert h.consentimientos.firmado(tenant_id=T2, paciente_id="paciente-1") is False
    with pytest.raises(ConsentimientoRequerido):
        h.svc.crear_ficha(actor("RECEPCION", tenant=T2), paciente_id="paciente-1")


def test_adjunto_de_a_no_listable_en_b():
    h = HarnessClinica()
    h.seed_paciente("paciente-1", tenant=T1)
    h.seed_profesional(P1, tenant=T1)
    h.seed_atiende(P1, "paciente-1", tenant=T1)
    h.dar_consentimiento("paciente-1", tenant=T1)
    h.svc.crear_ficha(actor("RECEPCION", tenant=T1), paciente_id="paciente-1")
    ficha = h.fichas.por_paciente(tenant_id=T1, paciente_id="paciente-1")
    h.svc.registrar_adjunto(
        actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1, tenant=T1),
        ficha_id=ficha.id,
        tipo="RX",
        storage_ref="objetos/x",
    )
    # T2 no lista el adjunto (la ficha no existe en T2 → 404).
    with pytest.raises(NoEncontrado):
        h.svc.listar_adjuntos(actor("RECEPCION", tenant=T2), ficha_id=ficha.id)
