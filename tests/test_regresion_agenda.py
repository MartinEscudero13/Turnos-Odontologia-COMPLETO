"""Task 4.1 — regresión agenda: los 12 escenarios del spec vigente, 1:1.

Cobertura de aceptación sobre el servicio (green-first por construcción;
los RED por módulo ya se observaron en los ciclos 1–8).
"""
from __future__ import annotations

import pytest

from app.turnos.servicio import Actor, ConflictoSolape, Invalido, ServicioTurnos
from conftest import PAC1, P1, PREST30, S1, S2, T1, T2, dt


def recep(tenant=T1):
    return Actor(tenant_id=tenant, rol="RECEPCION", user_id="recep-1")


def crear(svc, inicio, prof=P1, sillon=S1, tenant=T1, dur=30, **kw):
    kw.setdefault("paciente_id", PAC1)
    return svc.crear(recep(tenant), profesional_id=prof, sillon_id=sillon,
                     prestacion_id=PREST30, inicio=inicio,
                     duracion_min=dur, **kw)


def test_01_turno_valido_se_crea_pendiente():
    svc = ServicioTurnos()
    t = crear(svc, dt(hora=10))
    assert (t.estado, t.fin) == ("PENDIENTE", dt(hora=10, minuto=30))


def test_02_fin_derivado_no_ingresado():
    svc = ServicioTurnos()
    t = crear(svc, dt(hora=9), dur=45)
    assert t.fin == dt(hora=9, minuto=45)
    with pytest.raises(Invalido):
        crear(svc, dt(hora=11), sillon=S2, fin_cliente=dt(hora=11, minuto=45))


def test_03_solape_profesional_409_y_no_persiste():
    svc = ServicioTurnos()
    crear(svc, dt(hora=10))
    with pytest.raises(ConflictoSolape) as exc:
        crear(svc, dt(hora=10, minuto=15), sillon=S2, dur=30, paciente_id="p2")
    assert len(exc.value.alternativas) == 3
    assert len(svc.listar(recep())) == 1


def test_04_solape_sillon_409_y_no_persiste():
    from conftest import P2

    svc = ServicioTurnos()
    crear(svc, dt(hora=11))
    with pytest.raises(ConflictoSolape) as exc:
        crear(svc, dt(hora=11, minuto=15), prof=P2, paciente_id="p2")
    assert len(exc.value.alternativas) == 3
    assert len(svc.listar(recep())) == 1


def test_05_aislamiento_por_tenant():
    svc = ServicioTurnos()
    crear(svc, dt(hora=10), tenant=T1)
    t2 = crear(svc, dt(hora=10), tenant=T2)
    assert t2.estado == "PENDIENTE"


def test_06_adyacencia_exacta_permitida():
    svc = ServicioTurnos()
    crear(svc, dt(hora=10))
    t2 = crear(svc, dt(hora=10, minuto=30), paciente_id="p2")
    assert t2.estado == "PENDIENTE"


def test_07_hueco_cancelado_se_reutiliza():
    svc = ServicioTurnos()
    t = crear(svc, dt(hora=10))
    svc.cancelar(recep(), t.id, ahora=dt("2026-10-04", 10))
    assert crear(svc, dt(hora=10), paciente_id="p2").estado == "PENDIENTE"


def test_08_reprogramar_libera_original_y_nuevo_bloquea():
    svc = ServicioTurnos()
    t = crear(svc, dt(hora=10))
    res = svc.reprogramar(recep(), t.id, nuevo_inicio=dt(hora=14), ahora=dt("2026-10-04", 10))
    assert res.original.estado == "REPROGRAMADO"
    assert crear(svc, dt(hora=10), paciente_id="p2").estado == "PENDIENTE"
    with pytest.raises(ConflictoSolape):
        crear(svc, dt(hora=14), paciente_id="p3")


def test_09_sobreturno_con_motivo_se_crea_y_audita():
    svc = ServicioTurnos()
    crear(svc, dt(hora=10))
    sobre = crear(svc, dt(hora=10, minuto=15), paciente_id="p2", sobreturno=True,
                  motivo_sobreturno="urgencia con dolor")
    assert sobre.sobreturno is True
    entradas = [e for e in svc.auditoria(recep()) if e.accion == "SOBRETURNO"]
    assert len(entradas) == 1
    e = entradas[0]
    assert (e.actor, e.motivo, e.antes, e.despues) == ("recep-1", "urgencia con dolor", None, "PENDIENTE")


def test_10_sobreturno_sin_motivo_422_y_no_persiste():
    svc = ServicioTurnos()
    crear(svc, dt(hora=10))
    with pytest.raises(Invalido):
        crear(svc, dt(hora=10, minuto=15), paciente_id="p2", sobreturno=True,
              motivo_sobreturno="")
    assert len(svc.listar(recep())) == 1


def test_11_cancelacion_con_anticipacion_libera_hueco():
    svc = ServicioTurnos()
    t = crear(svc, dt(hora=10), dur=30)
    c = svc.cancelar(recep(), t.id, ahora=dt("2026-10-04", 10))  # 48 h antes
    assert c.estado == "CANCELADO"
    assert [e.accion for e in svc.auditoria(recep(), t.id)] == ["CANCELADO"]
    assert crear(svc, dt(hora=10), paciente_id="p2").estado == "PENDIENTE"


def test_12_reprogramacion_revalida_solape_en_servidor():
    svc = ServicioTurnos()
    t1 = crear(svc, dt(hora=10))
    crear(svc, dt(hora=14), paciente_id="p2")
    with pytest.raises(ConflictoSolape) as exc:
        svc.reprogramar(recep(), t1.id, nuevo_inicio=dt(hora=14, minuto=15),
                        ahora=dt("2026-10-04", 10))
    assert len(exc.value.alternativas) == 3
    intacto = svc.obtener(recep(), t1.id)
    assert (intacto.estado, intacto.inicio) == ("PENDIENTE", dt(hora=10))
