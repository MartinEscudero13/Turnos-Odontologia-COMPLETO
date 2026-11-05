"""Task 2.1 — contrato del PacientePort (normalización E.164): RED primero."""
from __future__ import annotations

from conftest import T1, T2

from app.reservas.puertos import Paciente, PacienteMemoria


def test_paciente_port_buscar_por_telefono_normaliza_e164():
    port = PacienteMemoria(
        [Paciente(id="p1", tenant_id=T1, nombre="Paciente Demo", telefono="+5491130551234")]
    )
    encontrado = port.buscar_por_telefono(T1, "+54 9 11 3055 1234")
    assert encontrado is not None
    assert encontrado.telefono == "+5491130551234"
    # ya normalizado también resuelve (identidad)
    assert port.buscar_por_telefono(T1, "+5491130551234") is not None
    # otro tenant no lo ve (aislamiento)
    assert port.buscar_por_telefono(T2, "+5491130551234") is None
