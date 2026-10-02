"""Task 3.4 — todo 409 trae 3 alternativas válidas: RED primero."""
from __future__ import annotations

import pytest

from app.turnos.overlap import intervalos_solapan
from app.turnos.servicio import Actor, ConflictoSolape, ServicioTurnos
from conftest import PAC1, P1, PREST30, S1, T1, dt


def recep():
    return Actor(tenant_id=T1, rol="RECEPCION", user_id="recep-1")


def test_crear_solapado_trae_tres_alternativas_libres():
    svc = ServicioTurnos()
    svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
              prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30)
    with pytest.raises(ConflictoSolape) as exc:
        svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id="p2",
                  prestacion_id=PREST30, inicio=dt(hora=10, minuto=15), duracion_min=30)
    alts = exc.value.alternativas
    assert len(alts) == 3
    inicios = [a.inicio for a in alts]
    assert inicios == sorted(inicios)
    for a in alts:
        assert not intervalos_solapan(a.inicio, a.fin, dt(hora=10), dt(hora=10, minuto=30))


def test_reprogramar_ocupado_trae_tres_alternativas():
    svc = ServicioTurnos()
    t1 = svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
                   prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30)
    svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id="p2",
              prestacion_id=PREST30, inicio=dt(hora=14), duracion_min=30)
    with pytest.raises(ConflictoSolape) as exc:
        svc.reprogramar(recep(), t1.id, nuevo_inicio=dt(hora=14, minuto=15),
                        ahora=dt("2026-10-04", 10))
    assert len(exc.value.alternativas) == 3


def test_primera_alternativa_es_directamente_reservable():
    svc = ServicioTurnos()
    svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
              prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30)
    try:
        svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id="p2",
                  prestacion_id=PREST30, inicio=dt(hora=10, minuto=15), duracion_min=30)
        raise AssertionError("debió chocar")
    except ConflictoSolape as choque:
        primera = choque.alternativas[0]
    reserva = svc.crear(recep(), profesional_id=P1, sillon_id=S1, paciente_id="p2",
                        prestacion_id=PREST30, inicio=primera.inicio, duracion_min=30)
    assert reserva.inicio == primera.inicio
