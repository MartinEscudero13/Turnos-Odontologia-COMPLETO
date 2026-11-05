"""Tasks 5.4–5.5 — reprogramación pública (D6/D7): RED primero."""
from __future__ import annotations

from _reserva_helpers import Harness, catalogo_estandar, emitir, reservar
from conftest import P1, S1, T1, dt

from app.turnos.servicio import Actor


def _harness(reloj: tuple = ("2026-10-20", 9, 0)) -> Harness:
    h = Harness(reloj_inicial=dt(*reloj))
    catalogo_estandar(h)
    return h


def test_reprogramacion_publica_a_hueco_ocupado_responde_409_con_tres_alternativas():
    h = _harness(("2026-10-05", 9, 0))
    body = reservar(h, inicio="2026-10-12T10:00:00+00:00").json()
    token = body["token_publico"]
    actor = Actor(tenant_id=T1, rol="RECEPCION", user_id="x")
    h.turnos.crear(
        actor, profesional_id=P1, sillon_id=S1, paciente_id="p-otro", prestacion_id="PREST-30",
        inicio=dt("2026-10-12", 14), duracion_min=30,
    )
    vid = emitir(h, accion="reprogramar")
    r = h.client.post(
        f"/api/publico/t1/reservas/{token}/reprogramacion",
        json={"nuevo_inicio": "2026-10-12T14:15:00+00:00", "verificacion_id": vid},
    )
    assert r.status_code == 409, r.text
    alts = r.json()["alternativas"]
    assert 0 < len(alts) <= 3
    assert [a["inicio"] for a in alts] == sorted(a["inicio"] for a in alts)
    g = h.client.get(f"/api/publico/t1/reservas/{token}")
    assert g.status_code == 200
    assert g.json()["estado"] == "PENDIENTE"
    assert g.json()["inicio"] == "2026-10-12T10:00:00Z"


def test_reprogramacion_publica_exitosa_marca_original_y_crea_nuevo():
    h = _harness(("2026-10-20", 9, 0))
    body = reservar(h, inicio="2026-10-21T10:00:00+00:00").json()
    token = body["token_publico"]
    vid = emitir(h, accion="reprogramar")
    r = h.client.post(
        f"/api/publico/t1/reservas/{token}/reprogramacion",
        json={"nuevo_inicio": "2026-10-21T14:00:00+00:00", "verificacion_id": vid},
    )
    assert r.status_code == 200, r.text
    assert r.json()["original"]["estado"] == "REPROGRAMADO"
    assert r.json()["nuevo"]["estado"] == "PENDIENTE"
    assert r.json()["nuevo"]["inicio"] == "2026-10-21T14:00:00Z"
