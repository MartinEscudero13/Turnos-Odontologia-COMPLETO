"""Tasks 3.1–3.4 — borde API FastAPI (contrato HTTP): RED primero."""
from __future__ import annotations

from datetime import UTC

from conftest import P1, PAC1, PREST30, S1, T1, T2
from fastapi.testclient import TestClient

from app.turnos.servicio import ServicioTurnos

BASE = {"X-Tenant-Id": T1, "X-User-Id": "recep-1", "X-Rol": "RECEPCION"}
PAYLOAD = {
    "profesional_id": P1,
    "sillon_id": S1,
    "paciente_id": PAC1,
    "prestacion_id": PREST30,
    "inicio": "2026-10-06T10:00:00+00:00",
    "duracion_min": 30,
}


def cliente():
    from app.routers.turnos import crear_app

    return TestClient(crear_app(ServicioTurnos()))


def test_crear_201_con_fin_calculado():
    c = cliente()
    r = c.post("/api/turnos", json=PAYLOAD, headers=BASE)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["estado"] == "PENDIENTE"
    # Pydantic v2 serializa UTC con sufijo Z (ISO-8601 con offset, válido).
    assert body["fin"] == "2026-10-06T10:30:00Z"


def test_solape_409_con_tres_alternativas_en_body():
    c = cliente()
    assert c.post("/api/turnos", json=PAYLOAD, headers=BASE).status_code == 201
    otro = dict(PAYLOAD, paciente_id="p2", inicio="2026-10-06T10:15:00+00:00")
    r = c.post("/api/turnos", json=otro, headers=BASE)
    assert r.status_code == 409
    assert len(r.json()["alternativas"]) == 3


def test_fin_cliente_distinto_422():
    c = cliente()
    r = c.post("/api/turnos", json=dict(PAYLOAD, fin_cliente="2026-10-06T10:45:00+00:00"),
               headers=BASE)
    assert r.status_code == 422


def test_sobreturno_sin_motivo_422_y_con_motivo_200():
    c = cliente()
    turno_id = c.post("/api/turnos", json=PAYLOAD, headers=BASE).json()["id"]
    r = c.post(f"/api/turnos/{turno_id}/sobreturno", json={"motivo": "  "}, headers=BASE)
    assert r.status_code == 422
    r = c.post(f"/api/turnos/{turno_id}/sobreturno", json={"motivo": "urgencia con dolor"},
               headers=BASE)
    assert r.status_code == 200
    assert r.json()["sobreturno"] is True


def test_cancelar_bajo_anticipacion_no_recepcion_403():
    from datetime import datetime, timedelta

    c = cliente()
    inicio = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    payload = dict(PAYLOAD, inicio=inicio)
    turno_id = c.post("/api/turnos", json=payload, headers=BASE).json()["id"]
    odo = {"X-Tenant-Id": T1, "X-User-Id": "odo-1", "X-Rol": "ODONTOLOGO",
           "X-Profesional-Id": P1}
    r = c.post(f"/api/turnos/{turno_id}/cancelar", headers=odo)
    assert r.status_code == 403  # 2 h < 24 h de anticipación mínima
    r = c.post(f"/api/turnos/{turno_id}/cancelar", headers=BASE)
    assert r.status_code == 200
    assert r.json()["estado"] == "CANCELADO"


def test_reprogramar_a_ocupado_409_y_original_intacto():
    c = cliente()
    t1 = c.post("/api/turnos", json=PAYLOAD, headers=BASE).json()["id"]
    c.post("/api/turnos", json=dict(PAYLOAD, paciente_id="p2",
                                    inicio="2026-10-06T14:00:00+00:00"), headers=BASE)
    r = c.post(f"/api/turnos/{t1}/reprogramar",
               json={"nuevo_inicio": "2026-10-06T14:15:00+00:00"}, headers=BASE)
    assert r.status_code == 409
    assert len(r.json()["alternativas"]) == 3
    assert c.get(f"/api/turnos/{t1}", headers=BASE).json()["estado"] == "PENDIENTE"


def test_get_cross_tenant_404():
    c = cliente()
    turno_id = c.post("/api/turnos", json=PAYLOAD, headers=BASE).json()["id"]
    otro = {"X-Tenant-Id": T2, "X-User-Id": "recep-2", "X-Rol": "RECEPCION"}
    assert c.get(f"/api/turnos/{turno_id}", headers=otro).status_code == 404
    assert c.get("/api/turnos", headers=otro).json() == []


def test_patch_solo_paciente_y_strict_422():
    c = cliente()
    turno_id = c.post("/api/turnos", json=PAYLOAD, headers=BASE).json()["id"]
    r = c.patch(f"/api/turnos/{turno_id}", json={"paciente_id": "p9"}, headers=BASE)
    assert r.status_code == 200 and r.json()["paciente_id"] == "p9"
    r = c.patch(f"/api/turnos/{turno_id}", json={"estado": "CONFIRMADO"}, headers=BASE)
    assert r.status_code == 422


def test_rol_invalido_422():
    c = cliente()
    r = c.get("/api/turnos", headers={"X-Tenant-Id": T1, "X-User-Id": "u", "X-Rol": "JEFE"})
    assert r.status_code == 422


def test_reprogramar_strict_rechaza_extras():
    c = cliente()
    turno_id = c.post("/api/turnos", json=PAYLOAD, headers=BASE).json()["id"]
    r = c.post(f"/api/turnos/{turno_id}/reprogramar",
               json={"nuevo_inicio": "2026-10-06T15:00:00+00:00", "otro": 1}, headers=BASE)
    assert r.status_code == 422
