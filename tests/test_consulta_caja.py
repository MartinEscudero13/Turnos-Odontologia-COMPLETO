"""Tasks 7.1–7.6 — consulta diaria de caja (TDD rojo primero).

Criterios (spec `caja` "Consulta diaria con totales vigentes y del cierre",
design D3/D4/H6):

- `GET /api/caja/movimientos?fecha=` devuelve movimientos, cobros pendientes,
  `totales_vigentes` (excluye anulados), `totales_cierre` (`null` si abierto) y
  `difieren_del_cierre`.
- Un día cerrado con anulación posterior informa **las dos cifras** y el cierre
  nunca se recalcula.
- La fecha es obligatoria (`422` si falta) y es un día operativo.

Datos ficticios: T1, U1 (RECEPCION), U2 (ADMIN), montos en centavos.
"""
from __future__ import annotations

from datetime import date

import pytest
from _caja_helpers import U1, U2, HarnessCaja, actor, d3
from conftest import T1
from fastapi.testclient import TestClient

from app.routers.caja import crear_app
from app.turnos.servicio import Invalido

FECHA = date(2026, 11, 10)
SIGUIENTE = date(2026, 11, 11)
VACIO = date(2026, 11, 8)

RECEP = {"X-Tenant-Id": T1, "X-User-Id": U1, "X-Rol": "RECEPCION"}


def test_totales_por_medio_del_dia() -> None:
    # GIVEN dos ingresos en efectivo, un egreso de efectivo, MP y OS del día.
    h = HarnessCaja()
    h.registrar(monto=100000, medio="EFECTIVO", fecha="2026-11-10")
    h.registrar(monto=50000, medio="EFECTIVO", fecha="2026-11-10")
    h.registrar(monto=20000, medio="EFECTIVO", tipo="EGRESO", fecha="2026-11-10")
    h.registrar(monto=30000, medio="MP", fecha="2026-11-10")
    h.registrar(monto=40000, medio="OS", fecha="2026-11-10")

    # WHEN se consulta el día por HTTP.
    client = TestClient(crear_app(h.svc))
    respuesta = client.get("/api/caja/movimientos", params={"fecha": "2026-11-10"}, headers=RECEP)

    # THEN los cuatro totales son los netos esperados.
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["fecha"] == "2026-11-10"
    assert cuerpo["estado"] == "abierto"
    assert cuerpo["totales_vigentes"] == {
        "efectivo": 130000,
        "transferencia": 0,
        "mp": 30000,
        "os": 40000,
    }
    assert cuerpo["totales_cierre"] is None
    assert cuerpo["difieren_del_cierre"] is False
    assert len(cuerpo["movimientos"]) == 5


def test_anulados_no_suman() -> None:
    # GIVEN un ingreso vigente de 100000 y otro de 50000 ya anulado.
    h = HarnessCaja()
    vigente = h.registrar(monto=100000, medio="EFECTIVO", fecha="2026-11-10")
    anulado = h.registrar(monto=50000, medio="EFECTIVO", fecha="2026-11-10")
    h.anular(anulado.id, actor_=actor("ADMIN", user_id=U2))

    # WHEN se consultan los totales del día.
    consulta = h.svc.consultar_dia(actor(), fecha=FECHA)

    # THEN sólo suma el vigente y el anulado se lista como anulado.
    assert consulta.totales_vigentes["EFECTIVO"] == 100000
    por_id = {movimiento.id: movimiento for movimiento in consulta.movimientos}
    assert por_id[vigente.id].anulado is False
    assert por_id[anulado.id].anulado is True
    assert por_id[anulado.id].monto == 50000


def test_dia_sin_movimientos_totales_cero() -> None:
    # GIVEN T1 sin movimientos el 2026-11-08.
    h = HarnessCaja()

    # WHEN se consulta ese día.
    consulta = h.svc.consultar_dia(actor(), fecha=VACIO)

    # THEN todo está en cero y el día está abierto.
    assert consulta.totales_vigentes == {
        "EFECTIVO": 0,
        "TRANSFERENCIA": 0,
        "MP": 0,
        "OS": 0,
    }
    assert consulta.movimientos == []
    assert consulta.pendientes == []
    assert consulta.ajustes == []
    assert consulta.estado == "abierto"
    assert consulta.totales_cierre is None
    assert consulta.difieren_del_cierre is False


def test_consulta_informa_estado_cierre() -> None:
    # GIVEN el 2026-11-10 cerrado y el 2026-11-11 sin cierre.
    h = HarnessCaja()
    h.registrar(monto=150000, medio="EFECTIVO", fecha="2026-11-10")
    cierre = h.cerrar_dia(fecha="2026-11-10", efectivo_contado=150000, responsable_id=U2)

    # WHEN se consultan ambos días.
    cerrado = h.svc.consultar_dia(actor(), fecha=FECHA)
    abierto = h.svc.consultar_dia(actor(), fecha=SIGUIENTE)

    # THEN el cerrado informa su snapshot y el abierto `null`.
    assert cerrado.estado == "cerrado"
    assert cerrado.totales_cierre is not None
    assert cerrado.totales_cierre.id == cierre.id
    assert cerrado.totales_cierre.total_efectivo == 150000
    assert cerrado.difieren_del_cierre is False
    assert abierto.estado == "abierto"
    assert abierto.totales_cierre is None


def test_dia_cerrado_con_anulacion_posterior_difiere() -> None:
    # GIVEN el 2026-11-10 cerrado con total_efectivo=150000 y un ingreso de
    # 150000 anulado el 2026-11-11 (H6).
    h = HarnessCaja()
    movimiento = h.registrar(monto=150000, medio="EFECTIVO", fecha="2026-11-10")
    cierre = h.cerrar_dia(fecha="2026-11-10", efectivo_contado=150000, responsable_id=U2)
    h.ahora = d3("2026-11-11", hora=9)
    h.anular(movimiento.id, actor_=actor("ADMIN", user_id=U2))

    # WHEN se consultan los movimientos del 2026-11-10.
    consulta = h.svc.consultar_dia(actor(), fecha=FECHA)

    # THEN informa las dos cifras y el cierre sigue intacto.
    assert consulta.totales_vigentes["EFECTIVO"] == 0
    assert consulta.totales_cierre is not None
    assert consulta.totales_cierre.total_efectivo == 150000
    assert consulta.totales_cierre.efectivo_contado == 150000
    assert consulta.totales_cierre.diferencia == 0
    assert consulta.totales_cierre.cerrado_at == cierre.cerrado_at
    assert consulta.difieren_del_cierre is True
    # El ajuste de la anulación posterior queda consultable en el día.
    assert len(consulta.ajustes) == 1
    assert consulta.ajustes[0].tipo == "AJUSTE_ANULACION"

    # AND el cierre persistido no se recalculó.
    persistido = h.cierres.obtener(tenant_id=T1, fecha=FECHA)
    assert persistido == cierre


def test_fecha_obligatoria_422() -> None:
    # GIVEN T1 con movimientos.
    h = HarnessCaja()
    h.registrar(monto=1000, medio="EFECTIVO", fecha="2026-11-10")
    client = TestClient(crear_app(h.svc))

    # WHEN se llama sin `fecha`.
    respuesta = client.get("/api/caja/movimientos", headers=RECEP)

    # THEN 422 y no devuelve movimientos de ningún día.
    assert respuesta.status_code == 422
    assert "movimientos" not in respuesta.json()

    # AND una fecha mal formada también es 422, nunca 500.
    invalida = client.get(
        "/api/caja/movimientos", params={"fecha": "10/11/2026"}, headers=RECEP
    )
    assert invalida.status_code == 422

    # AND el servicio exige la fecha aunque se lo invoque directo.
    with pytest.raises(Invalido) as excinfo:
        h.svc.consultar_dia(actor(), fecha=None)
    assert excinfo.value.codigo == 422
