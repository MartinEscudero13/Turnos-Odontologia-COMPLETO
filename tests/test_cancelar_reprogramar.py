"""Task 3.3 — cancelar/reprogramar con anticipación y revalidación: RED primero."""
from __future__ import annotations

from datetime import timedelta

import pytest

from app.turnos.servicio import (
    Actor,
    ConflictoSolape,
    Invalido,
    Prohibido,
    ServicioTurnos,
)
from conftest import PAC1, P1, PREST30, S1, T1, dt


def recep():
    return Actor(tenant_id=T1, rol="RECEPCION", user_id="recep-1")


def odo():
    return Actor(tenant_id=T1, rol="ODONTOLOGO", user_id="odo-1", profesional_id=P1)


def base(svc, hora=10, minuto=0):
    return svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
                     prestacion_id=PREST30, inicio=dt(hora=hora, minuto=minuto),
                     duracion_min=30)


def test_cancelar_con_anticipacion_libera_hueco():
    svc = ServicioTurnos()
    t = base(svc)  # 2026-10-06 10:00
    cancelado = svc.cancelar(recep(), t.id, ahora=dt("2026-10-04", 10))  # 48 h antes
    assert cancelado.estado == "CANCELADO"
    nuevo = svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id="p2",
                      prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30)
    assert nuevo.estado == "PENDIENTE"


def test_cancelar_bajo_anticipacion_solo_recepcion():
    svc = ServicioTurnos()
    t = base(svc)
    casi = t.inicio - timedelta(hours=2)  # 2 h antes < 24 h
    with pytest.raises(Prohibido):
        svc.cancelar(odo(), t.id, ahora=casi)
    cancelado = svc.cancelar(recep(), t.id, ahora=casi)
    assert cancelado.estado == "CANCELADO"
    entradas = svc.auditoria(recep(), t.id)
    assert [(e.accion, e.antes, e.despues) for e in entradas] == [("CANCELADO", "PENDIENTE", "CANCELADO")]


def test_reprogramar_mueve_y_libera_origen():
    svc = ServicioTurnos()
    t = base(svc)
    res = svc.reprogramar(recep(), t.id, nuevo_inicio=dt(hora=14), ahora=dt("2026-10-04", 10))
    assert res.original.estado == "REPROGRAMADO"
    assert res.nuevo.estado == "PENDIENTE"
    assert res.nuevo.inicio == dt(hora=14) and res.nuevo.fin == dt(hora=14, minuto=30)
    # Hueco original reutilizable; nuevo horario bloquea.
    reuso = svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id="p2",
                      prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30)
    assert reuso.estado == "PENDIENTE"
    with pytest.raises(ConflictoSolape):
        svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id="p3",
                  prestacion_id=PREST30, inicio=dt(hora=14, minuto=15), duracion_min=30)


def test_reprogramar_a_destino_ocupado_409_y_original_intacto():
    svc = ServicioTurnos()
    t1 = base(svc, hora=10)
    base(svc, hora=14)
    with pytest.raises(ConflictoSolape):
        svc.reprogramar(recep(), t1.id, nuevo_inicio=dt(hora=14, minuto=15),
                        ahora=dt("2026-10-04", 10))
    intacto = svc.obtener(recep(), t1.id)
    assert (intacto.estado, intacto.inicio) == ("PENDIENTE", dt(hora=10))


def test_reprogramar_bajo_anticipacion_solo_recepcion():
    svc = ServicioTurnos()
    t = base(svc)
    casi = t.inicio - timedelta(hours=2)
    with pytest.raises(Prohibido):
        svc.reprogramar(odo(), t.id, nuevo_inicio=dt(hora=15), ahora=casi)


def test_reprogramar_final_422():
    svc = ServicioTurnos()
    t = base(svc)
    svc.cancelar(recep(), t.id, ahora=dt("2026-10-04", 10))
    with pytest.raises(Invalido):
        svc.reprogramar(recep(), t.id, nuevo_inicio=dt(hora=15), ahora=dt("2026-10-04", 10))


def test_reprogramar_con_duracion_explicita():
    svc = ServicioTurnos()
    t = base(svc)
    res = svc.reprogramar(recep(), t.id, nuevo_inicio=dt(hora=15), duracion_min=60,
                          ahora=dt("2026-10-04", 10))
    assert res.nuevo.fin == dt(hora=16)
