"""Migración 012 — C-13 WhatsApp con Twilio.

Crea `mensajes_wa` para recordatorios, confirmaciones, cancelaciones y recall.
Twilio se integra detrás de un puerto; la tabla no guarda tokens.

Decisiones aplicadas (design C-13):
- D2: estados y canal acotados por CHECK.
- D3: UNIQUE parcial global de `provider_message_id`.
- D8: RLS `ENABLE + FORCE` y grants por columna; no se borran mensajes.
"""
from __future__ import annotations

from alembic import op

revision = "012_whatsapp_recordatorios"
down_revision = "011_calendar_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE mensajes_wa (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
          turno_id UUID REFERENCES turnos(id) ON DELETE SET NULL,
          plantilla TEXT NOT NULL,
          canal TEXT NOT NULL DEFAULT 'WA',
          estado TEXT NOT NULL DEFAULT 'PENDIENTE',
          provider_message_id TEXT,
          intentos INTEGER NOT NULL DEFAULT 0,
          proximo_intento TIMESTAMPTZ NOT NULL DEFAULT now(),
          cuerpo TEXT NOT NULL,
          respuesta TEXT,
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT mensajes_wa_plantilla_valida
            CHECK (plantilla IN ('RECORDATORIO','CONFIRMACION','CANCELACION','RECALL')),
          CONSTRAINT mensajes_wa_canal_valido CHECK (canal IN ('WA','EMAIL')),
          CONSTRAINT mensajes_wa_estado_valido
            CHECK (estado IN ('PENDIENTE','ENVIADO','ENTREGADO','LEIDO','FALLIDO')),
          CONSTRAINT mensajes_wa_intentos_no_negativos CHECK (intentos >= 0)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX mensajes_wa_provider_message_id_unique"
        " ON mensajes_wa (provider_message_id) WHERE provider_message_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX mensajes_wa_tenant_estado_idx"
        " ON mensajes_wa (tenant_id, estado, proximo_intento)"
    )
    op.execute("CREATE INDEX mensajes_wa_tenant_turno_idx ON mensajes_wa (tenant_id, turno_id)")

    op.execute("ALTER TABLE mensajes_wa ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE mensajes_wa FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY mensajes_wa_tenant_aislamiento ON mensajes_wa
          USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        """
    )

    op.execute("GRANT SELECT, INSERT ON mensajes_wa TO turnos_app")
    op.execute(
        "GRANT UPDATE (estado, provider_message_id, intentos, proximo_intento,"
        " respuesta, actualizado_en) ON mensajes_wa TO turnos_app"
    )
    op.execute("REVOKE UPDATE, DELETE ON mensajes_wa FROM turnos_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS mensajes_wa_tenant_aislamiento ON mensajes_wa")
    op.execute("DROP TABLE IF EXISTS mensajes_wa")
