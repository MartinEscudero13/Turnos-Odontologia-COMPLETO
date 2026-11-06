"""Tasks 2.5–2.7 — consentimiento informado (timestamp + canal, append-only)."""
from __future__ import annotations

import pytest
from _ficha_clinica_helpers import HarnessClinica, actor, d3
from conftest import T1

from app.turnos.servicio import Invalido, NoEncontrado


def test_registrar_consentimiento_timestamp_canal():
    h = HarnessClinica()
    h.seed_paciente("paciente-1")
    momento = d3()
    cons = h.svc.registrar_consentimiento(
        actor("RECEPCION"), paciente_id="paciente-1", timestamp=momento, canal="móvil"
    )
    assert cons.timestamp == momento
    assert cons.canal == "móvil"
    assert cons.paciente_id == "paciente-1"
    assert h.consentimientos.firmado(tenant_id=T1, paciente_id="paciente-1") is True


def test_registrar_consentimiento_timestamp_naive_422():
    h = HarnessClinica()
    h.seed_paciente("paciente-1")
    from datetime import datetime as _dt

    with pytest.raises(Invalido):
        h.svc.registrar_consentimiento(
            actor("RECEPCION"),
            paciente_id="paciente-1",
            timestamp=_dt(2026, 11, 10, 10, 0),  # naive
            canal="móvil",
        )
    assert h.consentimientos.total(T1) == 0


def test_registrar_consentimiento_paciente_otro_tenant_404():
    h = HarnessClinica()
    h.seed_paciente("paciente-1", tenant=T1)
    with pytest.raises(NoEncontrado):
        h.svc.registrar_consentimiento(
            actor("RECEPCION"), paciente_id="paciente-999", timestamp=d3(), canal="móvil"
        )
    assert h.consentimientos.total(T1) == 0


def test_refirma_crea_nuevo_registro():
    h = HarnessClinica()
    h.seed_paciente("paciente-1")
    primero = h.svc.registrar_consentimiento(
        actor("RECEPCION"), paciente_id="paciente-1", timestamp=d3(hora=10), canal="móvil"
    )
    segundo = h.svc.registrar_consentimiento(
        actor("RECEPCION"), paciente_id="paciente-1", timestamp=d3(hora=11), canal="móvil"
    )
    # Re-firma = nueva fila, sin editar la primera.
    assert primero.id != segundo.id
    assert h.consentimientos.total(T1) == 2
    lista = h.consentimientos.listar(tenant_id=T1, paciente_id="paciente-1")
    assert [c.timestamp for c in lista] == [d3(hora=10), d3(hora=11)]


def test_consentimiento_append_only():
    h = HarnessClinica()
    h.seed_paciente("paciente-1")
    cons = h.svc.registrar_consentimiento(
        actor("RECEPCION"), paciente_id="paciente-1", timestamp=d3(), canal="móvil"
    )
    # El servicio no expone update/delete; el adaptador tampoco.
    assert not hasattr(h.svc, "actualizar_consentimiento")
    assert not hasattr(h.svc, "eliminar_consentimiento")
    assert not hasattr(h.consentimientos, "actualizar")
    assert not hasattr(h.consentimientos, "eliminar")
    # El registro original permanece intacto.
    assert h.consentimientos.listar(tenant_id=T1, paciente_id="paciente-1") == [cons]
    assert h.consentimientos.total(T1) == 1
