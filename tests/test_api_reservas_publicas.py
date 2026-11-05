"""Tasks 7.1–7.5 — borde API público (Pydantic strict + FastAPI): RED primero."""
from __future__ import annotations

from _reserva_helpers import Harness, catalogo_estandar, emitir, reserva_payload, reservar
from conftest import P1, P2, S1, T1, T2, dt

from app.turnos.servicio import Actor


def _harness(**kw) -> Harness:
    h = Harness(reloj_inicial=dt("2026-10-05", 9), **kw)
    catalogo_estandar(h)
    return h


def test_payload_con_campo_extra_responde_422():
    h = _harness()
    vid = emitir(h)
    for extra, valor in {
        "sobreturno": True,
        "fin": "2026-10-06T10:15:00+00:00",
        "tenant_id": T2,
    }.items():
        payload = reserva_payload(verificacion_id=vid)
        payload[extra] = valor
        r = h.client.post("/api/publico/t1/reservas", json=payload)
        assert r.status_code == 422, (extra, r.text)


def test_post_reservas_publicas_201_con_token():
    h = _harness()
    actor = Actor(tenant_id=T1, rol="RECEPCION", user_id="x")
    # S1 ocupado por OTRO profesional a las 11:00 → el servidor elige S2
    h.turnos.crear(
        actor, profesional_id=P2, sillon_id=S1, paciente_id="p-otro", prestacion_id="PREST-30",
        inicio=dt("2026-10-06", 11), duracion_min=30,
    )
    vid = emitir(h)
    r = h.client.post(
        "/api/publico/t1/reservas",
        json=reserva_payload(inicio="2026-10-06T11:00:00+00:00", verificacion_id=vid),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["estado"] == "PENDIENTE"
    assert body["origen"] == "RESERVA_ONLINE"
    assert body["sillon_id"] == "sillon-2"
    assert body["token_publico"]


def test_get_reserva_por_token_devuelve_solo_turno_propio():
    h = _harness()
    body = reservar(h).json()
    token = body["token_publico"]
    g = h.client.get(f"/api/publico/t1/reservas/{token}")
    assert g.status_code == 200, g.text
    assert set(g.json().keys()) == {
        "turno_id", "estado", "inicio", "fin", "prestacion", "token_publico",
    }
    assert h.client.get("/api/publico/t1/reservas/NO-EXISTE").status_code == 404


def test_headers_de_actor_no_elevan_privilegios_en_rutas_publicas():
    h = _harness()
    vid = emitir(h)
    r = h.client.post(
        "/api/publico/t1/reservas",
        json=reserva_payload(verificacion_id=vid),
        headers={"X-Rol": "ADMIN", "X-Tenant-Id": T2},
    )
    assert r.status_code == 201, r.text
    assert r.json()["origen"] == "RESERVA_ONLINE"
    assert len(h.turnos.listar(Actor(tenant_id=T1, rol="RECEPCION", user_id="x"))) == 1


def test_errores_publicos_mapean_403_404_409_422_429():
    h = _harness()
    # 403 sin verificación válida
    r403 = h.client.post(
        "/api/publico/t1/reservas", json=reserva_payload(verificacion_id="INEXISTENTE")
    )
    assert r403.status_code == 403
    assert "Traceback" not in r403.text
    # 404 tenant inexistente
    r404 = h.client.get(
        "/api/publico/no-existe/disponibilidad",
        params={"prestacion": "PREST-30", "desde": "2026-10-06T00:00:00+00:00"},
    )
    assert r404.status_code == 404
    # 409 slot ocupado
    actor = Actor(tenant_id=T1, rol="RECEPCION", user_id="x")
    h.turnos.crear(
        actor, profesional_id=P1, sillon_id=S1, paciente_id="p", prestacion_id="PREST-30",
        inicio=dt("2026-10-06", 10), duracion_min=30,
    )
    r409 = reservar(h, inicio="2026-10-06T10:00:00+00:00")
    assert r409.status_code == 409
    # 422 campo extra
    vid = emitir(h)
    payload = reserva_payload(verificacion_id=vid)
    payload["fin"] = "2026-10-06T10:15:00+00:00"
    r422 = h.client.post("/api/publico/t1/reservas", json=payload)
    assert r422.status_code == 422
    # 429 rate-limit (harness con tope 1)
    h2 = Harness(rate_limit_max=1, rate_limit_ventana_s=60, reloj_inicial=dt("2026-10-05", 9))
    catalogo_estandar(h2)
    assert reservar(h2).status_code == 201
    r429 = reservar(h2, inicio="2026-10-06T11:00:00+00:00")
    assert r429.status_code == 429
