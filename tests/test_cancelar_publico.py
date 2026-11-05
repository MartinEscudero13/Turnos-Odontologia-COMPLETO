"""Tasks 5.1–5.3 — cancelación pública con anticipación mínima (D6): RED primero."""
from __future__ import annotations

from _reserva_helpers import Harness, catalogo_estandar, emitir, reservar
from conftest import dt


def _harness(reloj: tuple = ("2026-10-09", 10, 0)) -> Harness:
    h = Harness(reloj_inicial=dt(*reloj))
    catalogo_estandar(h)
    return h


def test_cancelacion_en_el_umbral_exacto_se_acepta():
    h = _harness(("2026-10-09", 10, 0))
    body = reservar(h, inicio="2026-10-10T10:00:00+00:00").json()
    token = body["token_publico"]
    vid = emitir(h, accion="cancelar")
    r = h.client.post(
        f"/api/publico/t1/reservas/{token}/cancelacion", json={"verificacion_id": vid}
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "CANCELADO"


def test_cancelacion_un_minuto_bajo_el_umbral_responde_403_sin_mutar():
    h = _harness(("2026-10-09", 10, 1))
    body = reservar(h, inicio="2026-10-10T10:00:00+00:00").json()
    token = body["token_publico"]
    vid = emitir(h, accion="cancelar")
    r = h.client.post(
        f"/api/publico/t1/reservas/{token}/cancelacion", json={"verificacion_id": vid}
    )
    assert r.status_code == 403, r.text
    assert "recepción" in r.json()["detalle"]
    g = h.client.get(f"/api/publico/t1/reservas/{token}")
    assert g.status_code == 200
    assert g.json()["estado"] == "PENDIENTE"
    assert g.json()["inicio"] == "2026-10-10T10:00:00Z"


def test_cancelacion_publica_libera_el_hueco():
    h = _harness(("2026-10-05", 9, 0))
    body = reservar(h, inicio="2026-10-06T10:00:00+00:00").json()
    token = body["token_publico"]
    vid = emitir(h, accion="cancelar")
    r = h.client.post(
        f"/api/publico/t1/reservas/{token}/cancelacion", json={"verificacion_id": vid}
    )
    assert r.status_code == 200, r.text
    d = h.client.get(
        "/api/publico/t1/disponibilidad",
        params={"prestacion": "PREST-30", "profesional": "profesional-1", "desde": "2026-10-06T00:00:00+00:00"},
    )
    inicios = {s["inicio"] for s in d.json()}
    assert "2026-10-06T10:00:00Z" in inicios
