"""Migración 004 — C-03 auth-rbac-auditoria.

Agrega secreto TOTP cifrado y refresh tokens revocables. La tabla de refresh
tokens queda bajo RLS y sólo el rol de aplicación puede leer/insertar/actualizar
(no se necesita DELETE para logout: se marca revocado).
"""
from __future__ import annotations

from alembic import op

revision = "004_auth_rbac"
down_revision = "003_turnos_anti_solape"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE usuarios ADD COLUMN two_factor_secret TEXT NULL")
    op.execute(
        """
        CREATE TABLE refresh_tokens (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
          token_hash TEXT NOT NULL,
          expira_en TIMESTAMPTZ NOT NULL,
          revocado_en TIMESTAMPTZ,
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT refresh_tokens_hash_unique UNIQUE (token_hash)
        )
        """
    )
    op.execute(
        "CREATE INDEX refresh_tokens_tenant_usuario_idx ON refresh_tokens (tenant_id, usuario_id)"
    )
    op.execute("ALTER TABLE refresh_tokens ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE refresh_tokens FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY refresh_tokens_tenant_aislamiento ON refresh_tokens
          USING (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE ON refresh_tokens TO turnos_app")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS refresh_tokens")
    op.execute("ALTER TABLE usuarios DROP COLUMN IF EXISTS two_factor_secret")
