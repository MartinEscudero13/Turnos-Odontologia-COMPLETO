"""Task 3.1 — CRUD ServicioTurnos (fin calculado, tenant-scoped, RBAC): RED primero."""
from __future__ import annotations

from datetime import datetime

import pytest
from conftest import P1, P2, PAC1, PREST30, S1, S2, T1, T2, dt

from app.turnos.servicio import (
    Actor,
    ConflictoSolape,
    Invalido,
    NoEncontrado,
    Prohibido,
    ServicioTurnos,
)


def recep(tenant=T1):
    return Actor(tenant_id=tenant, rol="RECEPCION", user_id="recep-1")


def test_crear_valido_calcula_fin_y_queda_pendiente():
    svc = ServicioTurnos()
    t = svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
                  prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30)
    assert t.estado == "PENDIENTE"
    assert t.fin == dt(hora=10, minuto=30)
    assert t.sobreturno is False


def test_fin_deriva_de_prestacion_y_cliente_distinto_422():
    svc = ServicioTurnos()
    t = svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
                  prestacion_id=PREST30, inicio=dt(hora=9), duracion_min=45)
    assert t.fin == dt(hora=9, minuto=45)
    with pytest.raises(Invalido):
        svc.crear(recep(), profesional_id=P1, sillon_id=S2, paciente_id=PAC1,
                  prestacion_id=PREST30, inicio=dt(hora=11), duracion_min=30,
                  fin_cliente=dt(hora=11, minuto=45))


def test_listar_filtra_por_tenant():
    svc = ServicioTurnos()
    svc.crear(recep(T1), profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
              prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30)
    svc.crear(recep(T2), profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
              prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30)
    assert len(svc.listar(recep(T1))) == 1
    assert len(svc.listar(recep(T2))) == 1


def test_obtener_404_cross_tenant():
    svc = ServicioTurnos()
    t = svc.crear(recep(T1), profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
                  prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30)
    with pytest.raises(NoEncontrado):
        svc.obtener(recep(T2), t.id)


def test_actualizar_solo_paciente_y_final_no_editable():
    svc = ServicioTurnos()
    t = svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
                  prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30)
    upd = svc.actualizar(recep(), t.id, paciente_id="paciente-2")
    assert upd.paciente_id == "paciente-2"
    svc.cancelar(recep(), t.id, ahora=dt("2026-10-01", 10))
    with pytest.raises(Invalido):
        svc.actualizar(recep(), t.id, paciente_id="paciente-3")


def test_paciente_solo_sus_turnos_y_sin_sobreturno():
    svc = ServicioTurnos()
    pac = Actor(tenant_id=T1, rol="PACIENTE", user_id=PAC1)
    t = svc.crear(pac, profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
                  prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30)
    assert t.estado == "PENDIENTE"
    with pytest.raises(Prohibido):
        svc.crear(pac, profesional_id=P1, sillon_id=S1, paciente_id="otro",
                  prestacion_id=PREST30, inicio=dt(hora=11), duracion_min=30)
    with pytest.raises(Prohibido):
        svc.crear(pac, profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
                  prestacion_id=PREST30, inicio=dt(hora=12), duracion_min=30,
                  sobreturno=True, motivo_sobreturno="urgencia")


def test_odontologo_solo_agenda_propia():
    svc = ServicioTurnos()
    odo = Actor(tenant_id=T1, rol="ODONTOLOGO", user_id="odo-1", profesional_id=P1)
    with pytest.raises(Prohibido):
        svc.crear(odo, profesional_id=P2, sillon_id=S1, paciente_id=PAC1,
                  prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30)


def test_inicio_naive_se_rechaza():
    svc = ServicioTurnos()
    naive = datetime(2026, 10, 6, 10, 0)  # sin tz → no es timestamptz
    with pytest.raises(Invalido):
        svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
                  prestacion_id=PREST30, inicio=naive, duracion_min=30)


def test_solape_profesional_409():
    svc = ServicioTurnos()
    svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
              prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30)
    with pytest.raises(ConflictoSolape):
        svc.crear(recep(), profesional_id=P1, sillon_id=S2, paciente_id="p2",
                  prestacion_id=PREST30, inicio=dt(hora=10, minuto=15), duracion_min=30)


def test_adyacencia_exacta_permitida():
    svc = ServicioTurnos()
    svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
              prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30)
    t2 = svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id="p2",
                   prestacion_id=PREST30, inicio=dt(hora=10, minuto=30), duracion_min=30)
    assert t2.estado == "PENDIENTE"


def test_cancelado_no_bloquea():
    svc = ServicioTurnos()
    t = svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
                  prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30)
    svc.cancelar(recep(), t.id, ahora=dt("2026-10-01", 10))
    t2 = svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id="p2",
                   prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30)
    assert t2.estado == "PENDIENTE"


def test_mismo_horario_otro_tenant_no_choca():
    svc = ServicioTurnos()
    svc.crear(recep(T1), profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
              prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30)
    t2 = svc.crear(recep(T2), profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
                   prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30)
    assert t2.estado == "PENDIENTE"


def test_solape_por_sillon_distinto_profesional_409():
    from conftest import P2

    svc = ServicioTurnos()
    svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
              prestacion_id=PREST30, inicio=dt(hora=11), duracion_min=30)
    with pytest.raises(ConflictoSolape):
        svc.crear(recep(), profesional_id=P2, sillon_id=S1, paciente_id="p2",
                  prestacion_id=PREST30, inicio=dt(hora=11, minuto=15), duracion_min=30)


def test_crear_sobreturno_con_motivo_no_choca_pero_marca_flag():
    svc = ServicioTurnos()
    svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
              prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30)
    sobre = svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id="p2",
                      prestacion_id=PREST30, inicio=dt(hora=10, minuto=15),
                      duracion_min=30, sobreturno=True, motivo_sobreturno="urgencia con dolor")
    assert sobre.sobreturno is True
    assert sobre.motivo_sobreturno == "urgencia con dolor"


def test_crear_sobreturno_sin_motivo_422_y_no_persiste():
    svc = ServicioTurnos()
    with pytest.raises(Invalido):
        svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
                  prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30,
                  sobreturno=True, motivo_sobreturno="  ")
    assert svc.listar(recep()) == []
