"""Tasks 5.1–5.3 — gate de consentimiento (bloquea clínica, no agenda)."""
from __future__ import annotations

import pytest
from _ficha_clinica_helpers import HarnessClinica, actor, d3
from conftest import P1, T1

from app.ficha_clinica.servicio import ConsentimientoRequerido


def test_gate_consulta_consentimientos():
    h = HarnessClinica()
    h.seed_paciente("paciente-1")
    h.seed_profesional(P1)
    h.seed_atiende(P1, "paciente-1")
    # Sin fila en `consentimientos` → clínica bloqueada (el boolean C-04 no es fuente).
    with pytest.raises(ConsentimientoRequerido) as exc:
        h.svc.crear_ficha(actor("RECEPCION"), paciente_id="paciente-1")
    assert exc.value.codigo == 409
    # Fila con `timestamp` válido → habilitada.
    h.svc.registrar_consentimiento(
        actor("RECEPCION"), paciente_id="paciente-1", timestamp=d3(), canal="móvil"
    )
    ficha = h.svc.crear_ficha(actor("RECEPCION"), paciente_id="paciente-1")
    assert ficha.paciente_id == "paciente-1"


def test_fila_sin_timestamp_valido_no_desbloquea():
    h = HarnessClinica()
    h.seed_paciente("paciente-1")
    h.seed_profesional(P1)
    h.seed_atiende(P1, "paciente-1")
    # Fila sin timestamp válido (NULL) → no desbloquea.
    h.consentimientos.registrar(tenant_id=T1, paciente_id="paciente-1", timestamp=None, canal="móvil")
    assert h.consentimientos.firmado(tenant_id=T1, paciente_id="paciente-1") is False
    with pytest.raises(ConsentimientoRequerido):
        h.svc.crear_ficha(actor("RECEPCION"), paciente_id="paciente-1")


def test_sin_consentimiento_clinica_bloqueada_409():
    h = HarnessClinica()
    h.seed_paciente("paciente-1")
    h.seed_profesional(P1)
    h.seed_atiende(P1, "paciente-1")
    # ficha
    with pytest.raises(ConsentimientoRequerido):
        h.svc.crear_ficha(actor("RECEPCION"), paciente_id="paciente-1")
    # evolución
    with pytest.raises(ConsentimientoRequerido):
        h.svc.registrar_evolucion(
            actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1),
            paciente_id="paciente-1",
            profesional_id=P1,
            fecha=d3(),
            texto="evolución",
        )
    # adjunto: sembramos la ficha directo para aislar el gate (sin consentimiento).
    ficha = h.fichas.crear(tenant_id=T1, paciente_id="paciente-1")
    with pytest.raises(ConsentimientoRequerido):
        h.svc.registrar_adjunto(
            actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1),
            ficha_id=ficha.id,
            tipo="RX",
            storage_ref="objetos/x",
        )


def test_sin_consentimiento_turno_agenda_201():
    from app.turnos.servicio import ServicioTurnos

    turnos = ServicioTurnos(anticipacion_min_horas=0.0)
    turno = turnos.crear(
        actor("RECEPCION"),
        profesional_id=P1,
        sillon_id="sillon-1",
        paciente_id="paciente-1",
        prestacion_id="prestacion-1",
        inicio=d3(),
        duracion_min=30,
    )
    assert turno.paciente_id == "paciente-1"
    assert turno.estado == "PENDIENTE"
