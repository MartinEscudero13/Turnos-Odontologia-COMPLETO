"""Utilidades de PostgreSQL real para los tests de aceptación — C-09 (no recolectado).

Se salta todo sin `C02_DATABASE_URL`. Datos ficticios: "Paciente Demo",
"Conducto Demo", `P1`/`S1`, un turno y un presupuesto `VIGENTE` de una línea.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

PG_URL = os.environ.get("C02_DATABASE_URL")
requiere_pg = pytest.mark.skipif(not PG_URL, reason="C02_DATABASE_URL no configurada")

TZ = timezone(timedelta(hours=-3))
AHORA = datetime(2026, 11, 10, 10, 0, tzinfo=TZ)

CONSULTA_TURNOS = text(
    "SELECT id, paciente_id, inicio, fin, estado, sobreturno"
    " FROM turnos WHERE tenant_id = :t ORDER BY id"
)


def motor() -> Engine:
    assert PG_URL is not None
    return create_engine(PG_URL, future=True)


def sembrar_base(conn: Connection) -> dict[str, str]:
    """Crea tenant/paciente/prestación/presupuesto/línea ficticios y un turno."""
    ids = {
        clave: str(uuid.uuid4())
        for clave in (
            "tenant",
            "paciente",
            "profesional",
            "sillon",
            "prestacion",
            "presupuesto",
            "linea",
            "turno",
        )
    }
    conn.execute(
        text("INSERT INTO tenants (id, nombre, slug) VALUES (:id, 'T7', :slug)"),
        {"id": ids["tenant"], "slug": f"c09a-{ids['tenant'][:8]}"},
    )
    conn.execute(
        text(
            "INSERT INTO pacientes (id, tenant_id, nombre, telefono)"
            " VALUES (:id, :t, 'Paciente Demo', :tel)"
        ),
        {
            "id": ids["paciente"],
            "t": ids["tenant"],
            # E.164 ficticio (el CHECK de 002 exige `+` y 8–15 dígitos).
            "tel": f"+5491{int(ids['paciente'].replace('-', ''), 16) % 10**10:010d}",
        },
    )
    conn.execute(
        text(
            "INSERT INTO prestaciones (id, tenant_id, nombre, duracion_min, precio_base)"
            " VALUES (:id, :t, 'Conducto Demo', 30, 150000)"
        ),
        {"id": ids["prestacion"], "t": ids["tenant"]},
    )
    conn.execute(
        text(
            "INSERT INTO presupuestos (id, tenant_id, paciente_id, estado)"
            " VALUES (:id, :t, :p, 'VIGENTE')"
        ),
        {"id": ids["presupuesto"], "t": ids["tenant"], "p": ids["paciente"]},
    )
    conn.execute(
        text(
            "INSERT INTO presupuesto_lineas"
            " (id, tenant_id, presupuesto_id, prestacion_id, monto, cobertura_os, a_cargo_paciente)"
            " VALUES (:id, :t, :pr, :pres, 100000, 40000, 60000)"
        ),
        {
            "id": ids["linea"],
            "t": ids["tenant"],
            "pr": ids["presupuesto"],
            "pres": ids["prestacion"],
        },
    )
    conn.execute(
        text(
            "INSERT INTO turnos"
            " (id, tenant_id, profesional_id, sillon_id, paciente_id, prestacion_id, inicio, fin)"
            " VALUES (:id, :t, :prof, :sil, :pac, :pres, :inicio, :fin)"
        ),
        {
            "id": ids["turno"],
            "t": ids["tenant"],
            "prof": ids["profesional"],
            "sil": ids["sillon"],
            "pac": ids["paciente"],
            "pres": ids["prestacion"],
            "inicio": AHORA,
            "fin": AHORA + timedelta(minutes=30),
        },
    )
    return ids


def limpiar(engine: Engine, ids: dict[str, str]) -> None:
    """Borra el tenant sembrado (cascade) y libera el engine."""
    if ids:
        with engine.connect() as owner:
            tx = owner.begin()
            owner.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": ids["tenant"]})
            tx.commit()
    engine.dispose()
