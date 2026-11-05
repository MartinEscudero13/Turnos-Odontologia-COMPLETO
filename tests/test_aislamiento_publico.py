"""Tasks 8.1–8.3 — aislamiento multi-tenant en rutas públicas: RED primero."""
from __future__ import annotations

from _reserva_helpers import Harness, catalogo_estandar, reservar
from conftest import P1, S1, T1, T2, dt

from app.turnos.servicio import Actor


def _harness() -> Harness:
    h = Harness(reloj_inicial=dt("2026-10-05", 9))
    catalogo_estandar(h, tenant=T1)
    catalogo_estandar(h, tenant=T2)
    return h


def test_token_de_tenant_a_en_ruta_de_tenant_b_responde_404():
    h = _harness()
    token = reservar(h, tenant="t1").json()["token_publico"]
    ajeno = h.client.get(f"/api/publico/t2/reservas/{token}")
    inexistente = h.client.get("/api/publico/t2/reservas/NO-EXISTE")
    assert ajeno.status_code == 404
    assert inexistente.status_code == 404
    assert ajeno.json() == inexistente.json()


def test_disponibilidad_de_b_no_muestra_turnos_de_a():
    h = _harness()
    actor = Actor(tenant_id=T1, rol="RECEPCION", user_id="x")
    h.turnos.crear(
        actor, profesional_id=P1, sillon_id=S1, paciente_id="p-a", prestacion_id="PREST-30",
        inicio=dt("2026-10-15", 10), duracion_min=30,
    )
    params = {"prestacion": "PREST-30", "profesional": "profesional-1", "desde": "2026-10-15T00:00:00+00:00"}
    inicios_b = {s["inicio"] for s in h.client.get("/api/publico/t2/disponibilidad", params=params).json()}
    inicios_a = {s["inicio"] for s in h.client.get("/api/publico/t1/disponibilidad", params=params).json()}
    assert "2026-10-15T10:00:00Z" in inicios_b
    assert "2026-10-15T10:00:00Z" not in inicios_a


def test_reserva_en_b_no_escribe_en_a():
    h = _harness()
    r = reservar(h, tenant="t2")
    assert r.status_code == 201, r.text
    turnos_t1 = h.turnos.listar(Actor(tenant_id=T1, rol="RECEPCION", user_id="x"))
    turnos_t2 = h.turnos.listar(Actor(tenant_id=T2, rol="RECEPCION", user_id="x"))
    assert turnos_t1 == []
    assert len(turnos_t2) == 1
    assert turnos_t2[0].tenant_id == T2
