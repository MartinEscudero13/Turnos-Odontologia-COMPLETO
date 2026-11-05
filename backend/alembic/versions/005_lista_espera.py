"""Migración 005 — C-07 lista-espera-auto-oferta (Alembic).

Crea `lista_espera` y `ofertas` con `tenant_id NOT NULL`, FKs a pacientes,
prestaciones, profesionales y turnos, índices y RLS por tenant. La 004 ya la
consumió C-03 (`004_auth_rbac`), por eso esta es la 005.

Convenciones heredadas de 002/003: timestamptz (nunca timestamp), PK uuid,
NOT NULL + CHECK a nivel DB, RLS forzada (fail-closed), UNIQUE parcial para la
oferta vigente por entrada. Downgrade reversible: sólo elimina lo propio.
"""
from __future__ import annotations

from alembic import op

revision = "005_lista_espera"
down_revision = "004_auth_rbac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE lista_espera (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
          prestacion_id UUID NOT NULL REFERENCES prestaciones(id) ON DELETE CASCADE,
          profesional_pref UUID REFERENCES profesionales(id) ON DELETE SET NULL,
          ventana_desde TIMESTAMPTZ,
          ventana_hasta TIMESTAMPTZ,
          estado TEXT NOT NULL DEFAULT 'PENDIENTE'
            CHECK (estado IN ('PENDIENTE','OFRECIDO','CONVERTIDO','VENCIDO')),
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT lista_espera_ventana_valida CHECK (
            ventana_desde IS NULL OR ventana_hasta IS NULL OR ventana_hasta > ventana_desde
          )
        )
        """
    )
    op.execute("CREATE INDEX lista_espera_tenant_estado_idx ON lista_espera (tenant_id, estado)")
    op.execute(
        "CREATE INDEX lista_espera_tenant_paciente_prestacion_idx"
        " ON lista_espera (tenant_id, paciente_id, prestacion_id)"
    )

    op.execute(
        """
        CREATE TABLE ofertas (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          lista_espera_id UUID NOT NULL REFERENCES lista_espera(id) ON DELETE CASCADE,
          hueco_turno_id UUID REFERENCES turnos(id) ON DELETE SET NULL,
          expira_at TIMESTAMPTZ NOT NULL,
          estado TEXT NOT NULL DEFAULT 'PENDIENTE'
            CHECK (estado IN ('PENDIENTE','ACEPTADA','VENCIDA','CANCELADA')),
          token UUID NOT NULL DEFAULT gen_random_uuid(),
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ofertas_tenant_estado_idx ON ofertas (tenant_id, estado)")
    op.execute("CREATE INDEX ofertas_tenant_expira_idx ON ofertas (tenant_id, expira_at)")
    # A lo sumo una oferta vigente por entrada dentro del tenant (D1/D8).
    op.execute(
        "CREATE UNIQUE INDEX ofertas_tenant_entrada_vigente_uidx"
        " ON ofertas (tenant_id, lista_espera_id) WHERE estado = 'PENDIENTE'"
    )

    # RLS forzada en ambas (fail-closed: sin app.tenant_id no hay filas).
    for table in ("lista_espera", "ofertas"):
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


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS ofertas_tenant_aislamiento ON ofertas")
    op.execute("DROP TABLE IF EXISTS ofertas")
    op.execute("DROP POLICY IF EXISTS lista_espera_tenant_aislamiento ON lista_espera")
    op.execute("DROP TABLE IF EXISTS lista_espera")
