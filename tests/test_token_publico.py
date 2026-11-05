"""Tasks 3.1–3.4 — token público UUID v4 (D3): RED primero."""
from __future__ import annotations

import uuid

from _reserva_helpers import Harness, catalogo_estandar, emitir, reservar
from conftest import P1, PAC1, PREST30, S1, T1, T2, dt

from app.reservas.puertos import TokenResuelto
from app.reservas.tokens import TokenRepositorioEnMemoria
from app.turnos.servicio import Actor


def _harness() -> Harness:
    h = Harness(reloj_inicial=dt("2026-10-05", 9))
    catalogo_estandar(h)
    return h


def test_reserva_devuelve_token_uuid_no_secuencial():
    h = _harness()
    t1 = reservar(h).json()["token_publico"]
    t2 = reservar(h, inicio="2026-10-06T11:00:00+00:00").json()["token_publico"]
    assert t1 != t2
    for t in (t1, t2):
        assert uuid.UUID(t).version == 4
        assert not t.isdigit()


def test_token_solo_resuelve_en_su_tenant():
    repo = TokenRepositorioEnMemoria()
    token = repo.emitir(T1, "turno-1")
    assert repo.resolver(T2, token) is None
    assert repo.resolver(T1, token) == TokenResuelto(tenant_id=T1, turno_id="turno-1")


def test_token_de_turno_cancelado_o_vencido_no_gestiona():
    h = _harness()
    body = reservar(h).json()
    token = body["token_publico"]
    assert h.client.get(f"/api/publico/t1/reservas/{token}").status_code == 200

    # cancelado → el token deja de gestionar (404)
    vid = emitir(h, accion="cancelar")
    r = h.client.post(f"/api/publico/t1/reservas/{token}/cancelacion", json={"verificacion_id": vid})
    assert r.status_code == 200
    assert h.client.get(f"/api/publico/t1/reservas/{token}").status_code == 404

    # fin en el pasado → 404 (vigencia por fin, no por reloj)
    actor = Actor(tenant_id=T1, rol="RECEPCION", user_id="x")
    pasado = h.turnos.crear(
        actor, profesional_id=P1, sillon_id=S1, paciente_id=PAC1, prestacion_id=PREST30,
        inicio=dt("2026-10-01", 10), duracion_min=30,
    )
    tok = h.tokens.emitir(T1, pasado.id)
    assert h.client.get(f"/api/publico/t1/reservas/{tok}").status_code == 404


def test_reprogramar_transfiere_el_token_al_turno_nuevo():
    h = _harness()
    h.fijar_ahora("2026-10-20", 9)
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
    resuelto = h.tokens.resolver(T1, token)
    assert resuelto is not None
    assert resuelto.turno_id == r.json()["nuevo"]["turno_id"]
    g = h.client.get(f"/api/publico/t1/reservas/{token}")
    assert g.status_code == 200
    assert g.json()["turno_id"] == r.json()["nuevo"]["turno_id"]
