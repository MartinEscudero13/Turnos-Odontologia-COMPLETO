"""Tasks 8.1–8.12 — RBAC de caja (TDD rojo primero).

Criterios (spec `caja` y `cierre-caja`, design D10):

- `RECEPCION` y `ADMIN` registran movimientos, cobran pendientes y cierran el día;
- `ADMIN` es el único que anula (C10-OQ-9) y la exportación no existe en C-10
  (vive en C-15, es de ADMIN);
- `ODONTOLOGO` sólo lee;
- una identidad de paciente no tiene sesión ⇒ `401` (nunca `403`);
- un rol interno sin permiso ⇒ `403` y nada persistido.

Datos ficticios: T1, U1 (RECEPCION), U2 (ADMIN), U3 (ODONTOLOGO), PACI-1.
"""
from __future__ import annotations

from datetime import date

from _caja_helpers import PAC1, U1, U2, U3, HarnessCaja
from conftest import T1
from fastapi.testclient import TestClient

from app.caja.puertos import CobroPendiente
from app.routers.caja import crear_app
from app.turnos.servicio import Actor

FECHA = date(2026, 11, 10)

RECEP = {"X-Tenant-Id": T1, "X-User-Id": U1, "X-Rol": "RECEPCION"}
ADMIN = {"X-Tenant-Id": T1, "X-User-Id": U2, "X-Rol": "ADMIN"}
ODONTO = {"X-Tenant-Id": T1, "X-User-Id": U3, "X-Rol": "ODONTOLOGO"}
PACIENTE = {"X-Tenant-Id": T1, "X-User-Id": PAC1, "X-Rol": "PACIENTE"}


def _client(h: HarnessCaja) -> TestClient:
    return TestClient(crear_app(h.svc))


def _pasado_hoy(h: HarnessCaja) -> None:
    """El día operativo del reloj es el 2026-11-10."""
    assert h.ahora.date() == FECHA


def test_recepcion_registra_y_cobra() -> None:
    # GIVEN T1 con U1 de recepción y un cobro pendiente.
    h = HarnessCaja()
    _pasado_hoy(h)
    pendiente = h.imputar_tramo(monto=60000, medio=None)
    assert isinstance(pendiente, CobroPendiente)
    client = _client(h)

    # WHEN U1 registra un ingreso y cobra el pendiente.
    alta = client.post(
        "/api/caja/movimientos",
        json={"monto": 150000, "medio": "EFECTIVO", "fecha": "2026-11-10"},
        headers=RECEP,
    )
    cobro = client.post(
        f"/api/caja/pendientes/{pendiente.id}/cobrar",
        json={"medio": "TRANSFERENCIA"},
        headers=RECEP,
    )

    # THEN ambas operaciones quedan registradas con usuario_id=U1.
    assert alta.status_code == 201
    assert alta.json()["usuario_id"] == U1
    assert cobro.status_code in (200, 201)
    assert cobro.json()["movimiento"]["usuario_id"] == U1
    assert cobro.json()["pendiente"]["id"] == pendiente.id
    assert cobro.json()["pendiente"]["resuelto_en"] is not None


def test_odontologo_lee_pero_no_escribe() -> None:
    # GIVEN T1 con el odontólogo U3.
    h = HarnessCaja()
    client = _client(h)

    # WHEN U3 consulta los movimientos del día y luego intenta registrar uno.
    lectura = client.get(
        "/api/caja/movimientos", params={"fecha": "2026-11-10"}, headers=ODONTO
    )
    alta = client.post(
        "/api/caja/movimientos",
        json={"monto": 150000, "medio": "EFECTIVO", "fecha": "2026-11-10"},
        headers=ODONTO,
    )

    # THEN la consulta responde 200 y el alta 403 sin persistir nada.
    assert lectura.status_code == 200
    assert alta.status_code == 403
    assert h.movimientos.total(T1) == 0


def test_recepcion_no_anula_403() -> None:
    # GIVEN T1 con un movimiento vigente y U1 de recepción.
    h = HarnessCaja()
    movimiento = h.registrar(monto=150000, medio="EFECTIVO", fecha="2026-11-10")
    client = _client(h)

    # WHEN U1 intenta anular con un motivo válido.
    respuesta = client.post(
        f"/api/caja/movimientos/{movimiento.id}/anular",
        json={"motivo": "cobro duplicado"},
        headers=RECEP,
    )

    # THEN 403: sigue vigente y no hay compensatorio ni ajuste.
    assert respuesta.status_code == 403
    vigente = h.movimientos.obtener(tenant_id=T1, movimiento_id=movimiento.id)
    assert vigente is not None and vigente.anulado is False
    assert len(h.movimientos.listar_por_fecha(tenant_id=T1, fecha=FECHA)) == 1
    assert h.ajustes.total(T1) == 0


def test_admin_anula_con_motivo() -> None:
    # GIVEN T1 con un movimiento vigente y U2 de ADMIN.
    h = HarnessCaja()
    movimiento = h.registrar(monto=150000, medio="EFECTIVO", fecha="2026-11-10")
    client = _client(h)

    # WHEN U2 anula con un motivo válido.
    respuesta = client.post(
        f"/api/caja/movimientos/{movimiento.id}/anular",
        json={"motivo": "cobro duplicado"},
        headers=ADMIN,
    )

    # THEN 200 y la anulación queda registrada con anulado_por=U2.
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["anulado"] is True
    assert cuerpo["anulado_por"] == U2
    assert cuerpo["motivo_anulacion"] == "cobro duplicado"


def test_recepcion_lee_reportes() -> None:
    # GIVEN T1 con movimientos y U1 de recepción.
    h = HarnessCaja()
    h.registrar(monto=100000, medio="EFECTIVO", fecha="2026-11-10")
    client = _client(h)

    # WHEN U1 pide reportes y cierres.
    reporte = client.get(
        "/api/caja/reportes",
        params={"desde": "2026-11-09", "hasta": "2026-11-10"},
        headers=RECEP,
    )
    cierres = client.get(
        "/api/caja/cierres",
        params={"desde": "2026-11-09", "hasta": "2026-11-10"},
        headers=RECEP,
    )

    # THEN ambas responden 200 con datos de T1.
    assert reporte.status_code == 200
    assert reporte.json()["totales"]["efectivo"] == 100000
    assert cierres.status_code == 200
    assert cierres.json() == []


def test_exportacion_de_caja_no_existe() -> None:
    # GIVEN T1 con U1 de recepción y U2 ADMIN.
    h = HarnessCaja()
    client = _client(h)

    # WHEN cualquiera pide la exportación de caja (C-15, ADMIN).
    for headers in (RECEP, ADMIN):
        respuesta = client.get("/api/caja/reportes/export", headers=headers)
        # THEN 404/405, nunca 200.
        assert respuesta.status_code in (404, 405)
        assert respuesta.status_code != 200


def test_paciente_sin_sesion_401() -> None:
    # GIVEN T1 con movimientos del día.
    h = HarnessCaja()
    h.registrar(monto=100000, medio="EFECTIVO", fecha="2026-11-10")
    client = _client(h)

    # WHEN una petición con identidad de paciente lee o registra movimientos.
    lectura = client.get(
        "/api/caja/movimientos", params={"fecha": "2026-11-10"}, headers=PACIENTE
    )
    alta = client.post(
        "/api/caja/movimientos",
        json={"monto": 150000, "medio": "EFECTIVO", "fecha": "2026-11-10"},
        headers=PACIENTE,
    )

    # THEN 401 (no 403), sin exponer ni persistir nada.
    assert lectura.status_code == 401
    assert alta.status_code == 401
    assert h.movimientos.total(T1) == 1


def test_recepcion_cierra() -> None:
    # GIVEN T1 con U1 de recepción y el 2026-11-10 sin cierre.
    h = HarnessCaja()
    client = _client(h)

    # WHEN U1 cierra el día.
    respuesta = client.post(
        "/api/caja/cierre",
        json={"efectivo_contado": 0, "responsable_id": U1},
        headers=RECEP,
    )

    # THEN 201 con el cierre creado.
    assert respuesta.status_code == 201
    assert respuesta.json()["responsable_id"] == U1
    assert respuesta.json()["fecha"] == "2026-11-10"


def test_admin_cierra() -> None:
    # GIVEN T1 con U2 de ADMIN y el 2026-11-10 sin cierre.
    h = HarnessCaja()
    client = _client(h)

    # WHEN U2 cierra el día con responsable U2.
    respuesta = client.post(
        "/api/caja/cierre",
        json={"efectivo_contado": 0, "responsable_id": U2},
        headers=ADMIN,
    )

    # THEN 201 con responsable_id=U2.
    assert respuesta.status_code == 201
    assert respuesta.json()["responsable_id"] == U2


def test_odontologo_no_cierra_403() -> None:
    # GIVEN T1 con el odontólogo U3 y el día sin cierre.
    h = HarnessCaja()
    client = _client(h)

    # WHEN U3 intenta cerrar el día.
    respuesta = client.post(
        "/api/caja/cierre",
        json={"efectivo_contado": 0, "responsable_id": U3},
        headers=ODONTO,
    )

    # THEN 403, el día sigue abierto y no se persiste cierre.
    assert respuesta.status_code == 403
    assert h.cierres.total(T1) == 0
    assert (
        h.svc.estado_dia(
            Actor(tenant_id=T1, rol="ODONTOLOGO", user_id=U3), fecha=FECHA
        ).estado
        == "abierto"
    )


def test_odontologo_lee_cierre() -> None:
    # GIVEN T1 con el cierre del 2026-11-10.
    h = HarnessCaja()
    h.registrar(monto=150000, medio="EFECTIVO", fecha="2026-11-10")
    client = _client(h)
    assert (
        client.post(
            "/api/caja/cierre",
            json={"efectivo_contado": 150000, "responsable_id": U1},
            headers=RECEP,
        ).status_code
        == 201
    )

    # WHEN U3 consulta el cierre y el estado del día.
    cierre = client.get(
        "/api/caja/cierre", params={"fecha": "2026-11-10"}, headers=ODONTO
    )
    estado = client.get(
        "/api/caja/cierre/estado", params={"fecha": "2026-11-10"}, headers=ODONTO
    )
    cierre_recep = client.get(
        "/api/caja/cierre", params={"fecha": "2026-11-10"}, headers=RECEP
    )

    # THEN ambas responden 200 con los mismos totales que ve recepción.
    assert cierre.status_code == 200
    assert estado.status_code == 200
    assert cierre.json() == cierre_recep.json()
    assert estado.json()["estado"] == "cerrado"
    assert estado.json()["cierre"]["totales"]["total_efectivo"] == 150000


def test_paciente_no_accede_al_cierre_401() -> None:
    # GIVEN T1 con el cierre del 2026-11-10.
    h = HarnessCaja()
    client = _client(h)
    h.cerrar_dia(fecha="2026-11-10", efectivo_contado=0, responsable_id=U1)

    # WHEN una petición con identidad de paciente consulta o crea un cierre.
    lectura = client.get(
        "/api/caja/cierre", params={"fecha": "2026-11-10"}, headers=PACIENTE
    )
    estado = client.get(
        "/api/caja/cierre/estado", params={"fecha": "2026-11-10"}, headers=PACIENTE
    )
    alta = client.post(
        "/api/caja/cierre",
        json={"efectivo_contado": 0, "responsable_id": U1},
        headers=PACIENTE,
    )

    # THEN 401 y no expone ni registra nada.
    assert lectura.status_code == 401
    assert estado.status_code == 401
    assert alta.status_code == 401
    assert h.cierres.total(T1) == 1
