"""Tasks 7.1–7.3 — borde HTTP del odontograma.

`POST /api/odontograma` registra un hallazgo o deriva (bloque `derivar` con
header `Idempotency-Key`); `GET /api/odontograma` lee el historial y
`POST /api/odontograma/{id}/resolver` marca `resuelto` una sola vez. No existe
`PATCH` ni `DELETE` (inmutabilidad clínica, D2).
"""
from __future__ import annotations

from _odontograma_helpers import KEY, PAC1, PREST1, HarnessOdontograma, d3
from conftest import P1, T1
from fastapi.testclient import TestClient

from app.routers.odontograma import crear_app

ODONTO = {
    "X-Tenant-Id": T1,
    "X-User-Id": "odont-1",
    "X-Rol": "ODONTOLOGO",
    "X-Profesional-Id": P1,
}
RECEP = {"X-Tenant-Id": T1, "X-User-Id": "recep-1", "X-Rol": "RECEPCION"}


def _client() -> tuple[HarnessOdontograma, TestClient]:
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    return h, TestClient(crear_app(h.svc))


def _body(*, pieza_fdi: int = 36, derivar: bool = False) -> dict[str, object]:
    body: dict[str, object] = {
        "paciente_id": PAC1,
        "pieza_fdi": pieza_fdi,
        "superficie": "O",
        "hallazgo": "caries oclusal",
        "fecha": d3().isoformat(),
        "profesional_id": P1,
    }
    if derivar:
        body["derivar"] = {"prestacion_id": PREST1}
    return body


def test_payload_con_campo_extra_422():
    _, client = _client()
    r = client.post(
        "/api/odontograma", json={**_body(), "tenant_id": "intruso"}, headers=ODONTO
    )
    assert r.status_code == 422
    r2 = client.post(
        "/api/odontograma",
        json={**_body(derivar=True), "derivar": {"prestacion_id": PREST1, "extra": 1}},
        headers={**ODONTO, "Idempotency-Key": KEY},
    )
    assert r2.status_code == 422


def test_crud_http_201_200():
    h, client = _client()

    creado = client.post("/api/odontograma", json=_body(), headers=ODONTO)
    assert creado.status_code == 201
    hallazgo_id = creado.json()["id"]
    assert creado.json()["resuelto"] is False

    historial = client.get(
        "/api/odontograma", params={"paciente_id": PAC1}, headers=RECEP
    )
    assert historial.status_code == 200
    assert [x["id"] for x in historial.json()] == [hallazgo_id]

    por_pieza = client.get(
        "/api/odontograma",
        params={"paciente_id": PAC1, "pieza_fdi": 36},
        headers=RECEP,
    )
    assert por_pieza.status_code == 200
    assert len(por_pieza.json()) == 1
    vacia = client.get(
        "/api/odontograma",
        params={"paciente_id": PAC1, "pieza_fdi": 11},
        headers=RECEP,
    )
    assert vacia.status_code == 200 and vacia.json() == []

    derivada = client.post(
        "/api/odontograma",
        json=_body(derivar=True),
        headers={**ODONTO, "Idempotency-Key": KEY},
    )
    assert derivada.status_code == 201
    assert derivada.json()["creada"] is True
    derivacion = derivada.json()
    assert derivacion["hallazgo_id"] and derivacion["linea_id"]

    replay = client.post(
        "/api/odontograma",
        json=_body(derivar=True),
        headers={**ODONTO, "Idempotency-Key": KEY},
    )
    assert replay.status_code == 200
    assert replay.json()["creada"] is False
    assert replay.json()["hallazgo_id"] == derivacion["hallazgo_id"]
    assert replay.json()["linea_id"] == derivacion["linea_id"]
    assert h.hallazgos.total(T1) == 2
    assert h.lineas.total(T1) == 1

    resuelto = client.post(
        f"/api/odontograma/{hallazgo_id}/resolver", headers=ODONTO
    )
    assert resuelto.status_code == 200
    assert resuelto.json()["resuelto"] is True


def test_no_existe_patch_ni_delete():
    _, client = _client()
    creado = client.post("/api/odontograma", json=_body(), headers=ODONTO)
    assert creado.status_code == 201
    hallazgo_id = creado.json()["id"]

    patch = client.patch(
        f"/api/odontograma/{hallazgo_id}", json={"hallazgo": "texto editado"}, headers=ODONTO
    )
    delete = client.delete(f"/api/odontograma/{hallazgo_id}", headers=ODONTO)
    patch_resolver = client.patch(
        f"/api/odontograma/{hallazgo_id}/resolver", json={"resuelto": False}, headers=ODONTO
    )
    for respuesta in (patch, delete, patch_resolver):
        assert respuesta.status_code in (405, 403, 404)
        assert respuesta.status_code != 200

    historial = client.get(
        "/api/odontograma", params={"paciente_id": PAC1}, headers=RECEP
    ).json()
    assert [x["hallazgo"] for x in historial] == ["caries oclusal"]
    assert historial[0]["resuelto"] is False


def test_errores_mapean_404_403_409_422():
    _, client = _client()

    r404 = client.post(
        "/api/odontograma", json={**_body(), "paciente_id": "paciente-999"}, headers=ODONTO
    )
    assert r404.status_code == 404
    assert "detalle" in r404.json() and "trace" not in r404.text.lower()

    r403 = client.post("/api/odontograma", json=_body(), headers=RECEP)
    assert r403.status_code == 403

    assert (
        client.post(
            "/api/odontograma",
            json=_body(derivar=True),
            headers={**ODONTO, "Idempotency-Key": KEY},
        ).status_code
        == 201
    )
    r409 = client.post(
        "/api/odontograma",
        json=_body(pieza_fdi=37, derivar=True),
        headers={**ODONTO, "Idempotency-Key": KEY},
    )
    assert r409.status_code == 409

    without_key = client.post(
        "/api/odontograma", json=_body(derivar=True), headers=ODONTO
    )
    assert without_key.status_code == 422
    bad_key = client.post(
        "/api/odontograma",
        json=_body(derivar=True),
        headers={**ODONTO, "Idempotency-Key": "no-es-uuid"},
    )
    assert bad_key.status_code == 422

    empty_body = client.post("/api/odontograma", json={}, headers=ODONTO)
    assert empty_body.status_code == 422
    empty_text = client.post(
        "/api/odontograma", json={**_body(), "hallazgo": ""}, headers=ODONTO
    )
    assert empty_text.status_code == 422
