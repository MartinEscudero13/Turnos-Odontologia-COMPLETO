"""Task 11.1 — regresión de C-03/C-05/C-09 con la caja de C-10 (TDD rojo primero).

Criterios (tasks 11.1):

- la migración 008 sólo agrega las tablas de caja: no toca `usuarios`, `turnos`,
  `presupuestos`, `presupuesto_lineas` ni `aceptaciones` (M7);
- el gate de consentimiento de C-03 y el anti-solape de C-05 siguen intactos;
- la aceptación de C-09 con `medio=NULL` sigue respondiendo `200` porque ahora
  existe el cobro pendiente que C-10 completa al cobrar (D5).

Datos ficticios: T1, U1 (RECEPCION), PACI-1, "Conducto Demo".
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _caja_helpers import U1, HarnessCaja
from _odontograma_helpers import PAC1, PREST1
from _presupuesto_helpers import HarnessPresupuesto, crear_borrador, presupuesto_vigente
from conftest import T1
from fastapi.testclient import TestClient

from app.routers.presupuesto import crear_app as crear_app_presupuesto
from app.turnos.servicio import Actor, ConflictoSolape, ServicioTurnos

TZ = timezone(timedelta(hours=-3))
MIG = (
    Path(__file__).resolve().parent.parent
    / "backend"
    / "alembic"
    / "versions"
    / "008_caja_cierre_diario.py"
)
RECEP = {"X-Tenant-Id": T1, "X-User-Id": U1, "X-Rol": "RECEPCION"}


def test_c03_c05_c09_siguen_en_verde() -> None:
    # --- 008 sólo agrega las tablas de caja y no toca aceptaciones -----
    sql = MIG.read_text(encoding="utf-8")
    tablas = set(re.findall(r"CREATE TABLE ([a-z_]+)", sql))
    assert tablas == {
        "movimientos_caja",
        "cierres_diarios",
        "cobros_pendientes",
        "ajustes_post_cierre",
        "cuentas_por_cobrar_os",
    }
    for tabla in (
        "usuarios",
        "turnos",
        "presupuestos",
        "presupuesto_lineas",
        "aceptaciones",
    ):
        assert f"ALTER TABLE {tabla}" not in sql
    assert "aceptaciones ADD COLUMN" not in sql
    assert "column('medio'" not in sql

    # --- el gate de consentimiento de C-03 sigue vigente ---------------
    hp = HarnessPresupuesto()
    borrador = crear_borrador(hp)
    client = TestClient(crear_app_presupuesto(hp.svc))
    sin_consentimiento = client.post(
        f"/api/presupuestos/{borrador.id}/lineas",
        json={"prestacion_id": PREST1, "monto": 100000, "pieza_fdi": 36},
        headers=RECEP,
    )
    assert sin_consentimiento.status_code == 409
    assert sin_consentimiento.json()["detalle"] == "CONSENTIMIENTO_REQUERIDO"
    assert hp.lineas.listar(tenant_id=T1, presupuesto_id=borrador.id) == []

    # --- el anti-solape de C-05 sigue vigente --------------------------
    turnos = ServicioTurnos()
    actor = Actor(tenant_id=T1, rol="RECEPCION", user_id=U1)
    inicio = datetime(2026, 11, 10, 9, 0, tzinfo=TZ)
    turnos.crear(
        actor,
        profesional_id="profesional-1",
        sillon_id="sillon-1",
        paciente_id=PAC1,
        prestacion_id=PREST1,
        inicio=inicio,
        duracion_min=30,
    )
    try:
        turnos.crear(
            actor,
            profesional_id="profesional-1",
            sillon_id="sillon-1",
            paciente_id=PAC1,
            prestacion_id=PREST1,
            inicio=inicio,
            duracion_min=30,
        )
    except ConflictoSolape as exc:
        assert exc.codigo == 409
    else:  # pragma: no cover - el anti-solape debe rechazar el segundo turno
        raise AssertionError("el anti-solape de C-05 no rechazó el turno superpuesto")

    # --- C-09 acepta con medio=NULL y C-10 crea el cobro pendiente ------
    caja = HarnessCaja()
    hp2 = HarnessPresupuesto(imputacion=caja.adaptador)
    presupuesto_id, (linea_id,) = presupuesto_vigente(hp2)
    caja.lineas_presupuesto.agregar(T1, presupuesto_id, linea_id)
    client_c09 = TestClient(crear_app_presupuesto(hp2.svc))

    respuesta = client_c09.post(
        f"/api/presupuestos/{presupuesto_id}/aceptar",
        json={
            "linea_id": linea_id,
            "acepta": True,
            "canal": "CONSULTORIO",
            "medio": None,
        },
        headers=RECEP,
    )

    # THEN 200 (no 503), un pendiente y ningún movimiento todavía.
    assert respuesta.status_code == 200
    assert hp2.aceptaciones.total(T1) == 1
    assert caja.pendientes.total(T1) == 1
    assert caja.movimientos.total(T1) == 0
    [pendiente] = caja.pendientes.listar(tenant_id=T1)
    assert pendiente.linea_id == linea_id
