"""Migración 001 — C-02 core-models-multitenant.

Crea el núcleo de tenancy, identidad y auditoría. La aplicación usa un rol
no-owner (`turnos_app`); las migraciones corren con `turnos_owner`.
RLS: las tablas de negocio se filtran por `current_setting('app.tenant_id')::uuid`.
"""
from __future__ import annotations

from alembic import op

revision = "001_core_multitenant"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.execute(
        """
        CREATE TABLE tenants (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          nombre TEXT NOT NULL,
          slug TEXT NOT NULL UNIQUE,
          plan TEXT NOT NULL DEFAULT 'BASICO',
          activo BOOLEAN NOT NULL DEFAULT true,
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE usuarios (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          nombre TEXT NOT NULL,
          email TEXT NOT NULL,
          password_hash TEXT NOT NULL,
          rol TEXT NOT NULL CHECK (rol IN ('ADMIN','RECEPCION','ODONTOLOGO')),
          two_factor BOOLEAN NOT NULL DEFAULT false,
          activo BOOLEAN NOT NULL DEFAULT true,
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT usuarios_tenant_email_unique UNIQUE (tenant_id, email),
          CONSTRAINT usuarios_email_normalizado CHECK (email = lower(email))
        )
        """
    )
    op.execute('CREATE INDEX usuarios_tenant_rol_idx ON usuarios (tenant_id, rol)')

    op.execute(
        """
        CREATE TABLE auditoria (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          actor_id TEXT NOT NULL,
          accion TEXT NOT NULL,
          entidad TEXT NOT NULL,
          entidad_id TEXT NOT NULL,
          antes JSONB,
          despues JSONB,
          motivo TEXT,
          registrado_en TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute('CREATE INDEX auditoria_tenant_entidad_idx ON auditoria (tenant_id, entidad, entidad_id)')
    op.execute('CREATE INDEX auditoria_tenant_fecha_idx ON auditoria (tenant_id, registrado_en)')

    op.execute(
        """
        CREATE TABLE tenant_parametros (
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          clave TEXT NOT NULL,
          valor JSONB NOT NULL,
          actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (tenant_id, clave)
        )
        """
    )

    # RLS: no se puede operar sin tenant. FORCE evita que el owner saltee la política.
    op.execute("ALTER TABLE usuarios ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE auditoria ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_parametros ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE usuarios FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE auditoria FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_parametros FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY usuarios_tenant_aislamiento ON usuarios
          USING (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )
    op.execute(
        """
        CREATE POLICY auditoria_tenant_aislamiento ON auditoria
          USING (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_parametros_tenant_aislamiento ON tenant_parametros
          USING (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )

    # Rol de aplicación: sin UPDATE/DELETE sobre auditoría (append-only).
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'turnos_app') THEN
            CREATE ROLE turnos_app NOLOGIN;
          END IF;
        END
        $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO turnos_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON tenants, usuarios, tenant_parametros TO turnos_app")
    op.execute("GRANT SELECT, INSERT ON auditoria TO turnos_app")
    op.execute("REVOKE UPDATE, DELETE ON auditoria FROM turnos_app")
    op.execute("REVOKE UPDATE, DELETE ON auditoria FROM PUBLIC")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tenant_parametros")
    op.execute("DROP TABLE IF EXISTS auditoria")
    op.execute("DROP TABLE IF EXISTS usuarios")
    op.execute("DROP TABLE IF EXISTS tenants")
