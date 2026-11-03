"""C-03 live RLS test for refresh tokens."""
from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

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


def test_refresh_tokens_are_tenant_scoped() -> None:
    assert URL is not None
    engine = create_engine(URL, future=True)
    t1, t2 = str(uuid.uuid4()), str(uuid.uuid4())
    u1, u2 = str(uuid.uuid4()), str(uuid.uuid4())
    with engine.connect() as owner:
        tx = owner.begin()
        try:
            owner.execute(
                text("INSERT INTO tenants (id, nombre, slug) VALUES (:id, :nombre, :slug)"),
                [
                    {"id": t1, "nombre": "T1", "slug": f"c03-{t1[:8]}"},
                    {"id": t2, "nombre": "T2", "slug": f"c03-{t2[:8]}"},
                ],
            )
            owner.execute(
                text(
                    "INSERT INTO usuarios (id, tenant_id, nombre, email, password_hash, rol) "
                    "VALUES (:id, :tenant, :nombre, :email, 'fake', 'ADMIN')"
                ),
                [
                    {"id": u1, "tenant": t1, "nombre": "U1", "email": "u1@example.test"},
                    {"id": u2, "tenant": t2, "nombre": "U2", "email": "u2@example.test"},
                ],
            )
            future = datetime.now(UTC) + timedelta(days=1)
            owner.execute(
                text(
                    "INSERT INTO refresh_tokens (tenant_id, usuario_id, token_hash, expira_en) "
                    "VALUES (:t1, :u1, 'hash-1', :exp), (:t2, :u2, 'hash-2', :exp)"
                ),
                {"t1": t1, "u1": u1, "t2": t2, "u2": u2, "exp": future},
            )
            tx.commit()
        except Exception:
            tx.rollback()
            raise

    try:
        with app_connection(engine, t1) as connection:
            hashes = connection.execute(text("SELECT token_hash FROM refresh_tokens")).scalars().all()
            assert hashes == ["hash-1"]
            with pytest.raises(DBAPIError):
                connection.execute(
                    text(
                        "INSERT INTO refresh_tokens (tenant_id, usuario_id, token_hash, expira_en) "
                        "VALUES (:tenant, :user, 'hash-3', :exp)"
                    ),
                    {"tenant": t2, "user": u2, "exp": future},
                )
    finally:
        with engine.connect() as owner:
            tx = owner.begin()
            owner.execute(text("DELETE FROM tenants WHERE id = ANY(:ids)"), {"ids": [t1, t2]})
            tx.commit()
        engine.dispose()

