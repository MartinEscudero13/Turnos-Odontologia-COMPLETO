"""Task 4.2 — concurrencia doble-reserva: solo una confirma (sin flakiness)."""
from __future__ import annotations

import threading

from app.turnos.servicio import Actor, ConflictoSolape, ServicioTurnos
from conftest import PAC1, P1, PREST30, S1, T1, dt


def intentar(svc, resultados, i):
    actor = Actor(tenant_id=T1, rol="RECEPCION", user_id=f"recep-{i}")
    try:
        t = svc.crear(actor, profesional_id=P1, sillon_id=S1, paciente_id=f"p{i}",
                      prestacion_id=PREST30, inicio=dt(hora=10), duracion_min=30)
        resultados.append(("ok", t.id))
    except ConflictoSolape as exc:
        assert len(exc.alternativas) == 3
        resultados.append(("conflicto", None))


def correr_carrera(n=8):
    svc = ServicioTurnos()
    resultados: list = []
    hilos = [threading.Thread(target=intentar, args=(svc, resultados, i)) for i in range(n)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    return resultados


def test_doble_reserva_solo_una_confirma():
    for _ in range(5):  # repetir para descartar flakiness
        res = correr_carrera()
        assert [r for r, _ in res].count("ok") == 1
        assert [r for r, _ in res].count("conflicto") == 7


def test_huecos_distintos_no_chocan_en_paralelo():
    svc = ServicioTurnos()
    errores: list = []

    def reservar(hora):
        try:
            svc.crear(Actor(tenant_id=T1, rol="RECEPCION", user_id="r"),
                      profesional_id=P1, sillon_id=S1, paciente_id=PAC1,
                      prestacion_id=PREST30, inicio=dt(hora=hora), duracion_min=30)
        except Exception as exc:  # noqa: BLE001
            errores.append(exc)

    hilos = [threading.Thread(target=reservar, args=(h,)) for h in (9, 10, 11)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert errores == []
    assert len(svc.listar(Actor(tenant_id=T1, rol="RECEPCION", user_id="r"))) == 3
