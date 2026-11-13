"""Tasks 9.1–9.6 — borde API de caja (TDD rojo primero).

Criterios (design D9/D11, spec `caja` "Sin PHI" y "Consulta diaria"):

- payloads estrictos: un campo extra responde `422` y no procesa nada;
- endpoints completos: alta, consulta, detalle, anular, pendientes, cobrar,
  cierre (POST), estado del día, cierres por rango y reportes;
- errores mapeados: `404` no encontrado/cross-tenant, `403` RBAC, `409`
  conflicto de estado, `422` validación, `401` identidad de paciente;
- no existen reapertura, KPIs de agenda ni exportación de caja;
- el día cerrado con anulación posterior expone las dos cifras y los ajustes.

Datos ficticios: T1, U1 (RECEPCION), U2 (ADMIN), U3 (ODONTOLOGO), LINEA1.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from _caja_helpers import LINEA1, PAC1, PRESU1, U1, U2, U3, HarnessCaja, actor, d3
from conftest import T1, T2
from fastapi.testclient import TestClient

from app.caja.puertos import CobroPendiente
from app.routers.caja import crear_app

DIA = date(2026, 11, 9)
SIGUIENTE = date(2026, 11, 10)

RECEP = {"X-Tenant-Id": T1, "X-User-Id": U1, "X-Rol": "RECEPCION"}
ADMIN = {"X-Tenant-Id": T1, "X-User-Id": U2, "X-Rol": "ADMIN"}
ODONTO = {"X-Tenant-Id": T1, "X-User-Id": U3, "X-Rol": "ODONTOLOGO"}
PACIENTE = {"X-Tenant-Id": T1, "X-User-Id": PAC1, "X-Rol": "PACIENTE"}


def _client(h: HarnessCaja) -> TestClient:
    return TestClient(crear_app(h.svc))


def test_payload_con_campo_extra_422() -> None:
    # GIVEN T1 y un payload de movimiento con campos inyectados.
    h = HarnessCaja()
    client = _client(h)

    # WHEN se envían `tenant_id` o `paciente_nombre` (allow-list estricta).
    con_tenant = client.post(
        "/api/caja/movimientos",
        json={"monto": 1000, "medio": "EFECTIVO", "tenant_id": T1},
        headers=RECEP,
    )
    con_phi = client.post(
        "/api/caja/movimientos",
        json={"monto": 1000, "medio": "EFECTIVO", "paciente_nombre": "Paciente Demo"},
        headers=RECEP,
    )

    # THEN 422 y no se procesa el movimiento.
    assert con_tenant.status_code == 422
    assert con_phi.status_code == 422
    assert h.movimientos.total(T1) == 0

    # AND los totales del cierre no se aceptan desde el cliente.
    cierre = client.post(
        "/api/caja/cierre",
        json={
            "efectivo_contado": 0,
            "responsable_id": U1,
            "total_efectivo": 999999,
        },
        headers=RECEP,
    )
    assert cierre.status_code == 422
    assert h.cierres.total(T1) == 0

    # AND el motivo de anulación es un campo cerrado.
    movimiento = h.registrar(monto=1000, medio="EFECTIVO", fecha="2026-11-10")
    anulacion = client.post(
        f"/api/caja/movimientos/{movimiento.id}/anular",
        json={"motivo": "error de carga", "actor_id": U2},
        headers=ADMIN,
    )
    assert anulacion.status_code == 422
    vigente = h.movimientos.obtener(tenant_id=T1, movimiento_id=movimiento.id)
    assert vigente is not None and vigente.anulado is False


def test_crud_http_movimientos_201_200() -> None:
    # GIVEN T1 con un cobro pendiente del 2026-11-11.
    h = HarnessCaja()
    pendiente = h.imputar_tramo(fecha="2026-11-11", monto=60000, medio=None)
    assert isinstance(pendiente, CobroPendiente)
    client = _client(h)

    # WHEN se recorren todos los endpoints de caja.
    alta = client.post(
        "/api/caja/movimientos",
        json={"monto": 150000, "medio": "EFECTIVO", "fecha": "2026-11-10"},
        headers=RECEP,
    )
    assert alta.status_code == 201
    movimiento_id = alta.json()["id"]

    consulta = client.get(
        "/api/caja/movimientos", params={"fecha": "2026-11-10"}, headers=RECEP
    )
    assert consulta.status_code == 200
    assert consulta.json()["totales_vigentes"]["efectivo"] == 150000

    detalle = client.get(f"/api/caja/movimientos/{movimiento_id}", headers=RECEP)
    assert detalle.status_code == 200
    assert detalle.json()["monto"] == 150000

    anulacion = client.post(
        f"/api/caja/movimientos/{movimiento_id}/anular",
        json={"motivo": "error de carga"},
        headers=ADMIN,
    )
    assert anulacion.status_code == 200
    assert anulacion.json()["anulado"] is True

    cierre = client.post(
        "/api/caja/cierre",
        json={"efectivo_contado": 0, "responsable_id": U1},
        headers=RECEP,
    )
    assert cierre.status_code == 201

    consulta_cierre = client.get(
        "/api/caja/cierre", params={"fecha": "2026-11-10"}, headers=RECEP
    )
    assert consulta_cierre.status_code == 200
    assert consulta_cierre.json()["id"] == cierre.json()["id"]

    estado = client.get(
        "/api/caja/cierre/estado", params={"fecha": "2026-11-10"}, headers=RECEP
    )
    assert estado.status_code == 200
    assert estado.json()["estado"] == "cerrado"

    cierres = client.get(
        "/api/caja/cierres",
        params={"desde": "2026-11-09", "hasta": "2026-11-11"},
        headers=RECEP,
    )
    assert cierres.status_code == 200
    assert len(cierres.json()) == 1

    pendientes = client.get(
        "/api/caja/pendientes", params={"fecha": "2026-11-11"}, headers=RECEP
    )
    assert pendientes.status_code == 200
    assert [p["id"] for p in pendientes.json()] == [pendiente.id]

    cobro = client.post(
        f"/api/caja/pendientes/{pendiente.id}/cobrar",
        json={"medio": "TRANSFERENCIA"},
        headers=RECEP,
    )
    assert cobro.status_code in (200, 201)
    assert cobro.json()["movimiento"]["monto"] == 60000

    reportes = client.get(
        "/api/caja/reportes",
        params={"desde": "2026-11-09", "hasta": "2026-11-11"},
        headers=RECEP,
    )
    assert reportes.status_code == 200
    assert reportes.json()["fuente"] == "movimientos_vigentes"


def test_errores_mapean_404_403_409_422() -> None:
    # --- 404: recurso inexistente / cross-tenant -----------------------
    h = HarnessCaja()
    client = _client(h)
    assert client.get("/api/caja/movimientos/no-existe", headers=RECEP).status_code == 404
    movimiento_t2 = h.registrar(
        monto=1000, medio="EFECTIVO", fecha="2026-11-10", actor_=actor(tenant=T2)
    )
    assert (
        client.get(f"/api/caja/movimientos/{movimiento_t2.id}", headers=RECEP).status_code
        == 404
    )

    # --- 403: rol interno sin permiso ----------------------------------
    assert (
        client.post(
            "/api/caja/movimientos",
            json={"monto": 1000, "medio": "EFECTIVO", "fecha": "2026-11-10"},
            headers=ODONTO,
        ).status_code
        == 403
    )

    # --- 401: identidad de paciente (no es 403) ------------------------
    assert (
        client.get(
            "/api/caja/movimientos", params={"fecha": "2026-11-10"}, headers=PACIENTE
        ).status_code
        == 401
    )

    # --- 409 CIERRE_CERRADO -------------------------------------------
    h = HarnessCaja()
    client = _client(h)
    assert (
        client.post(
            "/api/caja/cierre",
            json={"efectivo_contado": 0, "responsable_id": U1},
            headers=RECEP,
        ).status_code
        == 201
    )
    cerrado = client.post(
        "/api/caja/movimientos",
        json={"monto": 1000, "medio": "EFECTIVO", "fecha": "2026-11-10"},
        headers=RECEP,
    )
    assert cerrado.status_code == 409
    assert cerrado.json()["codigo"] == "CIERRE_CERRADO"

    # --- 409 CIERRE_EXISTENTE -----------------------------------------
    repetido = client.post(
        "/api/caja/cierre",
        json={"efectivo_contado": 0, "responsable_id": U1},
        headers=RECEP,
    )
    assert repetido.status_code == 409
    assert repetido.json()["codigo"] == "CIERRE_EXISTENTE"

    # --- 409 ANULADO ---------------------------------------------------
    h = HarnessCaja()
    movimiento = h.registrar(monto=1000, medio="EFECTIVO", fecha="2026-11-10")
    client = _client(h)
    assert (
        client.post(
            f"/api/caja/movimientos/{movimiento.id}/anular",
            json={"motivo": "error de carga"},
            headers=ADMIN,
        ).status_code
        == 200
    )
    segunda = client.post(
        f"/api/caja/movimientos/{movimiento.id}/anular",
        json={"motivo": "otra vez"},
        headers=ADMIN,
    )
    assert segunda.status_code == 409
    assert segunda.json()["codigo"] == "ANULADO"

    # --- 409 COBRO_YA_RESUELTO ----------------------------------------
    h = HarnessCaja()
    pendiente = h.imputar_tramo(monto=60000, medio=None)
    assert isinstance(pendiente, CobroPendiente)
    client = _client(h)
    assert (
        client.post(
            f"/api/caja/pendientes/{pendiente.id}/cobrar",
            json={"medio": "EFECTIVO"},
            headers=RECEP,
        ).status_code
        in (200, 201)
    )
    segundo_cobro = client.post(
        f"/api/caja/pendientes/{pendiente.id}/cobrar",
        json={"medio": "EFECTIVO"},
        headers=RECEP,
    )
    assert segundo_cobro.status_code == 409
    assert segundo_cobro.json()["codigo"] == "COBRO_YA_RESUELTO"

    # --- 409 IMPUTACION_DUPLICADA (replay por otra vía) ---------------
    h = HarnessCaja()
    pendiente = h.imputar_tramo(monto=60000, medio=None)
    assert isinstance(pendiente, CobroPendiente)
    h.movimientos.registrar(
        tenant_id=T1,
        fecha=DIA,
        medio="EFECTIVO",
        monto=60000,
        tipo="INGRESO",
        usuario_id=U1,
        tramo="PACIENTE",
        presupuesto_id=PRESU1,
        linea_id=LINEA1,
        origen="IMPUTACION",
    )
    client = _client(h)
    duplicada = client.post(
        f"/api/caja/pendientes/{pendiente.id}/cobrar",
        json={"medio": "TRANSFERENCIA"},
        headers=RECEP,
    )
    assert duplicada.status_code == 409
    assert duplicada.json()["codigo"] == "IMPUTACION_DUPLICADA"

    # --- 422 validación -------------------------------------------------
    h = HarnessCaja()
    h.registrar(monto=100000, medio="EFECTIVO", fecha="2026-11-09")
    client = _client(h)
    invalidos = [
        {"monto": 0, "medio": "EFECTIVO", "fecha": "2026-11-10"},
        {"monto": 1000, "medio": "CHEQUE", "fecha": "2026-11-10"},
        {"monto": 1000, "medio": "EFECTIVO", "fecha": "10/11/2026"},
        {"medio": "EFECTIVO"},
    ]
    for payload in invalidos:
        respuesta = client.post(
            "/api/caja/movimientos", json=payload, headers=RECEP
        )
        assert respuesta.status_code == 422
        assert respuesta.status_code != 500
    # Cierre sin responsable y diferencia sin motivo.
    sin_responsable = client.post(
        "/api/caja/cierre", json={"efectivo_contado": 0}, headers=RECEP
    )
    assert sin_responsable.status_code == 422
    sin_motivo = client.post(
        "/api/caja/cierre",
        json={"efectivo_contado": 95000, "responsable_id": U1},
        headers=RECEP,
    )
    assert sin_motivo.status_code == 422
    assert h.cierres.total(T1) == 0

    # --- el error de "movimientos sin responsable" no existe ----------
    caja = Path(__file__).resolve().parents[1] / "backend" / "app" / "caja"
    for archivo in caja.glob("*.py"):
        assert "MOVIMIENTOS_SIN_RESPONSABLE" not in archivo.read_text(encoding="utf-8")


def test_cierre_http_201_200_409_422() -> None:
    # GIVEN T1 con 100000 en efectivo el 2026-11-09.
    h = HarnessCaja()
    h.registrar(monto=100000, medio="EFECTIVO", fecha="2026-11-09")
    client = _client(h)

    # WHEN se cierra el 2026-11-09 con la diferencia en cero.
    cierre = client.post(
        "/api/caja/cierre",
        json={
            "fecha": "2026-11-09",
            "efectivo_contado": 100000,
            "responsable_id": U1,
        },
        headers=RECEP,
    )

    # THEN 201 y la consulta 200.
    assert cierre.status_code == 201
    assert cierre.json()["diferencia"] == 0
    assert cierre.json()["totales"]["total_efectivo"] == 100000
    consulta = client.get(
        "/api/caja/cierre", params={"fecha": "2026-11-09"}, headers=RECEP
    )
    assert consulta.status_code == 200

    # AND un segundo cierre del mismo día es 409.
    repetido = client.post(
        "/api/caja/cierre",
        json={
            "fecha": "2026-11-09",
            "efectivo_contado": 100000,
            "responsable_id": U1,
        },
        headers=RECEP,
    )
    assert repetido.status_code == 409

    # AND una diferencia sin motivo es 422 y con motivo (sin observación) 201.
    sin_motivo = client.post(
        "/api/caja/cierre",
        json={"efectivo_contado": 95000, "responsable_id": U1},
        headers=RECEP,
    )
    assert sin_motivo.status_code == 422
    assert h.cierres.total(T1) == 1

    con_motivo = client.post(
        "/api/caja/cierre",
        json={
            "efectivo_contado": 95000,
            "responsable_id": U1,
            "motivo_diferencia": "faltante de caja",
        },
        headers=RECEP,
    )
    assert con_motivo.status_code == 201
    assert con_motivo.json()["diferencia"] == 95000
    assert con_motivo.json()["observacion"] is None


def test_rutas_inexistentes_404_405() -> None:
    # GIVEN T1 con el 2026-11-10 cerrado.
    h = HarnessCaja()
    cierre = h.cerrar_dia(fecha="2026-11-10", efectivo_contado=0, responsable_id=U1)
    client = _client(h)

    # WHEN se intentan reapertura, KPIs de agenda y exportación de caja.
    respuestas = [
        client.post("/api/caja/cierre/reabrir", json={}, headers=RECEP),
        client.post(f"/api/caja/cierre/{cierre.id}/reabrir", json={}, headers=RECEP),
        client.get("/api/caja/reportes/ocupacion", headers=RECEP),
        client.get("/api/caja/reportes/facturacion-profesional", headers=RECEP),
        client.get("/api/caja/reportes/export", headers=ADMIN),
        client.patch("/api/caja/movimientos/1", json={"monto": 1}, headers=RECEP),
        client.delete("/api/caja/movimientos/1", headers=ADMIN),
        client.patch("/api/caja/cierre", json={"efectivo_contado": 1}, headers=RECEP),
        client.delete("/api/caja/cierre", headers=ADMIN),
    ]

    # THEN 404/405, nunca 200, y el cierre sigue cerrado.
    for respuesta in respuestas:
        assert respuesta.status_code in (404, 405)
        assert respuesta.status_code != 200
    assert h.svc.estado_dia(actor(), fecha=date(2026, 11, 10)).estado == "cerrado"


def test_ajuste_expuesto_en_la_consulta() -> None:
    # GIVEN el 2026-11-10 cerrado con un ingreso de 150000 anulado el 2026-11-11.
    h = HarnessCaja()
    movimiento = h.registrar(monto=150000, medio="EFECTIVO", fecha="2026-11-10")
    h.cerrar_dia(fecha="2026-11-10", efectivo_contado=150000, responsable_id=U2)
    h.ahora = d3("2026-11-11", hora=9)
    h.anular(movimiento.id, actor_=actor("ADMIN", user_id=U2))
    client = _client(h)

    # WHEN se consulta el día cerrado por HTTP.
    respuesta = client.get(
        "/api/caja/movimientos", params={"fecha": "2026-11-10"}, headers=RECEP
    )

    # THEN devuelve las dos cifras y la marca de diferencia.
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["totales_vigentes"]["efectivo"] == 0
    assert cuerpo["totales_cierre"]["total_efectivo"] == 150000
    assert cuerpo["difieren_del_cierre"] is True

    # AND los ajustes del cierre son consultables y no llevan PHI.
    assert len(cuerpo["ajustes"]) == 1
    ajuste = cuerpo["ajustes"][0]
    assert ajuste["tipo"] == "AJUSTE_ANULACION"
    assert ajuste["monto"] == 150000
    assert ajuste["medio"] == "EFECTIVO"
    assert "paciente" not in ajuste
    assert "Paciente Demo" not in respuesta.text
    assert "+5491" not in respuesta.text

    # AND no existe un endpoint que reabra el cierre.
    assert (
        client.post("/api/caja/cierre/reabrir", json={}, headers=RECEP).status_code
        in (404, 405)
    )
