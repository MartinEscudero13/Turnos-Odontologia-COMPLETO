"""C-02 migration 001: structural contract and RLS expectations."""
from __future__ import annotations

from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parent.parent
    / "backend"
    / "alembic"
    / "versions"
    / "001_core_multitenant.py"
)


def sql() -> str:
    assert MIGRATION.exists()
    return MIGRATION.read_text(encoding="utf-8")


def test_creates_core_tables() -> None:
    text = sql()
    for table in ("tenants", "usuarios", "auditoria", "tenant_parametros"):
        assert f"CREATE TABLE {table}" in text


def test_tenant_user_and_parameter_constraints() -> None:
    text = sql()
    assert "CONSTRAINT usuarios_tenant_email_unique UNIQUE (tenant_id, email)" in text
    assert "REFERENCES tenants(id)" in text
    assert "email = lower(email)" in text
    assert "PRIMARY KEY (tenant_id, clave)" in text


def test_rls_is_forced_and_fail_closed() -> None:
    text = sql()
    assert text.count("ENABLE ROW LEVEL SECURITY") == 3
    assert text.count("FORCE ROW LEVEL SECURITY") == 3
    assert text.count("USING (tenant_id = current_setting('app.tenant_id')::uuid)") == 3
    assert text.count("WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)") == 3
    # fail-closed: no coalesce/default that could let a missing setting pass
    assert "coalesce(current_setting" not in text.lower()


def test_audit_is_append_only_and_app_role_has_no_mutation_grants() -> None:
    text = sql()
    assert "REVOKE UPDATE, DELETE ON auditoria FROM turnos_app" in text
    assert "REVOKE UPDATE, DELETE ON auditoria FROM PUBLIC" in text
    assert "GRANT SELECT, INSERT ON auditoria TO turnos_app" in text


def test_revision_chain_and_downgrade() -> None:
    text = sql()
    assert 'revision = "001_core_multitenant"' in text
    assert "down_revision = None" in text
    assert "def upgrade" in text and "def downgrade" in text
    assert "DROP TABLE IF EXISTS tenants" in text
