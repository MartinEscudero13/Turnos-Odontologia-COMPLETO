"""Migración 011 — C-14 Google Calendar sync (Alembic).

Crea `calendar_links` (OAuth por profesional), `calendar_eventos` (mapeo
turno↔evento y bloqueos externos) y `calendar_envios` (cola de reintentos).

Nota de numeración: el roadmap asignaba 012 a C-14, pero 011 pertenece a C-13
(bloqueado por PO-03). Se usa 011 y C-15 tomará 012.

Decisiones aplicadas (design C-14):
- D1: el turno interno gana; un evento externo se guarda como
  `CONFLICTO_SISTEMA` y nunca cancela la agenda.
- D2: `UNIQUE(tenant, link, gcal_event_id)` parcial para el mapeo idempotente.
- D3/D4: `calendar_envios` con intentos y próximo intento; estados
  `PENDIENTE/PROCESADO/AGOTADO`.
- D5: `oauth_ref` es una referencia, nunca el token en claro.
- RLS `ENABLE + FORCE` fail-closed en las tres tablas y grants por columna.
"""
from __future__ import annotations

from alembic import op

revision = "011_calendar_sync"
down_revision = "010_obras_sociales_liquidacion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE calendar_links (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          profesional_id UUID NOT NULL REFERENCES profesionales(id) ON DELETE CASCADE,
          gcal_calendar_id TEXT NOT NULL,
          oauth_ref TEXT NOT NULL,
          estado TEXT NOT NULL DEFAULT 'CONECTADO',
          ultima_sync TIMESTAMPTZ,
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT calendar_links_estado_valido
            CHECK (estado IN ('CONECTADO','DESCONECTADO','TOKEN_REVOCADO')),
          CONSTRAINT calendar_links_tenant_prof_unique UNIQUE (tenant_id, profesional_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX calendar_links_tenant_estado_idx ON calendar_links (tenant_id, estado)"
    )

    op.execute(
        """
        CREATE TABLE calendar_eventos (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          link_id UUID NOT NULL REFERENCES calendar_links(id) ON DELETE CASCADE,
          turno_id UUID REFERENCES turnos(id) ON DELETE SET NULL,
          gcal_event_id TEXT,
          origen TEXT NOT NULL DEFAULT 'SISTEMA',
          estado TEXT NOT NULL DEFAULT 'PENDIENTE',
          inicio TIMESTAMPTZ NOT NULL,
          fin TIMESTAMPTZ NOT NULL,
          resumen TEXT NOT NULL DEFAULT 'Turno',
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT calendar_eventos_origen_valido
            CHECK (origen IN ('SISTEMA','EXTERNO')),
          CONSTRAINT calendar_eventos_estado_valido
            CHECK (estado IN ('PENDIENTE','SINCRONIZADO','BLOQUEADO','CONFLICTO_SISTEMA','CANCELADO')),
          CONSTRAINT calendar_eventos_rango_valido CHECK (fin > inicio)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX calendar_eventos_tenant_link_gcal_unique"
        " ON calendar_eventos (tenant_id, link_id, gcal_event_id)"
        " WHERE gcal_event_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX calendar_eventos_tenant_link_turno_idx"
        " ON calendar_eventos (tenant_id, link_id, turno_id)"
    )
    op.execute(
        "CREATE INDEX calendar_eventos_tenant_origen_rango_idx"
        " ON calendar_eventos (tenant_id, origen, inicio)"
    )

    op.execute(
        """
        CREATE TABLE calendar_envios (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          link_id UUID NOT NULL REFERENCES calendar_links(id) ON DELETE CASCADE,
          evento_id UUID REFERENCES calendar_eventos(id) ON DELETE SET NULL,
          accion TEXT NOT NULL,
          intentos INTEGER NOT NULL DEFAULT 0,
          proximo_intento TIMESTAMPTZ NOT NULL DEFAULT now(),
          estado TEXT NOT NULL DEFAULT 'PENDIENTE',
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT calendar_envios_accion_valida CHECK (accion IN ('PUSH','DELETE')),
          CONSTRAINT calendar_envios_estado_valido
            CHECK (estado IN ('PENDIENTE','PROCESADO','AGOTADO')),
          CONSTRAINT calendar_envios_intentos_no_negativos CHECK (intentos >= 0)
        )
        """
    )
    op.execute(
        "CREATE INDEX calendar_envios_tenant_estado_idx"
        " ON calendar_envios (tenant_id, estado, proximo_intento)"
    )

    for tabla in ("calendar_links", "calendar_eventos", "calendar_envios"):
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {tabla}_tenant_aislamiento ON {tabla}
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            """
        )

    op.execute("GRANT SELECT, INSERT ON calendar_links TO turnos_app")
    op.execute(
        "GRANT UPDATE (estado, ultima_sync, actualizado_en) ON calendar_links TO turnos_app"
    )
    op.execute("REVOKE UPDATE, DELETE ON calendar_links FROM turnos_app")

    op.execute("GRANT SELECT, INSERT ON calendar_eventos TO turnos_app")
    op.execute(
        "GRANT UPDATE (estado, gcal_event_id, inicio, fin, resumen, actualizado_en)"
        " ON calendar_eventos TO turnos_app"
    )
    op.execute("REVOKE UPDATE, DELETE ON calendar_eventos FROM turnos_app")

    op.execute("GRANT SELECT, INSERT ON calendar_envios TO turnos_app")
    op.execute(
        "GRANT UPDATE (estado, intentos, proximo_intento) ON calendar_envios TO turnos_app"
    )
    op.execute("REVOKE UPDATE, DELETE ON calendar_envios FROM turnos_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS calendar_envios_tenant_aislamiento ON calendar_envios")
    op.execute("DROP TABLE IF EXISTS calendar_envios")
    op.execute("DROP POLICY IF EXISTS calendar_eventos_tenant_aislamiento ON calendar_eventos")
    op.execute("DROP TABLE IF EXISTS calendar_eventos")
    op.execute("DROP POLICY IF EXISTS calendar_links_tenant_aislamiento ON calendar_links")
    op.execute("DROP TABLE IF EXISTS calendar_links")

