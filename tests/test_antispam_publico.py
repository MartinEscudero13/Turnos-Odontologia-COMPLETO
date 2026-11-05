"""Tasks 4.1–4.4 — anti-spam: rate-limit + verificación single-use (D5): RED primero."""
from __future__ import annotations

from _reserva_helpers import Harness, catalogo_estandar, emitir, reserva_payload, reservar
from conftest import T1, dt

from app.reservas.antispam import VerificadorMemoria
from app.turnos.servicio import Actor


def _harness(**kw) -> Harness:
    h = Harness(reloj_inicial=dt("2026-10-05", 9), **kw)
    catalogo_estandar(h)
    return h


def _turnos(h: Harness) -> list:
    return h.turnos.listar(Actor(tenant_id=T1, rol="RECEPCION", user_id="x"))


def test_rate_limit_excedido_responde_429_sin_mutar():
    h = _harness(rate_limit_max=2, rate_limit_ventana_s=60)
    for i in range(2):
        r = reservar(h, inicio=f"2026-10-06T{10 + i}:00:00+00:00")
        assert r.status_code == 201, r.text
    r = reservar(h, inicio="2026-10-06T12:00:00+00:00")
    assert r.status_code == 429, r.text
    assert "Retry-After" in r.headers
    assert len(_turnos(h)) == 2  # cero turnos nuevos


def test_accion_sin_verificacion_responde_403_sin_mutar():
    h = _harness()
    r = h.client.post(
        "/api/publico/t1/reservas",
        json=reserva_payload(verificacion_id="INEXISTENTE"),
    )
    assert r.status_code == 403, r.text
    assert _turnos(h) == []
    # el hueco sigue ofreciéndose
    d = h.client.get(
        "/api/publico/t1/disponibilidad",
        params={
            "prestacion": "PREST-30",
            "profesional": "profesional-1",
            "desde": "2026-10-06T00:00:00+00:00",
        },
    )
    inicios = {s["inicio"] for s in d.json()}
    assert "2026-10-06T10:00:00Z" in inicios


def test_verificacion_es_de_un_solo_uso():
    h = _harness()
    vid = emitir(h)
    r1 = h.client.post(
        "/api/publico/t1/reservas", json=reserva_payload(verificacion_id=vid)
    )
    assert r1.status_code == 201, r1.text
    r2 = h.client.post(
        "/api/publico/t1/reservas",
        json=reserva_payload(inicio="2026-10-06T11:00:00+00:00", verificacion_id=vid),
    )
    assert r2.status_code == 403, r2.text

    # vencida (TTL) → 403
    h.fijar_ahora("2026-10-05", 9, 0)
    vid2 = emitir(h)  # expira_at = 09:10
    h.fijar_ahora("2026-10-05", 9, 11)
    r3 = h.client.post(
        "/api/publico/t1/reservas",
        json=reserva_payload(inicio="2026-10-06T12:00:00+00:00", verificacion_id=vid2),
    )
    assert r3.status_code == 403, r3.text


def test_verificador_port_acepta_captcha_u_otp():
    ahora = dt("2026-10-05", 9)
    for canal in ("captcha", "otp"):
        v = VerificadorMemoria(ttl_min=10, canal=canal)
        d = v.desafio(tenant_id=T1, accion="reservar", ip="1.2.3.4", ahora=ahora)
        assert d.canal == canal
        assert (
            v.verificar(
                tenant_id=T1, accion="reservar", prueba=d.verificacion_id, ip="1.2.3.4", ahora=ahora
            )
            is True
        )
