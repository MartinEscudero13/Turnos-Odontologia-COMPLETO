"""Migración 003 — C-05 turnos-anti-solape (Alembic).

Fuente de verdad del anti-solapamiento: 2 EXCLUDE parciales (D1/D2).
Convenciones: timestamptz (nunca timestamp), PK uuid, NOT NULL + CHECK
a nivel DB, RLS por tenant. Sin CONCURRENTLY (corre en transacción;
CONCURRENTLY queda para evoluciones expand-contract).
Revisión Alembic de la DDL versionada (antes: Prisma/SQL en la corrida TS).
FKs a C-04 (profesionales, sillones, pacientes, prestaciones) diferidas a su
change (expand-contract): acá van IDs escalares sin constraints.
"""
from __future__ import annotations

from alembic import op

revision = "003_turnos_anti_solape"
down_revision = "002_catalogos_pacientes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "btree_gist"')
    op.execute(
        """
        CREATE TABLE turnos (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          profesional_id UUID NOT NULL,
          sillon_id UUID NOT NULL,
          paciente_id UUID NOT NULL,
          prestacion_id UUID NOT NULL,
          inicio TIMESTAMPTZ NOT NULL,
          fin TIMESTAMPTZ NOT NULL,
          estado TEXT NOT NULL DEFAULT 'PENDIENTE'
            CHECK (estado IN ('PENDIENTE','CONFIRMADO','PRESENTE','AUSENTE','CANCELADO','REPROGRAMADO')),
          sobreturno BOOLEAN NOT NULL DEFAULT false,
          motivo_sobreturno TEXT,
          origen TEXT NOT NULL DEFAULT 'RECEPCION'
            CHECK (origen IN ('RECEPCION','RESERVA_ONLINE','LISTA_ESPERA')),
          token_publico TEXT,
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT turnos_fin_posterior CHECK (fin > inicio),
          CONSTRAINT turnos_sobreturno_motivo CHECK (sobreturno = false OR motivo_sobreturno IS NOT NULL)
        )
        """
    )
    # D1: anti-solape real en DB, rango half-open [inicio, fin).
    # Parcial: CANCELADO/REPROGRAMADO y sobreturnos no bloquean.
    op.execute(
        """
        ALTER TABLE turnos
          ADD CONSTRAINT turnos_no_solape_profesional EXCLUDE USING gist (
            tenant_id WITH =,
            profesional_id WITH =,
            tstzrange(inicio, fin) WITH &&
          ) WHERE (estado NOT IN ('CANCELADO', 'REPROGRAMADO') AND sobreturno = false)
        """
    )
    op.execute(
        """
        ALTER TABLE turnos
          ADD CONSTRAINT turnos_no_solape_sillon EXCLUDE USING gist (
            tenant_id WITH =,
            sillon_id WITH =,
            tstzrange(inicio, fin) WITH &&
          ) WHERE (estado NOT IN ('CANCELADO', 'REPROGRAMADO') AND sobreturno = false)
        """
    )
    # D4: índices de búsqueda de hueco y agenda.
    op.execute(
        "CREATE INDEX turnos_tenant_profesional_inicio_idx"
        " ON turnos (tenant_id, profesional_id, inicio)"
    )
    op.execute(
        "CREATE INDEX turnos_tenant_sillon_inicio_idx ON turnos (tenant_id, sillon_id, inicio)"
    )
    op.execute("CREATE INDEX turnos_tenant_estado_idx ON turnos (tenant_id, estado)")
    # token público opcional: unicidad solo cuando existe.
    op.execute(
        "CREATE UNIQUE INDEX turnos_token_publico_uidx"
        " ON turnos (token_publico) WHERE token_publico IS NOT NULL"
    )
    # D2: RLS + aislamiento por tenant (fail-closed: sin app.tenant_id no hay filas).
    op.execute("ALTER TABLE turnos ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY turnos_tenant_aislamiento ON turnos
          USING (tenant_id = current_setting('app.tenant_id')::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS turnos_tenant_aislamiento ON turnos")
    op.execute("DROP TABLE IF EXISTS turnos")
