"""Task 3.2 — POST sobreturno (motivo obligatorio + auditoría): RED primero."""
from __future__ import annotations

import pytest
from conftest import P1, P2, PAC1, PREST30, S1, T1, dt

from app.turnos.servicio import (
    Actor,
    Invalido,
    Prohibido,
    ServicioTurnos,
)


def recep():
    return Actor(tenant_id=T1, rol="RECEPCION", user_id="recep-1")


def turno_base(svc):
    return svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
                     prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30)


def test_sobreturno_con_motivo_marca_y_audita():
    svc = ServicioTurnos()
    t = turno_base(svc)
    marcado = svc.sobreturno(recep(), t.id, motivo="urgencia con dolor")
    assert marcado.sobreturno is True
    assert marcado.motivo_sobreturno == "urgencia con dolor"
    entradas = svc.auditoria(recep(), t.id)
    assert len(entradas) == 1
    e = entradas[0]
    assert (e.actor, e.motivo, e.antes, e.despues) == ("recep-1", "urgencia con dolor", "PENDIENTE", "PENDIENTE")
    assert e.accion == "SOBRETURNO"


def test_sobreturno_sin_motivo_422_y_no_marca():
    svc = ServicioTurnos()
    t = turno_base(svc)
    with pytest.raises(Invalido):
        svc.sobreturno(recep(), t.id, motivo="   ")
    assert svc.obtener(recep(), t.id).sobreturno is False
    assert svc.auditoria(recep(), t.id) == []


def test_paciente_no_crea_sobreturnos():
    svc = ServicioTurnos()
    t = turno_base(svc)
    pac = Actor(tenant_id=T1, rol="PACIENTE", user_id=PAC1)
    with pytest.raises(Prohibido):
        svc.sobreturno(pac, t.id, motivo="quiero antes")


def test_sobreturno_en_final_422():
    svc = ServicioTurnos()
    t = turno_base(svc)
    svc.cancelar(recep(), t.id, ahora=dt("2026-10-01", 10))
    with pytest.raises(Invalido):
        svc.sobreturno(recep(), t.id, motivo="tarde")


def test_odontologo_agenda_ajena_403():
    svc = ServicioTurnos()
    t = turno_base(svc)
    odo = Actor(tenant_id=T1, rol="ODONTOLOGO", user_id="odo-2", profesional_id=P2)
    with pytest.raises(Prohibido):
        svc.sobreturno(odo, t.id, motivo="lo tomo yo")


def test_turno_marcado_sobreturno_no_bloquea_hueco():
    # El sobreturno existente no cuenta para el anti-solape (predicado EXCLUDE).
    svc = ServicioTurnos()
    t = turno_base(svc)
    svc.sobreturno(recep(), t.id, motivo="urgencia")
    libre = svc.crear(recep(), profesional_id=P1, sillon_id=S1,
                      paciente_id="p9", prestacion_id=PREST30,
                      inicio=dt(hora=10), duracion_min=30)
    assert libre.estado == "PENDIENTE"


def test_motivo_se_preserva_como_fue_dado():
    svc = ServicioTurnos()
    t = turno_base(svc)
    marcado = svc.sobreturno(recep(), t.id, motivo="Urgencia Con Dolor")
    assert marcado.motivo_sobreturno == "Urgencia Con Dolor"
