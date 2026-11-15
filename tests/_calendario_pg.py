"""Wiring PostgreSQL real de C-14 para RLS y repositorios."""
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


def motor() -> Engine:
    assert PG_URL is not None
    return create_engine(PG_URL, future=True)


def sembrar(conn: Connection, *, prefijo: str) -> dict[str, str]:
    """Tenant + profesional ficticios."""
    ids = {"tenant": str(uuid.uuid4()), "profesional": str(uuid.uuid4())}
    conn.execute(
        text("INSERT INTO tenants (id, nombre, slug) VALUES (:id, 'C14 demo', :slug)"),
        {"id": ids["tenant"], "slug": f"{prefijo}-{ids['tenant'][:8]}"},
    )
    conn.execute(
        text(
            "INSERT INTO profesionales (id, tenant_id, nombre, especialidad)"
            " VALUES (:id, :t, 'Odontólogo Demo', 'Odontología')"
        ),
        {"id": ids["profesional"], "t": ids["tenant"]},
    )
    return ids
