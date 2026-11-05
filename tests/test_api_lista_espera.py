"""Tasks 7.1–7.4 — borde API de lista de espera (management + aceptación pública)."""
from __future__ import annotations

from _lista_espera_helpers import PREST30, HarnessLista
from conftest import T1, dt

BASE = {"X-Tenant-Id": T1, "X-User-Id": "recep-1", "X-Rol": "RECEPCION"}


def _h() -> HarnessLista:
    h = HarnessLista()
    h.seed_catalogo()
    h.seed_paciente("paciente-1")
    return h


def test_payload_con_campo_extra_responde_422():
    h = _h()
    client = h.build_lista()
    r = client.post(
        "/api/lista-espera",
        json={"paciente_id": "paciente-1", "prestacion_id": PREST30, "tenant_id": "x"},
        headers=BASE,
    )
    assert r.status_code == 422
    r2 = client.post(
        "/api/lista-espera",
        json={"paciente_id": "paciente-1", "prestacion_id": PREST30, "fin": "2026-10-14T10:30:00+00:00"},
        headers=BASE,
    )
    assert r2.status_code == 422


def test_alta_baja_listar_por_http_201_200_204():
    h = _h()
    client = h.build_lista()
    alta = client.post(
        "/api/lista-espera",
        json={"paciente_id": "paciente-1", "prestacion_id": PREST30},
        headers=BASE,
    )
    assert alta.status_code == 201
    entrada_id = alta.json()["id"]
    assert alta.json()["estado"] == "PENDIENTE"

    lista = client.get("/api/lista-espera", headers=BASE)
    assert lista.status_code == 200
    assert [e["id"] for e in lista.json()] == [entrada_id]

    baja = client.delete(f"/api/lista-espera/{entrada_id}", headers=BASE)
    assert baja.status_code == 204
    assert client.get("/api/lista-espera", headers=BASE).json() == []


def test_aceptar_oferta_publica_201_con_turno():
    h = _h()
    h.alta_entrada(paciente_id="paciente-1", prestacion_id=PREST30, ahora=dt("2026-10-13", 9))
    turno = h.crear_turno(paciente_id="paciente-otro", inicio=dt("2026-10-14", 10))
    h.cancelar_turno(turno.id, ahora=dt("2026-10-13", 9))
    oferta = h.svc_ofertas.procesar_hueco_liberado(T1, turno.id, ahora=dt("2026-10-13", 9))
    assert oferta is not None

    client = h.build_lista()
    r = client.post(f"/api/publico/t1/ofertas/{oferta.token}/aceptar")
    assert r.status_code == 201
    body = r.json()
    assert body["origen"] == "LISTA_ESPERA"
    assert body["turno_id"]

    # token ajeno o inexistente → 404
    assert client.post("/api/publico/t1/ofertas/token-inexistente/aceptar").status_code == 404
    assert client.post("/api/publico/t2/ofertas/otro-token/aceptar").status_code == 404


def test_errores_lista_espera_mapean_404_409_422():
    h = _h()
    client = h.build_lista()
    # 404: baja de una entrada inexistente
    r404 = client.delete("/api/lista-espera/entrada-inexistente", headers=BASE)
    assert r404.status_code == 404
    assert "trace" not in r404.text.lower() and "detalle" in r404.json()
    # 409: alta duplicada
    client.post("/api/lista-espera", json={"paciente_id": "paciente-1", "prestacion_id": PREST30}, headers=BASE)
    r409 = client.post(
        "/api/lista-espera", json={"paciente_id": "paciente-1", "prestacion_id": PREST30}, headers=BASE
    )
    assert r409.status_code == 409
    assert "detalle" in r409.json()
    # 422: payload con campo extra
    r422 = client.post(
        "/api/lista-espera", json={"paciente_id": "paciente-1", "prestacion_id": PREST30, "extra": 1}, headers=BASE
    )
    assert r422.status_code == 422
