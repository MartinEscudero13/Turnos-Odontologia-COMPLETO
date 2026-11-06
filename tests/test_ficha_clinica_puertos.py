"""Task 2.1 — puertos (Protocol) y adaptadores en memoria scoped por tenant."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from conftest import T1, T2

from app.ficha_clinica.puertos import (
    AdjuntoMemoria,
    AuditoriaMemoria,
    ConsentimientoMemoria,
    EvolucionMemoria,
    FichaMemoria,
    PacienteMemoria,
    ProfesionalMemoria,
    TurnoMemoria,
)

TZ = timezone(timedelta(hours=-3))


def d3(dia: str = "2026-11-10", hora: int = 10) -> datetime:
    y, m, d = (int(x) for x in dia.split("-"))
    return datetime(y, m, d, hora, 0, tzinfo=TZ)


def test_repositorio_memoria_scoped_por_tenant():
    fichas = FichaMemoria()
    evoluciones = EvolucionMemoria()
    adjuntos = AdjuntoMemoria()
    consentimientos = ConsentimientoMemoria()

    f1 = fichas.crear(tenant_id=T1, paciente_id="paciente-1", ahora=d3())
    ev1 = evoluciones.registrar(
        tenant_id=T1, paciente_id="paciente-1", profesional_id="profesional-1",
        fecha=d3(), texto="evolución demo", ahora=d3(),
    )
    adj1 = adjuntos.registrar(tenant_id=T1, ficha_id=f1.id, tipo="RX", storage_ref="obj/rx-1", ahora=d3())
    consentimientos.registrar(tenant_id=T1, paciente_id="paciente-1", timestamp=d3(), canal="móvil", ahora=d3())

    # T2 no ve ni muta nada de T1 (404/aislamiento).
    assert fichas.por_paciente(tenant_id=T2, paciente_id="paciente-1") is None
    assert fichas.obtener(tenant_id=T2, ficha_id=f1.id) is None
    assert evoluciones.listar(tenant_id=T2, paciente_id="paciente-1") == []
    assert adjuntos.listar(tenant_id=T2, ficha_id=f1.id) == []
    assert consentimientos.firmado(tenant_id=T2, paciente_id="paciente-1") is False
    assert consentimientos.listar(tenant_id=T2, paciente_id="paciente-1") == []

    # T1 sí ve lo propio.
    assert fichas.por_paciente(tenant_id=T1, paciente_id="paciente-1") == f1
    assert evoluciones.listar(tenant_id=T1, paciente_id="paciente-1") == [ev1]
    assert adjuntos.listar(tenant_id=T1, ficha_id=f1.id) == [adj1]
    assert consentimientos.firmado(tenant_id=T1, paciente_id="paciente-1") is True


def test_puertos_de_identidad_y_atiende():
    pacientes = PacienteMemoria([(T1, "paciente-1"), (T1, "paciente-2")])
    profesionales = ProfesionalMemoria([(T1, "profesional-1")])
    turnos = TurnoMemoria([(T1, "profesional-1", "paciente-1")])

    assert pacientes.existe(tenant_id=T1, paciente_id="paciente-1") is True
    assert pacientes.existe(tenant_id=T1, paciente_id="paciente-999") is False
    assert pacientes.existe(tenant_id=T2, paciente_id="paciente-1") is False
    assert profesionales.existe(tenant_id=T1, profesional_id="profesional-1") is True
    assert profesionales.existe(tenant_id=T2, profesional_id="profesional-1") is False
    assert turnos.atiende(tenant_id=T1, profesional_id="profesional-1", paciente_id="paciente-1") is True
    assert turnos.atiende(tenant_id=T1, profesional_id="profesional-1", paciente_id="paciente-2") is False
    assert turnos.atiende(tenant_id=T2, profesional_id="profesional-1", paciente_id="paciente-1") is False


def test_auditoria_memoria_append_only():
    auditoria = AuditoriaMemoria()
    auditoria.registrar(tenant_id=T1, accion="FICHA_CREADA", actor="recep-1", entidad="ficha", entidad_id="ficha-1")
    assert len(auditoria.entradas) == 1
    # No expone métodos de mutación (append-only).
    assert not hasattr(auditoria, "borrar")
    assert not hasattr(auditoria, "actualizar")
    assert not hasattr(auditoria, "eliminar")
