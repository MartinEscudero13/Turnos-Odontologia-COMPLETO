"""Migración 006 — C-08 ficha clínica y consentimiento (Alembic).

Crea `fichas` (ancla 1—1 con paciente), `evoluciones` (append-only),
`adjuntos` (Rx/foto, referencia opaca) y `consentimientos` (timestamp NOT NULL
+ canal) con `tenant_id NOT NULL`, FKs, índices por tenant y RLS forzada.
`evoluciones` y `consentimientos` nacen con `GRANT SELECT, INSERT` +
`REVOKE UPDATE, DELETE` al rol `turnos_app` (append-only a nivel DB, RN-CL-03).

Convenciones heredadas de 002/003/005: timestamptz (nunca timestamp), PK uuid,
NOT NULL + CHECK a nivel DB, RLS forzada (fail-closed), UNIQUE para la 1—1.
Downgrade reversible: sólo elimina lo propio, sin tocar turnos/catálogos/lista.
"""
from __future__ import annotations

from alembic import op

revision = "006_ficha_clinica"
down_revision = "005_lista_espera"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ficha = ancla 1—1 mínima, sin campos clínicos estructurados (D2).
    op.execute(
        """
        CREATE TABLE fichas (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT fichas_tenant_paciente_unique UNIQUE (tenant_id, paciente_id)
        )
        """
    )
    op.execute("CREATE INDEX fichas_tenant_paciente_idx ON fichas (tenant_id, paciente_id)")

    op.execute(
        """
        CREATE TABLE evoluciones (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
          profesional_id UUID NOT NULL REFERENCES profesionales(id) ON DELETE RESTRICT,
          fecha TIMESTAMPTZ NOT NULL,
          texto TEXT NOT NULL,
          firma_hash TEXT,
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX evoluciones_tenant_paciente_idx ON evoluciones (tenant_id, paciente_id)"
    )

    op.execute(
        """
        CREATE TABLE adjuntos (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          ficha_id UUID NOT NULL REFERENCES fichas(id) ON DELETE CASCADE,
          tipo TEXT NOT NULL CHECK (tipo IN ('RX','FOTO')),
          storage_ref TEXT NOT NULL,
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX adjuntos_tenant_ficha_idx ON adjuntos (tenant_id, ficha_id)")

    op.execute(
        """
        CREATE TABLE consentimientos (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
          timestamp TIMESTAMPTZ NOT NULL,
          canal TEXT NOT NULL CHECK (canal <> ''),
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX consentimientos_tenant_paciente_idx"
        " ON consentimientos (tenant_id, paciente_id)"
    )

    # RLS forzada en las 4 tablas (fail-closed: sin app.tenant_id no hay filas).
    for table in ("fichas", "evoluciones", "adjuntos", "consentimientos"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_aislamiento ON {table}
              USING (tenant_id = current_setting('app.tenant_id')::uuid)
              WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
            """
        )
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO turnos_app")

    # Append-only a nivel DB: evoluciones y consentimientos no se editan ni borran.
    op.execute("REVOKE UPDATE, DELETE ON evoluciones FROM turnos_app")
    op.execute("REVOKE UPDATE, DELETE ON consentimientos FROM turnos_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS consentimientos_tenant_aislamiento ON consentimientos")
    op.execute("DROP TABLE IF EXISTS consentimientos")
    op.execute("DROP POLICY IF EXISTS adjuntos_tenant_aislamiento ON adjuntos")
    op.execute("DROP TABLE IF EXISTS adjuntos")
    op.execute("DROP POLICY IF EXISTS evoluciones_tenant_aislamiento ON evoluciones")
    op.execute("DROP TABLE IF EXISTS evoluciones")
    op.execute("DROP POLICY IF EXISTS fichas_tenant_aislamiento ON fichas")
    op.execute("DROP TABLE IF EXISTS fichas")
