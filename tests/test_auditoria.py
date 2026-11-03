"""Task 4.3 — auditoría append-only: rastro con antes/después, sin PHI en logs."""
from __future__ import annotations

import dataclasses

import pytest
from conftest import P1, P2, PAC1, PREST30, S1, T1, dt

from app.turnos.servicio import Actor, Prohibido, ServicioTurnos


def recep():
    return Actor(tenant_id=T1, rol="RECEPCION", user_id="recep-1")


def test_acciones_dejan_rastro_con_antes_despues():
    svc = ServicioTurnos()
    t = svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
                  prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30)
    svc.sobreturno(recep(), t.id, motivo="urgencia")
    svc.cancelar(recep(), t.id, ahora=dt("2026-10-04", 10))
    t2 = svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id="p2",
                   prestacion_id=PREST30, inicio=dt(hora=11), duracion_min=30)
    svc.reprogramar(recep(), t2.id, nuevo_inicio=dt(hora=15), ahora=dt("2026-10-04", 10))
    acciones = [(e.accion, e.antes, e.despues) for e in svc.auditoria(recep())]
    assert ("SOBRETURNO", "PENDIENTE", "PENDIENTE") in acciones
    assert ("CANCELADO", "PENDIENTE", "CANCELADO") in acciones
    assert ("REPROGRAMADO", "PENDIENTE", "REPROGRAMADO") in acciones


def test_paciente_sin_acceso_y_odontologo_solo_su_agenda():
    svc = ServicioTurnos()
    t = svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
                  prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30)
    svc.cancelar(recep(), t.id, ahora=dt("2026-10-04", 10))
    with pytest.raises(Prohibido):
        svc.auditoria(Actor(tenant_id=T1, rol="PACIENTE", user_id=PAC1))
    odo_otro = Actor(tenant_id=T1, rol="ODONTOLOGO", user_id="odo-2", profesional_id=P2)
    assert svc.auditoria(odo_otro) == []
    odo = Actor(tenant_id=T1, rol="ODONTOLOGO", user_id="odo-1", profesional_id=P1)
    assert len(svc.auditoria(odo)) == 1


def test_entradas_sin_phi_y_sin_borrado():
    svc = ServicioTurnos()
    assert not hasattr(svc, "borrar_auditoria") and not hasattr(svc, "editar_auditoria")
    t = svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
                  prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30)
    svc.sobreturno(recep(), t.id, motivo="urgencia con dolor")
    (e,) = svc.auditoria(recep(), t.id)
    campos = set(dataclasses.asdict(e))
    assert campos == {"turno_id", "tenant_id", "accion", "actor", "motivo",
                      "antes", "despues", "registrado_en"}
    assert "paciente" not in str(campos) and "dni" not in str(campos).lower()
