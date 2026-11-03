"""C-04 live RLS test for the catalog."""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError

URL = os.environ.get("C02_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="C02_DATABASE_URL no configurada")


def app_connection(engine: Engine, tenant: str) -> Connection:
    connection = engine.connect()
    connection.execute(text("SET ROLE turnos_app"))
    connection.execute(text("SELECT set_config('app.tenant_id', :tenant, false)"), {"tenant": tenant})
    return connection


def test_catalog_is_tenant_scoped() -> None:
    assert URL is not None
    engine = create_engine(URL, future=True)
    t1, t2 = str(uuid.uuid4()), str(uuid.uuid4())
    s1, s2 = str(uuid.uuid4()), str(uuid.uuid4())
    with engine.connect() as owner:
        tx = owner.begin()
        try:
            owner.execute(
                text("INSERT INTO tenants (id, nombre, slug) VALUES (:id, :nombre, :slug)"),
                [
                    {"id": t1, "nombre": "T1", "slug": f"c04-{t1[:8]}"},
                    {"id": t2, "nombre": "T2", "slug": f"c04-{t2[:8]}"},
                ],
            )
            owner.execute(
                text(
                    "INSERT INTO sillones (id, tenant_id, nombre) "
                    "VALUES (:id, :tenant, :nombre)"
                ),
                [
                    {"id": s1, "tenant": t1, "nombre": "Sillón T1"},
                    {"id": s2, "tenant": t2, "nombre": "Sillón T2"},
                ],
            )
            tx.commit()
        except Exception:
            tx.rollback()
            raise

    try:
        with app_connection(engine, t1) as connection:
            names = connection.execute(text("SELECT nombre FROM sillones")).scalars().all()
            assert names == ["Sillón T1"]
            with pytest.raises(DBAPIError):
                connection.execute(
                    text("INSERT INTO sillones (tenant_id, nombre) VALUES (:tenant, 'Intruso')"),
                    {"tenant": t2},
                )
    finally:
        with engine.connect() as owner:
            tx = owner.begin()
            owner.execute(text("DELETE FROM tenants WHERE id = ANY(:ids)"), {"ids": [t1, t2]})
            tx.commit()
        engine.dispose()
