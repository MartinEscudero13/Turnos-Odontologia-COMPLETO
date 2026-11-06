"""Task 9 — auditoría clínica append-only sin PHI."""
from __future__ import annotations

import pytest
from _ficha_clinica_helpers import HarnessClinica, actor, d3
from conftest import P1, T1

from app.ficha_clinica.servicio import ConsentimientoRequerido


def test_mutaciones_auditadas_sin_phi():
    h = HarnessClinica()
    h.seed_paciente("paciente-1")
    h.seed_profesional(P1)
    h.seed_atiende(P1, "paciente-1")
    h.dar_consentimiento("paciente-1")
    h.svc.crear_ficha(actor("RECEPCION"), paciente_id="paciente-1")
    ficha = h.fichas.por_paciente(tenant_id=T1, paciente_id="paciente-1")
    h.svc.registrar_evolucion(
        actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1),
        paciente_id="paciente-1",
        profesional_id=P1,
        fecha=d3(),
        texto="TEXTO CONFIDENCIAL DEL PACIENTE",
    )
    h.svc.registrar_adjunto(
        actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1),
        ficha_id=ficha.id,
        tipo="RX",
        storage_ref="objetos/rx",
    )

    acciones = [e.accion for e in h.auditoria.entradas]
    assert "CONSENTIMIENTO_REGISTRADO" in acciones
    assert "FICHA_CREADA" in acciones
    assert "EVOLUCION_REGISTRADA" in acciones
    assert "ADJUNTO_REGISTRADO" in acciones

    for e in h.auditoria.entradas:
        # RN-AU-02: quién/qué/cuándo/antes/después, sin PHI.
        assert e.actor
        assert e.entidad_id
        payload = str(e.antes) + str(e.despues)
        assert "TEXTO CONFIDENCIAL" not in payload
        assert "Paciente Demo" not in payload
        assert "+5491" not in payload
        assert "telefono" not in payload


def test_auditoria_sin_delete_ni_update():
    h = HarnessClinica()
    h.seed_paciente("paciente-1")
    h.dar_consentimiento("paciente-1")
    # El puerto es append-only: no expone update/delete.
    assert not hasattr(h.auditoria, "borrar")
    assert not hasattr(h.auditoria, "actualizar")
    assert not hasattr(h.auditoria, "eliminar")
    n = len(h.auditoria.entradas)
    h.svc.crear_ficha(actor("RECEPCION"), paciente_id="paciente-1")
    assert len(h.auditoria.entradas) == n + 1


def test_error_no_vuelca_texto_evolucion():
    h = HarnessClinica()
    h.seed_paciente("paciente-1")
    h.seed_profesional(P1)
    h.seed_atiende(P1, "paciente-1")
    with pytest.raises(ConsentimientoRequerido) as exc:
        h.svc.registrar_evolucion(
            actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1),
            paciente_id="paciente-1",
            profesional_id=P1,
            fecha=d3(),
            texto="SECRETO CLINICO NO DEBE APARECER",
        )
    assert "SECRETO CLINICO" not in str(exc.value)
    assert "SECRETO CLINICO" not in exc.value.mensaje
