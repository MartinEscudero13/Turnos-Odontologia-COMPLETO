"""Tasks 6.1–6.4 — conflicto, concurrencia y prohibición de sobreturno: RED primero."""
from __future__ import annotations

import threading
from datetime import time

from _reserva_helpers import Harness, catalogo_estandar, reserva_payload, reservar
from conftest import P1, P2, S1, T1, dt

from app.reservas.puertos import HorarioSemanal, Prestacion, Profesional, Sillon
from app.turnos.servicio import Actor, ConflictoSolape, TurnoError


def _harness(reloj: tuple = ("2026-10-12", 9, 0)) -> Harness:
    h = Harness(reloj_inicial=dt(*reloj))
    catalogo_estandar(h)
    return h


def _turnos(h: Harness) -> list:
    return h.turnos.listar(Actor(tenant_id=T1, rol="RECEPCION", user_id="x"))


def _intentar(h: Harness, resultados: list[int], i: int) -> None:
    d = h.svc.emitir_verificacion("t1", "reservar", f"ip-{i}")
    try:
        h.svc.reservar(
            "t1",
            prestacion_id="PREST-30",
            profesional_id=P1,
            inicio=dt("2026-10-13", 11),
            nombre=f"Paciente {i}",
            telefono="+5491130551234",
            verificacion_id=d.verificacion_id,
            ip=f"ip-{i}",
        )
        resultados.append(201)
    except ConflictoSolape as exc:
        assert len(exc.alternativas) == 3
        resultados.append(409)
    except TurnoError as exc:
        resultados.append(exc.codigo)


def test_slot_tomado_entre_pasos_responde_409_con_tres_alternativas():
    h = _harness(("2026-10-12", 9, 0))
    actor = Actor(tenant_id=T1, rol="RECEPCION", user_id="x")
    h.turnos.crear(
        actor, profesional_id=P1, sillon_id=S1, paciente_id="p-recep", prestacion_id="PREST-30",
        inicio=dt("2026-10-13", 10), duracion_min=30,
    )
    r = reservar(h, inicio="2026-10-13T10:00:00+00:00")
    assert r.status_code == 409, r.text
    alts = r.json()["alternativas"]
    assert 0 < len(alts) <= 3
    assert [a["inicio"] for a in alts] == sorted(a["inicio"] for a in alts)
    assert len(_turnos(h)) == 1  # solo el de recepción, ninguno del paciente


def test_dos_reservas_concurrentes_del_mismo_slot_solo_una_persiste():
    for _ in range(5):
        h = _harness(("2026-10-12", 9, 0))
        resultados: list[int] = []
        hilos = [threading.Thread(target=_intentar, args=(h, resultados, i)) for i in range(8)]
        for t in hilos:
            t.start()
        for t in hilos:
            t.join()
        assert resultados.count(201) == 1
        assert resultados.count(409) == 7


def test_reserva_publica_con_sobreturno_responde_422_sin_turno():
    h = _harness()
    vid = h.client.post("/api/publico/t1/verificacion", json={"accion": "reservar"}).json()[
        "verificacion_id"
    ]
    r = h.client.post(
        "/api/publico/t1/reservas",
        json=reserva_payload(sobreturno=True, verificacion_id=vid),
    )
    assert r.status_code == 422, r.text
    assert _turnos(h) == []


def test_solape_por_sillon_responde_409_y_no_crea_sobreturno():
    h = Harness(reloj_inicial=dt("2026-10-13", 9))
    c = h.catalogo
    c.agregar_prestacion(Prestacion(id="PREST-30", tenant_id=T1, duracion_min=30))
    c.agregar_profesional(Profesional(id=P1, tenant_id=T1))
    c.agregar_profesional(Profesional(id=P2, tenant_id=T1))
    c.agregar_sillon(Sillon(id=S1, tenant_id=T1))  # un único sillón activo
    for dia in range(1, 8):
        c.agregar_horario(HorarioSemanal(tenant_id=T1, dia=dia, desde=time(9, 0), hasta=time(12, 0), profesional_id=P1))
        c.agregar_horario(HorarioSemanal(tenant_id=T1, dia=dia, desde=time(9, 0), hasta=time(12, 0), profesional_id=P2))
        c.agregar_horario(HorarioSemanal(tenant_id=T1, dia=dia, desde=time(8, 0), hasta=time(18, 0), profesional_id=None))
    c.agregar_habilitado(T1, P1, "PREST-30")
    c.agregar_habilitado(T1, P2, "PREST-30")

    actor = Actor(tenant_id=T1, rol="RECEPCION", user_id="x")
    # S1 ocupado por OTRO profesional (P2) de 11:00 a 11:30
    h.turnos.crear(
        actor, profesional_id=P2, sillon_id=S1, paciente_id="p-otro", prestacion_id="PREST-30",
        inicio=dt("2026-10-14", 11), duracion_min=30,
    )
    # el paciente reserva con P1 en el mismo sillón a las 11:15 → solape por sillón
    r = reservar(h, profesional=P1, inicio="2026-10-14T11:15:00+00:00")
    assert r.status_code == 409, r.text
    assert 0 < len(r.json()["alternativas"]) <= 3
    assert all(not t.sobreturno for t in _turnos(h))
    assert len(_turnos(h)) == 1
