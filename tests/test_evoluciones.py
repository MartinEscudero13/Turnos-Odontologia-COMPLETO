"""Tasks 3.1–3.4 — evoluciones append-only."""
from __future__ import annotations

import pytest
from _ficha_clinica_helpers import HarnessClinica, actor, d3
from conftest import P1, T1

from app.turnos.servicio import NoEncontrado


def _h_consentido(paciente_id: str = "paciente-1") -> HarnessClinica:
    h = HarnessClinica()
    h.seed_paciente(paciente_id)
    h.seed_profesional(P1)
    h.seed_atiende(P1, paciente_id)
    h.dar_consentimiento(paciente_id)
    return h


def test_evolucion_valida_con_consentimiento():
    h = _h_consentido()
    fecha = d3()
    ev = h.svc.registrar_evolucion(
        actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1),
        paciente_id="paciente-1",
        profesional_id=P1,
        fecha=fecha,
        texto="evolución demo",
        firma_hash="abc123",
    )
    assert ev.profesional_id == P1
    assert ev.fecha == fecha
    assert ev.texto == "evolución demo"
    assert ev.firma_hash == "abc123"
    assert h.evoluciones.listar(tenant_id=T1, paciente_id="paciente-1") == [ev]


def test_corregir_agrega_nueva_evolucion_no_edita_original():
    h = _h_consentido()
    odonto = actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1)
    original = h.svc.registrar_evolucion(
        odonto, paciente_id="paciente-1", profesional_id=P1, fecha=d3(hora=10), texto="texto con error"
    )
    correccion = h.svc.registrar_evolucion(
        odonto, paciente_id="paciente-1", profesional_id=P1, fecha=d3(hora=11), texto="texto corregido"
    )
    # La original permanece intacta y la nueva se agrega al final.
    assert original.texto == "texto con error"
    lista = h.evoluciones.listar(tenant_id=T1, paciente_id="paciente-1")
    assert lista == [original, correccion]
    assert lista[-1].texto == "texto corregido"


def test_servicio_sin_update_delete():
    h = _h_consentido()
    h.svc.registrar_evolucion(
        actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1),
        paciente_id="paciente-1",
        profesional_id=P1,
        fecha=d3(),
        texto="original",
    )
    # No hay endpoints/métodos de mutación; la lista no cambia.
    assert not hasattr(h.svc, "actualizar_evolucion")
    assert not hasattr(h.svc, "eliminar_evolucion")
    assert not hasattr(h.evoluciones, "actualizar")
    assert not hasattr(h.evoluciones, "eliminar")
    assert len(h.evoluciones.listar(tenant_id=T1, paciente_id="paciente-1")) == 1


def test_evolucion_paciente_o_profesional_otro_tenant_404():
    h = HarnessClinica()
    h.seed_paciente("paciente-1", tenant=T1)
    h.seed_profesional(P1, tenant=T1)
    h.dar_consentimiento("paciente-1")
    # profesional ajeno a T1 → 404
    with pytest.raises(NoEncontrado):
        h.svc.registrar_evolucion(
            actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1),
            paciente_id="paciente-1",
            profesional_id="prof-ajeno",
            fecha=d3(),
            texto="x",
        )
    # paciente ajeno a T1 → 404
    with pytest.raises(NoEncontrado):
        h.svc.registrar_evolucion(
            actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1),
            paciente_id="paciente-999",
            profesional_id=P1,
            fecha=d3(),
            texto="x",
        )
    assert len(h.evoluciones.listar(tenant_id=T1, paciente_id="paciente-1")) == 0


def test_evolucion_texto_vacio_422():
    h = _h_consentido()
    from app.turnos.servicio import Invalido

    with pytest.raises(Invalido):
        h.svc.registrar_evolucion(
            actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1),
            paciente_id="paciente-1",
            profesional_id=P1,
            fecha=d3(),
            texto="   ",
        )
