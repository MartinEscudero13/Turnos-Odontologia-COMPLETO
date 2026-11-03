"""C-02 live RLS test. Runs only when C02_DATABASE_URL points to a migrated DB."""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError

URL = os.environ.get("C02_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not URL,
    reason="C02_DATABASE_URL no configurada; ejecutar con PostgreSQL migrado",
)


def owner_connection(engine: Engine) -> Connection:
    return engine.connect()


def app_connection(engine: Engine, tenant_id: str) -> Connection:
    connection = engine.connect()
    connection.execute(text("SET ROLE turnos_app"))
    connection.execute(
        text("SELECT set_config('app.tenant_id', :tenant, false)"),
        {"tenant": tenant_id},
    )
    return connection


def cleanup(engine: Engine, tenant_ids: list[str]) -> None:
    with owner_connection(engine) as connection:
        transaction = connection.begin()
        try:
            connection.execute(
                text("DELETE FROM tenants WHERE id = ANY(:ids)"),
                {"ids": tenant_ids},
            )
            transaction.commit()
        except Exception:
            transaction.rollback()
            raise


def test_rls_blocks_cross_tenant_reads_and_writes() -> None:
    assert URL is not None
    engine = create_engine(URL, future=True)
    t1 = str(uuid.uuid4())
    t2 = str(uuid.uuid4())
    with owner_connection(engine) as connection:
        transaction = connection.begin()
        try:
            connection.execute(
                text("INSERT INTO tenants (id, nombre, slug) VALUES (:id, :nombre, :slug)"),
                [
                    {"id": t1, "nombre": "Tenant Uno Demo", "slug": f"c02-{t1[:8]}"},
                    {"id": t2, "nombre": "Tenant Dos Demo", "slug": f"c02-{t2[:8]}"},
                ],
            )
            connection.execute(
                text(
                    "INSERT INTO usuarios (tenant_id, nombre, email, password_hash, rol) "
                    "VALUES (:tenant, 'Usuario Demo', :email, 'fake-hash', 'ADMIN')"
                ),
                [
                    {"tenant": t1, "email": "demo-a@example.test"},
                    {"tenant": t2, "email": "demo-b@example.test"},
                ],
            )
            transaction.commit()
        except Exception:
            transaction.rollback()
            raise

    try:
        with app_connection(engine, t1) as connection:
            visible = connection.execute(text("SELECT email FROM usuarios")).scalars().all()
            assert visible == ["demo-a@example.test"]

        with app_connection(engine, t1) as connection:
            hidden = connection.execute(
                text("SELECT email FROM usuarios WHERE tenant_id = :tenant"), {"tenant": t2}
            ).scalars().all()
            assert hidden == []

        with app_connection(engine, t1) as connection, pytest.raises(DBAPIError):
            connection.execute(
                text(
                    "INSERT INTO usuarios (tenant_id, nombre, email, password_hash, rol) "
                    "VALUES (:tenant, 'Intruso Demo', 'intruso@example.test', 'fake-hash', 'ADMIN')"
                ),
                {"tenant": t2},
            )
    finally:
        cleanup(engine, [t1, t2])
        engine.dispose()


def test_audit_is_append_only_for_app_role() -> None:
    assert URL is not None
    engine = create_engine(URL, future=True)
    tenant = str(uuid.uuid4())
    with owner_connection(engine) as connection:
        transaction = connection.begin()
        try:
            connection.execute(
                text("INSERT INTO tenants (id, nombre, slug) VALUES (:id, 'Audit Demo', :slug)"),
                [{"id": tenant, "slug": f"audit-{tenant[:8]}"}],
            )
            transaction.commit()
        except Exception:
            transaction.rollback()
            raise

    try:
        with app_connection(engine, tenant) as connection:
            connection.execute(
                text(
                    "INSERT INTO auditoria (tenant_id, actor_id, accion, entidad, entidad_id, antes, despues) "
                    "VALUES (:tenant, 'actor-demo', 'CREADO', 'turno', 'turno-demo', NULL, '{\"estado\":\"PENDIENTE\"}')"
                ),
                {"tenant": tenant},
            )

        with app_connection(engine, tenant) as connection, pytest.raises(DBAPIError):
            connection.execute(
                text("UPDATE auditoria SET accion = 'ALTERADO' WHERE tenant_id = :tenant"),
                {"tenant": tenant},
            )

        with app_connection(engine, tenant) as connection, pytest.raises(DBAPIError):
            connection.execute(
                text("DELETE FROM auditoria WHERE tenant_id = :tenant"),
                {"tenant": tenant},
            )
    finally:
        cleanup(engine, [tenant])
        engine.dispose()
