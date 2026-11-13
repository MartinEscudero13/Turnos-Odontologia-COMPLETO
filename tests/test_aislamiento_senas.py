"""Tasks 11.6–11.9 y 11.16 — aislamiento multi-tenant de señas (TDD rojo primero).

Criterios (spec `senas` §Aislamiento multi-tenant de señas y pagos):

- una seña de T1 no se lee ni se muta desde T2: `404` uniforme, idéntico al de
  una seña inexistente, sin revelar la existencia;
- aplicar o devolver desde otro tenant responde `404` **sin efectos** (ningún
  movimiento, ninguna obligación, ningún cambio de estado en T1);
- el **webhook** con metadata de T2 sobre una seña de T1 ⇒ `500`, no acredita,
  no persiste en T2 y deja un log estructurado con ids y motivo (sin PHI);
- `GET /api/senas` de T1 devuelve sólo las señas de T1 (jamás mezcla tenants).

Datos ficticios: T1/T2, U1/U2 (T1), U9 (T2), TUR-1/TUR-2, "Paciente Demo".
"""
from __future__ import annotations

import logging

import pytest
from _senas_helpers import (
    PACI1,
    T1,
    TUR1,
    TUR2,
    U1,
    U2,
    HarnessSenaAplicacion,
    HarnessSenaCiclo,
    d3,
)
from conftest import T2
from fastapi.testclient import TestClient

U9 = "usuario-9"

RECEP_T1 = {"X-Tenant-Id": T1, "X-User-Id": U1, "X-Rol": "RECEPCION"}
ADMIN_T1 = {"X-Tenant-Id": T1, "X-User-Id": U2, "X-Rol": "ADMIN"}
RECEP_T2 = {"X-Tenant-Id": T2, "X-User-Id": U9, "X-Rol": "RECEPCION"}
ADMIN_T2 = {"X-Tenant-Id": T2, "X-User-Id": U9, "X-Rol": "ADMIN"}

RANGO = {"desde": "2026-11-10", "hasta": "2026-11-30"}


def _client(h: HarnessSenaAplicacion) -> TestClient:
    return h.client_interno


# ---------------------------------------------------------------------------
# 11.6 — una seña de T1 no se lee desde T2
# ---------------------------------------------------------------------------


def test_sena_de_t1_no_se_lee_desde_t2() -> None:
    # GIVEN T1 con una seña ACREDITADA de 3000.
    h = HarnessSenaAplicacion()
    sena = h.sembrar_sena(estado="ACREDITADA", monto_centavos=3000)
    client = _client(h)

    # WHEN un actor de T2 pide la seña por id y por una seña que no existe.
    ajena = client.get(f"/api/senas/{sena.id}", headers=RECEP_T2)
    inexistente = client.get("/api/senas/sena-que-no-existe", headers=RECEP_T2)

    # THEN ambos 404 idénticos, sin ningún dato de T1.
    assert ajena.status_code == 404, ajena.text
    assert inexistente.status_code == 404, inexistente.text
    assert ajena.json() == inexistente.json()
    assert sena.id not in ajena.text
    assert "3000" not in ajena.text
    assert "ACREDITADA" not in ajena.text


# ---------------------------------------------------------------------------
# 11.7 — aplicar desde otro tenant falla
# ---------------------------------------------------------------------------


def test_aplicar_desde_otro_tenant_404() -> None:
    # GIVEN T2 y una seña ACREDITADA de T1.
    h = HarnessSenaAplicacion()
    sena = h.sembrar_sena(estado="ACREDITADA")
    client = _client(h)

    # WHEN un ADMIN de T2 intenta aplicarla.
    respuesta = client.post(
        f"/api/senas/{sena.id}/aplicar",
        json={"concepto": "TRATAMIENTO"},
        headers=ADMIN_T2,
    )

    # THEN 404 y no se crea ningún movimiento en T2 ni cambia la seña de T1.
    assert respuesta.status_code == 404, respuesta.text
    assert h.sena(sena).estado == "ACREDITADA"
    assert h.sena(sena).movimiento_caja_id is None
    assert h.movimientos.total(T2) == 0
    assert h.movimientos.total(T1) == 0


# ---------------------------------------------------------------------------
# 11.8 — el webhook no cruza tenants
# ---------------------------------------------------------------------------


def test_webhook_no_cruza_tenants(caplog: pytest.LogCaptureFixture) -> None:
    # GIVEN una notificación firmada con metadata de T2 y el sena_id de T1.
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena(paciente_id="Paciente Demo")  # T1
    logger = logging.getLogger("app.senas.webhook")

    # WHEN se procesa la notificación.
    with caplog.at_level(logging.ERROR, logger="app.senas.webhook"):
        respuesta = h.notificar(sena=sena, mp_payment_id="PAG-1", tenant_id=T2)

    # THEN 500 sin acreditar, sin persistir en T2 y sin revelar la seña de T1.
    assert respuesta.status_code == 500, respuesta.text
    assert respuesta.json()["codigo"] == "PAGO_NO_ASOCIABLE"
    assert h.sena(sena).estado == "PENDIENTE"
    assert h.pagos.total(T2) == 0
    assert sena.id not in respuesta.text
    assert "Paciente Demo" not in respuesta.text

    # AND el hecho queda en el log estructurado con ids y motivo, sin PHI.
    registros = [r for r in caplog.records if r.name == logger.name]
    assert registros, "falta el log estructurado del webhook no asociable"
    registro = registros[-1]
    assert registro.codigo == "PAGO_NO_ASOCIABLE"
    assert registro.mp_payment_id == "PAG-1"
    assert registro.tenant_id == T2
    assert registro.sena_id == sena.id
    assert registro.motivo == "sena_no_encontrada_en_el_tenant"
    assert "Paciente Demo" not in caplog.text
    assert PACI1 not in caplog.text


# ---------------------------------------------------------------------------
# 11.9 — el listado no mezcla tenants
# ---------------------------------------------------------------------------


def test_listado_no_mezcla() -> None:
    # GIVEN T1 con dos señas y T2 con una en el mismo rango de fechas.
    h = HarnessSenaAplicacion()
    primera = h.sembrar_sena(turno_id=TUR1, turno_inicio=d3("2026-11-20"))
    segunda = h.sembrar_sena(turno_id=TUR2, turno_inicio=d3("2026-11-21"))
    ajena = h.sembrar_sena(
        tenant_id=T2, turno_id="turno-9", turno_inicio=d3("2026-11-20")
    )
    client = _client(h)

    # WHEN un actor de T1 pide el rango y un actor de T2 pide el mismo rango.
    de_t1 = client.get("/api/senas", params=RANGO, headers=RECEP_T1)
    de_t2 = client.get("/api/senas", params=RANGO, headers=RECEP_T2)

    # THEN cada tenant ve sólo las suyas.
    assert de_t1.status_code == 200, de_t1.text
    assert [s["sena_id"] for s in de_t1.json()] == [primera.id, segunda.id]
    assert de_t2.status_code == 200, de_t2.text
    assert [s["sena_id"] for s in de_t2.json()] == [ajena.id]
    assert ajena.id not in de_t1.text
    assert primera.id not in de_t2.text


# ---------------------------------------------------------------------------
# 11.16 — devolver desde otro tenant falla
# ---------------------------------------------------------------------------


def test_devolver_desde_otro_tenant_404() -> None:
    # GIVEN T2 con un usuario ADMIN y una seña ACREDITADA de T1.
    h = HarnessSenaAplicacion()
    sena = h.sembrar_sena(estado="ACREDITADA")
    client = _client(h)

    # WHEN el ADMIN de T2 la devuelve con un motivo válido.
    respuesta = client.post(
        f"/api/senas/{sena.id}/devolver",
        json={"motivo": "cancelación con aviso"},
        headers=ADMIN_T2,
    )

    # THEN 404, la seña de T1 sigue ACREDITADA y T2 no tiene obligación.
    assert respuesta.status_code == 404, respuesta.text
    assert h.sena(sena).estado == "ACREDITADA"
    assert h.sena(sena).motivo_devolucion is None
    assert h.auditoria.de_tenant(T2) == []
    assert all(
        entrada.accion != "SENA_DEVUELTA" for entrada in h.auditoria.entradas
    )
