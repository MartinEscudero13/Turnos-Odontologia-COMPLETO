"""Task 6.12 — el paciente no accede al sistema en v1 (D13 / C09-OQ-10).

No hay login, JWT ni link público de paciente: una petición con identidad de
paciente no tiene sesión interna que la autentique y responde `401` (nunca
`403`), sin exponer hallazgos ni presupuesto y sin registrar ni imputar nada.
"""
from __future__ import annotations

from _odontograma_helpers import PAC1, HarnessOdontograma
from _presupuesto_helpers import HarnessPresupuesto, crear_borrador
from conftest import T1
from fastapi.testclient import TestClient

from app.routers.odontograma import crear_app as crear_app_odontograma
from app.routers.presupuesto import crear_app as crear_app_presupuesto

PACIENTE = {"X-Tenant-Id": T1, "X-User-Id": PAC1, "X-Rol": "PACIENTE"}


def test_paciente_sin_sesion_401_en_odontograma_y_presupuesto():
    odontograma = HarnessOdontograma()
    odontograma.dar_consentimiento(PAC1)
    odonto_client = TestClient(crear_app_odontograma(odontograma.svc))

    lectura = odonto_client.get(
        "/api/odontograma", params={"paciente_id": PAC1}, headers=PACIENTE
    )
    assert lectura.status_code == 401
    assert "hallazgo" not in lectura.text.lower()

    escritura = odonto_client.post(
        "/api/odontograma",
        json={
            "paciente_id": PAC1,
            "pieza_fdi": 36,
            "hallazgo": "caries oclusal",
            "fecha": "2026-11-10T10:00:00-03:00",
            "profesional_id": "profesional-1",
        },
        headers=PACIENTE,
    )
    assert escritura.status_code == 401
    assert odontograma.hallazgos.total(T1) == 0

    presupuesto_harness = HarnessPresupuesto()
    presupuesto = crear_borrador(presupuesto_harness)
    presu_client = TestClient(crear_app_presupuesto(presupuesto_harness.svc))

    consulta = presu_client.get(
        f"/api/presupuestos/{presupuesto.id}", headers=PACIENTE
    )
    assert consulta.status_code == 401
    assert "100000" not in consulta.text

    aceptacion = presu_client.post(
        f"/api/presupuestos/{presupuesto.id}/aceptar",
        json={"linea_id": "linea-1", "acepta": True, "canal": "LINK"},
        headers=PACIENTE,
    )
    assert aceptacion.status_code == 401
    assert presupuesto_harness.aceptaciones.total(T1) == 0
    assert presupuesto_harness.imputacion.llamadas_caja == []
    assert presupuesto_harness.imputacion.llamadas_agenda == []
