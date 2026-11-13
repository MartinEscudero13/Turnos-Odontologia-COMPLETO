"""Tasks 7.7–7.13 — reportes base de caja (TDD rojo primero).

Criterios (spec `caja` "Reportes base de caja", design D12):

- facturación neta por día y por medio **sobre movimientos vigentes**, con
  `fuente="movimientos_vigentes"` y sin datos personales;
- el reporte y el listado de cierres están acotados al tenant;
- `desde > hasta` ⇒ `422`;
- ocupación, ausentismo, facturación por profesional y exportación son de C-15:
  sus rutas responden `404`/`405`, nunca `200`.

Datos ficticios: T1/T2, U1 (RECEPCION), U9 (responsable de T2).
"""
from __future__ import annotations

from datetime import date

import pytest
from _caja_helpers import U1, U2, U9, HarnessCaja, actor
from conftest import T1, T2
from fastapi.testclient import TestClient

from app.routers.caja import crear_app
from app.turnos.servicio import Invalido

DIA = date(2026, 11, 9)
SIGUIENTE = date(2026, 11, 10)

RECEP = {"X-Tenant-Id": T1, "X-User-Id": U1, "X-Rol": "RECEPCION"}


def _claves(valor: object) -> set[str]:
    """Todas las claves de un JSON anidado (para verificar la allow-list)."""
    claves: set[str] = set()
    if isinstance(valor, dict):
        for clave, hijo in valor.items():
            claves.add(str(clave))
            claves |= _claves(hijo)
    elif isinstance(valor, list):
        for hijo in valor:
            claves |= _claves(hijo)
    return claves


def test_facturacion_por_medio_en_rango() -> None:
    # GIVEN T1 con movimientos vigentes en 2026-11-09 y 2026-11-10.
    h = HarnessCaja()
    h.registrar(monto=100000, medio="EFECTIVO", fecha="2026-11-09")
    h.registrar(monto=30000, medio="TRANSFERENCIA", fecha="2026-11-10")
    h.registrar(monto=20000, medio="EFECTIVO", tipo="EGRESO", fecha="2026-11-10")
    client = TestClient(crear_app(h.svc))

    # WHEN se pide el reporte del rango.
    respuesta = client.get(
        "/api/caja/reportes",
        params={"desde": "2026-11-09", "hasta": "2026-11-10"},
        headers=RECEP,
    )

    # THEN devuelve netos por día y por medio, con la fuente declarada.
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["fuente"] == "movimientos_vigentes"
    assert cuerpo["desde"] == "2026-11-09"
    assert cuerpo["hasta"] == "2026-11-10"
    por_dia = {fila["fecha"]: fila for fila in cuerpo["por_dia"]}
    assert por_dia["2026-11-09"]["efectivo"] == 100000
    assert por_dia["2026-11-10"]["efectivo"] == -20000
    assert por_dia["2026-11-10"]["transferencia"] == 30000
    assert cuerpo["totales"] == {
        "efectivo": 80000,
        "transferencia": 30000,
        "mp": 0,
        "os": 0,
    }
    assert cuerpo["cierres"] == 0

    # AND la respuesta no lleva datos personales.
    assert not {"paciente", "paciente_id", "nombre", "dni", "telefono"} & _claves(cuerpo)
    assert "Paciente Demo" not in respuesta.text
    assert "+5491" not in respuesta.text


def test_reporte_excluye_anulados() -> None:
    # GIVEN un ingreso vigente de 100000 y otro anulado de 50000 el 2026-11-09.
    h = HarnessCaja()
    h.registrar(monto=100000, medio="EFECTIVO", fecha="2026-11-09")
    anulado = h.registrar(monto=50000, medio="EFECTIVO", fecha="2026-11-09")
    h.anular(anulado.id, actor_=actor("ADMIN", user_id=U2))

    # WHEN se pide el reporte del día.
    reporte = h.svc.reporte_caja(actor(), desde="2026-11-09", hasta="2026-11-09")

    # THEN el total es 100000 y el anulado queda contado, no sumado.
    assert reporte.totales["EFECTIVO"] == 100000
    assert reporte.movimientos_anulados == 1
    [fila] = reporte.por_dia
    assert fila.totales["EFECTIVO"] == 100000
    assert fila.movimientos == 2
    assert fila.anulados == 1


def test_reporte_no_incluye_t2() -> None:
    # GIVEN T1 con 100000 y T2 con 900000 el mismo día.
    h = HarnessCaja()
    h.registrar(monto=100000, medio="EFECTIVO", fecha="2026-11-09")
    h.registrar(
        monto=900000, medio="EFECTIVO", fecha="2026-11-09", actor_=actor(tenant=T2)
    )
    client = TestClient(crear_app(h.svc))

    # WHEN un actor de T1 pide el reporte del día.
    respuesta = client.get(
        "/api/caja/reportes",
        params={"desde": "2026-11-09", "hasta": "2026-11-09"},
        headers=RECEP,
    )

    # THEN el total es 100000 y no aparece ninguna fila de T2.
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["totales"]["efectivo"] == 100000
    assert [fila["efectivo"] for fila in cuerpo["por_dia"]] == [100000]


def test_listado_de_cierres() -> None:
    # GIVEN T1 con los cierres de 2026-11-09 y 2026-11-10.
    h = HarnessCaja()
    h.cerrar_dia(fecha="2026-11-09", efectivo_contado=0, responsable_id=U2)
    h.cerrar_dia(fecha="2026-11-10", efectivo_contado=0, responsable_id=U1)
    client = TestClient(crear_app(h.svc))

    # WHEN se piden los cierres del período.
    respuesta = client.get(
        "/api/caja/cierres",
        params={"desde": "2026-11-09", "hasta": "2026-11-10"},
        headers=RECEP,
    )

    # THEN devuelve ambos con fecha, totales, contado, diferencia y responsable.
    assert respuesta.status_code == 200
    cierres = respuesta.json()
    assert [cierre["fecha"] for cierre in cierres] == ["2026-11-09", "2026-11-10"]
    assert [cierre["responsable_id"] for cierre in cierres] == [U2, U1]
    for cierre in cierres:
        assert cierre["totales"]["total_efectivo"] == 0
        assert cierre["efectivo_contado"] == 0
        assert cierre["diferencia"] == 0


def test_listado_de_cierres_no_incluye_t2() -> None:
    # GIVEN un cierre en T1 y dos en T2 del mismo período.
    h = HarnessCaja()
    h.cerrar_dia(fecha="2026-11-09", efectivo_contado=0, responsable_id=U1)
    h.cerrar(tenant_id=T2, fecha="2026-11-09", efectivo_contado=0, responsable_id=U9)
    h.cerrar(tenant_id=T2, fecha="2026-11-10", efectivo_contado=0, responsable_id=U9)
    client = TestClient(crear_app(h.svc))

    # WHEN un actor de T1 pide los cierres del período.
    respuesta = client.get(
        "/api/caja/cierres",
        params={"desde": "2026-11-09", "hasta": "2026-11-10"},
        headers=RECEP,
    )

    # THEN devuelve sólo el cierre de T1.
    assert respuesta.status_code == 200
    cierres = respuesta.json()
    assert len(cierres) == 1
    assert cierres[0]["fecha"] == "2026-11-09"
    assert cierres[0]["responsable_id"] == U1


def test_rango_invalido_422() -> None:
    # GIVEN T1 con movimientos.
    h = HarnessCaja()
    h.registrar(monto=1000, medio="EFECTIVO", fecha="2026-11-09")
    client = TestClient(crear_app(h.svc))

    # WHEN se pide un rango invertido en reportes y en cierres.
    parametros = {"desde": "2026-11-10", "hasta": "2026-11-09"}
    for ruta in ("/api/caja/reportes", "/api/caja/cierres"):
        respuesta = client.get(ruta, params=parametros, headers=RECEP)
        # THEN 422 y no calcula nada.
        assert respuesta.status_code == 422
        assert respuesta.json()["codigo"] == "RANGO_INVALIDO"

    # AND el servicio también rechaza el rango invertido.
    with pytest.raises(Invalido) as excinfo:
        h.svc.reporte_caja(actor(), desde=SIGUIENTE, hasta=DIA)
    assert excinfo.value.codigo == 422


def test_kpis_de_agenda_no_expuestos() -> None:
    # GIVEN T1 con movimientos y turnos.
    h = HarnessCaja()
    h.registrar(monto=1000, medio="EFECTIVO", fecha="2026-11-09")
    client = TestClient(crear_app(h.svc))

    # WHEN se intentan los KPIs de agenda (C-15).
    for ruta in (
        "/api/caja/reportes/ocupacion",
        "/api/caja/reportes/facturacion-profesional",
    ):
        respuesta = client.get(ruta, headers=RECEP)
        # THEN 404/405, nunca 200.
        assert respuesta.status_code in (404, 405)
        assert respuesta.status_code != 200
