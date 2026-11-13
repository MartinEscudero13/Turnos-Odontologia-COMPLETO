"""Tasks 8.13–8.17 — aislamiento multi-tenant de caja (TDD rojo primero).

Criterios (spec `caja` "Aislamiento multi-tenant de caja", design D7):

- T1 no ve movimientos, pendientes, cierres, ajustes ni reportes de T2, y
  viceversa, sin filtrar la existencia del recurso (`404` o lista vacía);
- anular o cobrar un recurso de otro tenant responde `404` sin efectos;
- una imputación con `linea_id` de otro tenant no escribe nada.

Datos ficticios: T1/T2, U1/U2 (T1), U9 (ADMIN de T2), PACI-1.
"""
from __future__ import annotations

import pytest
from _caja_helpers import LINEA1, PRESU1, U1, U2, U9, HarnessCaja, actor, d3
from conftest import T1, T2
from fastapi.testclient import TestClient

from app.routers.caja import crear_app
from app.turnos.servicio import NoEncontrado

FECHA = "2026-11-10"

ADMIN_T1 = {"X-Tenant-Id": T1, "X-User-Id": U2, "X-Rol": "ADMIN"}
RECEP_T1 = {"X-Tenant-Id": T1, "X-User-Id": U1, "X-Rol": "RECEPCION"}
ADMIN_T2 = {"X-Tenant-Id": T2, "X-User-Id": U9, "X-Rol": "ADMIN"}
RECEP_T2 = {"X-Tenant-Id": T2, "X-User-Id": U9, "X-Rol": "RECEPCION"}


def test_movimiento_t1_no_visible_en_t2() -> None:
    # GIVEN T1 con el movimiento M1 del 2026-11-10.
    h = HarnessCaja()
    movimiento = h.registrar(monto=150000, medio="EFECTIVO", fecha=FECHA)
    client = TestClient(crear_app(h.svc))

    # WHEN un actor de T2 consulta los movimientos del día.
    consulta = client.get(
        "/api/caja/movimientos", params={"fecha": FECHA}, headers=RECEP_T2
    )
    detalle = client.get(
        f"/api/caja/movimientos/{movimiento.id}", headers=RECEP_T2
    )

    # THEN M1 no aparece y el detalle por id responde 404.
    assert consulta.status_code == 200
    assert consulta.json()["movimientos"] == []
    assert consulta.json()["totales_vigentes"]["efectivo"] == 0
    assert detalle.status_code == 404
    assert detalle.json()["detalle"] == "movimiento de caja no encontrado"


def test_anular_desde_otro_tenant_404() -> None:
    # GIVEN T2 y el movimiento M1 de T1.
    h = HarnessCaja()
    movimiento = h.registrar(monto=150000, medio="EFECTIVO", fecha=FECHA)
    client = TestClient(crear_app(h.svc))

    # WHEN un ADMIN de T2 intenta anular M1.
    respuesta = client.post(
        f"/api/caja/movimientos/{movimiento.id}/anular",
        json={"motivo": "cobro duplicado"},
        headers=ADMIN_T2,
    )

    # THEN 404, M1 sigue vigente y no hay compensatorio ni ajuste.
    assert respuesta.status_code == 404
    vigente = h.movimientos.obtener(tenant_id=T1, movimiento_id=movimiento.id)
    assert vigente is not None and vigente.anulado is False
    assert h.movimientos.total(T2) == 0
    assert h.ajustes.total(T1) == 0


def test_cobrar_pendiente_otro_tenant_404() -> None:
    # GIVEN T1 con el cobro pendiente PEND-1.
    h = HarnessCaja()
    pendiente = h.imputar_tramo(monto=60000, medio=None)
    assert pendiente is not None
    client = TestClient(crear_app(h.svc))

    # WHEN un usuario de T2 intenta cobrarlo.
    respuesta = client.post(
        f"/api/caja/pendientes/{pendiente.id}/cobrar",
        json={"medio": "TRANSFERENCIA"},
        headers=RECEP_T2,
    )
    listado = client.get("/api/caja/pendientes", headers=RECEP_T2)

    # THEN 404, no se crea ningún movimiento en T2 y T2 no ve el pendiente.
    assert respuesta.status_code == 404
    assert h.movimientos.total(T2) == 0
    assert listado.status_code == 200
    assert listado.json() == []


def test_ajuste_no_visible_desde_otro_tenant() -> None:
    # GIVEN T1 con el cierre del 2026-11-10 y una anulación posterior que
    # asienta un ajuste post-cierre.
    h = HarnessCaja()
    movimiento = h.registrar(monto=150000, medio="EFECTIVO", fecha=FECHA)
    cierre = h.cerrar_dia(fecha=FECHA, efectivo_contado=150000, responsable_id=U2)
    h.ahora = d3("2026-11-11", hora=9)
    h.anular(movimiento.id, actor_=actor("ADMIN", user_id=U2))
    [ajuste] = h.ajustes.listar_por_cierre(tenant_id=T1, cierre_id=cierre.id)
    client = TestClient(crear_app(h.svc))

    # WHEN un actor de T2 consulta el cierre y los movimientos del día ajustado.
    respuesta = client.get("/api/caja/cierre", params={"fecha": FECHA}, headers=RECEP_T2)
    consulta = client.get(
        "/api/caja/movimientos", params={"fecha": FECHA}, headers=RECEP_T2
    )

    # THEN el cierre de T1 responde 404 y el ajuste no aparece.
    assert respuesta.status_code == 404
    assert consulta.status_code == 200
    assert consulta.json()["movimientos"] == []
    assert consulta.json()["ajustes"] == []
    assert consulta.json()["totales_cierre"] is None
    assert (
        h.ajustes.listar_por_cierre(tenant_id=T2, cierre_id=ajuste.cierre_id) == []
    )


def test_imputacion_de_otro_tenant_no_escribe_en_t1() -> None:
    # GIVEN T1 y la línea L9 del presupuesto de T2.
    h = HarnessCaja()
    linea_t2 = "linea-9"
    h.lineas_presupuesto.agregar(T2, PRESU1, linea_t2)

    # WHEN llega una imputación con tenant_id=T1 y linea_id=L9.
    with pytest.raises(NoEncontrado) as excinfo:
        h.imputar(tenant_id=T1, presupuesto_id=PRESU1, linea_id=linea_t2)

    # THEN 404 y no crea movimientos, pendientes ni cuentas por cobrar en T1.
    assert excinfo.value.codigo == 404
    assert h.movimientos.total(T1) == 0
    assert h.pendientes.total(T1) == 0
    assert h.cuentas.total(T1) == 0

    # AND la línea válida de T1 sigue imputándose con normalidad.
    h.imputar(tenant_id=T1, presupuesto_id=PRESU1, linea_id=LINEA1)
    assert h.movimientos.total(T1) == 1
