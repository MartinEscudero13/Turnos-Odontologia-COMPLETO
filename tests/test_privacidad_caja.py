"""Tasks 10.9–10.10 — privacidad de caja (TDD rojo primero, RN-CL-04).

Criterios (spec `caja` "Sin PHI en caja", design D11):

- un error de dominio de caja no vuelca nombre, DNI ni teléfono del paciente;
- los logs estructurados de caja sólo llevan `tenant_id`, `movimiento_id`,
  `fecha`, `medio` y `monto`, nunca datos personales ni texto clínico.

Datos ficticios: T1, U1, PACI-1, "Paciente Demo", "+5491...".
"""
from __future__ import annotations

import logging

import pytest
from _caja_helpers import PAC1, U1, HarnessCaja
from conftest import T1
from fastapi.testclient import TestClient

from app.caja.puertos import CobroPendiente
from app.caja.servicio import ConflictoCaja
from app.routers.caja import crear_app

RECEP = {"X-Tenant-Id": T1, "X-User-Id": U1, "X-Rol": "RECEPCION"}
PHI = ("Paciente Demo", "30111222", "+5491", "Conducto Demo")


def test_error_no_vuelca_phi() -> None:
    # GIVEN un cobro pendiente de un paciente con datos personales.
    h = HarnessCaja()
    pendiente = h.imputar_tramo(monto=60000, medio=None, paciente_id=PAC1)
    assert isinstance(pendiente, CobroPendiente)
    h.cobrar(pendiente.id, medio="EFECTIVO")

    # WHEN se produce un error de dominio al cobrarlo otra vez.
    with pytest.raises(ConflictoCaja) as excinfo:
        h.cobrar(pendiente.id, medio="EFECTIVO")

    # THEN la excepción sólo lleva el código y el mensaje de dominio.
    assert excinfo.value.codigo == 409
    assert excinfo.value.codigo_dominio == "COBRO_YA_RESUELTO"
    assert "cobro pendiente" in excinfo.value.mensaje
    for dato in PHI:
        assert dato not in str(excinfo.value)
        assert dato not in excinfo.value.mensaje

    # AND el borde HTTP tampoco filtra datos personales.
    h2 = HarnessCaja()
    pendiente2 = h2.imputar_tramo(monto=60000, medio=None, paciente_id=PAC1)
    assert isinstance(pendiente2, CobroPendiente)
    client = TestClient(crear_app(h2.svc))
    assert (
        client.post(
            f"/api/caja/pendientes/{pendiente2.id}/cobrar",
            json={"medio": "EFECTIVO"},
            headers=RECEP,
        ).status_code
        in (200, 201)
    )
    respuesta = client.post(
        f"/api/caja/pendientes/{pendiente2.id}/cobrar",
        json={"medio": "EFECTIVO"},
        headers=RECEP,
    )
    assert respuesta.status_code == 409
    for dato in PHI:
        assert dato not in respuesta.text


def test_logs_solo_llevan_ids_y_montos(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    # GIVEN T1 y U1.
    h = HarnessCaja()

    # WHEN se registra un movimiento correctamente.
    movimiento = h.registrar(monto=150000, medio="EFECTIVO", fecha="2026-11-10")

    # THEN el log estructurado lleva ids, fecha, medio y monto.
    texto = caplog.text
    assert T1 in texto
    assert movimiento.id in texto
    assert "2026-11-10" in texto
    assert "EFECTIVO" in texto
    assert "150000" in texto

    # AND no lleva datos personales ni texto clínico.
    for dato in PHI:
        assert dato not in texto
