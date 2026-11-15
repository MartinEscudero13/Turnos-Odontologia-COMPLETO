"""Wiring PostgreSQL real de C-12 para los tests de RLS y repositorios.

Se salta todo sin `C02_DATABASE_URL`. Datos ficticios (RN-GL-03): tenant,
prestación de `10000` centavos, paciente, profesional, sillón y un turno
`PRESENTE` del `2026-11-20T10:00:00-03:00`.
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
AHORA = datetime(2026, 11, 15, 9, 0, tzinfo=TZ)
INICIO = datetime(2026, 11, 20, 10, 0, tzinfo=TZ)
PRECIO = 10000


def motor() -> Engine:
    assert PG_URL is not None
    return create_engine(PG_URL, future=True)


def _telefono(semilla: str) -> str:
    digitos = int(semilla.replace("-", ""), 16) % 10**10
    return f"+5491{digitos:010d}"


def sembrar(conn: Connection, *, prefijo: str) -> dict[str, str]:
    """Tenant + prestación + paciente + profesional + sillón + turno PRESENTE."""
    ids = {
        clave: str(uuid.uuid4())
        for clave in (
            "tenant",
            "prestacion",
            "paciente",
            "profesional",
            "sillon",
            "turno",
        )
    }
    conn.execute(
        text("INSERT INTO tenants (id, nombre, slug) VALUES (:id, 'C12 demo', :slug)"),
        {"id": ids["tenant"], "slug": f"{prefijo}-{ids['tenant'][:8]}"},
    )
    conn.execute(
        text(
            "INSERT INTO prestaciones"
            " (id, tenant_id, nombre, duracion_min, precio_base)"
            " VALUES (:id, :t, :nombre, 30, :precio)"
        ),
        {
            "id": ids["prestacion"],
            "t": ids["tenant"],
            "nombre": f"Consulta {prefijo}-{ids['prestacion'][:8]}",
            "precio": PRECIO,
        },
    )
    conn.execute(
        text(
            "INSERT INTO pacientes (id, tenant_id, nombre, telefono)"
            " VALUES (:id, :t, 'Paciente Demo', :tel)"
        ),
        {"id": ids["paciente"], "t": ids["tenant"], "tel": _telefono(ids["paciente"])},
    )
    conn.execute(
        text(
            "INSERT INTO profesionales (id, tenant_id, nombre, especialidad)"
            " VALUES (:id, :t, 'Odontólogo Demo', 'Odontología')"
        ),
        {"id": ids["profesional"], "t": ids["tenant"]},
    )
    conn.execute(
        text(
            "INSERT INTO sillones (id, tenant_id, nombre)"
            " VALUES (:id, :t, :nombre)"
        ),
        {
            "id": ids["sillon"],
            "t": ids["tenant"],
            "nombre": f"Sillón {prefijo}-{ids['sillon'][:8]}",
        },
    )
    conn.execute(
        text(
            "INSERT INTO turnos"
            " (id, tenant_id, profesional_id, sillon_id, paciente_id, prestacion_id,"
            "  inicio, fin, estado, origen)"
            " VALUES (:id, :t, :prof, :sil, :pac, :prest, :inicio, :fin, 'PRESENTE', 'RECEPCION')"
        ),
        {
            "id": ids["turno"],
            "t": ids["tenant"],
            "prof": ids["profesional"],
            "sil": ids["sillon"],
            "pac": ids["paciente"],
            "prest": ids["prestacion"],
            "inicio": INICIO,
            "fin": INICIO + timedelta(minutes=30),
        },
    )
    return ids
