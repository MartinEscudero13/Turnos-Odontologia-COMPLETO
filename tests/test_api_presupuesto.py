"""Tasks 7.4–7.6 — borde HTTP del presupuesto.

`POST /api/presupuestos` crea el borrador, `GET` lee el presupuesto con sus líneas
y decisiones, `POST /{id}/lineas` agrega, `POST /{id}/emitir` fija `vence_en` y
`POST /{id}/aceptar` registra la decisión. No existe `PATCH` ni `DELETE` de línea
(D8.1).
"""
from __future__ import annotations

from _odontograma_helpers import PAC1, PREST1, d3
from _presupuesto_helpers import HarnessPresupuesto
from conftest import P1, T1
from fastapi.testclient import TestClient

from app.routers.presupuesto import crear_app

RECEP = {"X-Tenant-Id": T1, "X-User-Id": "recep-1", "X-Rol": "RECEPCION"}
ODONTO = {
    "X-Tenant-Id": T1,
    "X-User-Id": "odont-1",
    "X-Rol": "ODONTOLOGO",
    "X-Profesional-Id": P1,
}
VENCE = d3("2026-12-31", 23, 59).isoformat()


def _client() -> tuple[HarnessPresupuesto, TestClient]:
    h = HarnessPresupuesto()
    return h, TestClient(crear_app(h.svc))


def _crear(client: TestClient) -> str:
    alta = client.post("/api/presupuestos", json={"paciente_id": PAC1}, headers=RECEP)
    assert alta.status_code == 201
    return alta.json()["id"]


def _linea(client: TestClient, presupuesto_id: str, *, monto: int = 100000) -> str:
    r = client.post(
        f"/api/presupuestos/{presupuesto_id}/lineas",
        json={"prestacion_id": PREST1, "monto": monto},
        headers=RECEP,
    )
    assert r.status_code == 201
    return r.json()["id"]


def test_payload_con_campo_extra_422():
    _, client = _client()
    presupuesto_id = _crear(client)
    r = client.post(
        f"/api/presupuestos/{presupuesto_id}/lineas",
        json={"prestacion_id": PREST1, "monto": 100000, "tenant_id": "intruso"},
        headers=RECEP,
    )
    assert r.status_code == 422
    extra_creacion = client.post(
        "/api/presupuestos", json={"paciente_id": PAC1, "vence_en": VENCE}, headers=RECEP
    )
    assert extra_creacion.status_code == 422


def test_crud_http_201_200():
    h, client = _client()
    presupuesto_id = _crear(client)

    inicial = client.get(f"/api/presupuestos/{presupuesto_id}", headers=RECEP)
    assert inicial.status_code == 200
    assert inicial.json()["estado"] == "BORRADOR"
    assert inicial.json()["vence_en"] is None
    assert inicial.json()["lineas"] == []

    linea_id = _linea(client, presupuesto_id)
    detalle = client.get(f"/api/presupuestos/{presupuesto_id}", headers=RECEP).json()
    assert [x["linea"]["id"] for x in detalle["lineas"]] == [linea_id]
    assert detalle["lineas"][0]["aceptacion"] is None
    assert detalle["lineas"][0]["linea"]["monto"] == 100000
    assert detalle["lineas"][0]["linea"]["origen_cobertura"] == "SIN_COBERTURA"
    assert detalle["lineas"][0]["linea"]["validada_en_vivo"] is False

    emitido = client.post(
        f"/api/presupuestos/{presupuesto_id}/emitir", json={"vence_en": VENCE}, headers=RECEP
    )
    assert emitido.status_code == 200
    assert emitido.json()["estado"] == "VIGENTE"
    assert emitido.json()["vence_en"] is not None

    aceptada = client.post(
        f"/api/presupuestos/{presupuesto_id}/aceptar",
        json={"linea_id": linea_id, "acepta": True, "canal": "CONSULTORIO"},
        headers=RECEP,
    )
    assert aceptada.status_code == 200
    assert aceptada.json()["estado"] == "ACEPTADO"
    assert h.imputacion.llamadas_caja[0].linea_id == linea_id

    final = client.get(f"/api/presupuestos/{presupuesto_id}", headers=RECEP).json()
    assert final["estado"] == "ACEPTADO"
    assert final["lineas"][0]["aceptacion"]["acepta"] is True

    coleccion = client.get(
        "/api/presupuestos", params={"paciente_id": PAC1}, headers=RECEP
    )
    assert coleccion.status_code == 200
    assert [p["id"] for p in coleccion.json()] == [presupuesto_id]


def test_lineas_sin_patch_ni_delete_api():
    _, client = _client()
    presupuesto_id = _crear(client)
    linea_id = _linea(client, presupuesto_id)

    patch = client.patch(
        f"/api/presupuestos/{presupuesto_id}/lineas/{linea_id}",
        json={"monto": 1},
        headers=RECEP,
    )
    delete = client.delete(
        f"/api/presupuestos/{presupuesto_id}/lineas/{linea_id}", headers=RECEP
    )
    patch_coleccion = client.patch(
        f"/api/presupuestos/{presupuesto_id}/lineas", json={"monto": 1}, headers=RECEP
    )
    for respuesta in (patch, delete, patch_coleccion):
        assert respuesta.status_code in (405, 403, 404)
        assert respuesta.status_code != 200

    detalle = client.get(f"/api/presupuestos/{presupuesto_id}", headers=RECEP).json()
    assert detalle["lineas"][0]["linea"]["monto"] == 100000


def test_errores_mapean_404_403_409_422():
    _, client = _client()

    r404 = client.get("/api/presupuestos/presupuesto-999", headers=RECEP)
    assert r404.status_code == 404
    assert "detalle" in r404.json() and "trace" not in r404.text.lower()

    presupuesto_id = _crear(client)
    linea_id = _linea(client, presupuesto_id)
    r403 = client.post(
        f"/api/presupuestos/{presupuesto_id}/aceptar",
        json={"linea_id": linea_id, "acepta": True, "canal": "CONSULTORIO"},
        headers=ODONTO,
    )
    assert r403.status_code == 403

    assert (
        client.post(
            f"/api/presupuestos/{presupuesto_id}/emitir",
            json={"vence_en": VENCE},
            headers=RECEP,
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/presupuestos/{presupuesto_id}/aceptar",
            json={"linea_id": linea_id, "acepta": True, "canal": "CONSULTORIO"},
            headers=RECEP,
        ).status_code
        == 200
    )
    r409 = client.post(
        f"/api/presupuestos/{presupuesto_id}/aceptar",
        json={"linea_id": linea_id, "acepta": False, "canal": "CONSULTORIO"},
        headers=RECEP,
    )
    assert r409.status_code == 409

    otro = _crear(client)
    _linea(client, otro)
    pasado = client.post(
        f"/api/presupuestos/{otro}/emitir",
        json={"vence_en": d3("2026-11-01").isoformat()},
        headers=RECEP,
    )
    assert pasado.status_code == 422
    assert client.get(f"/api/presupuestos/{otro}", headers=RECEP).json()["estado"] == "BORRADOR"

    naive = client.post(
        f"/api/presupuestos/{otro}/emitir",
        json={"vence_en": "2026-11-30T23:59:59"},
        headers=RECEP,
    )
    assert naive.status_code == 422

    canal_vacio = client.post(
        f"/api/presupuestos/{presupuesto_id}/aceptar",
        json={"linea_id": linea_id, "acepta": True, "canal": ""},
        headers=RECEP,
    )
    assert canal_vacio.status_code == 422
    body_vacio = client.post(
        f"/api/presupuestos/{presupuesto_id}/aceptar", json={}, headers=RECEP
    )
    assert body_vacio.status_code == 422
