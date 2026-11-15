"""Migración 010 — C-12 obras sociales y liquidación (Alembic).

Crea `obras_sociales` (catálogo por tenant), `coberturas` (par OS × prestación
con modo `PORCENTAJE`/`MONTO` y tope), `liquidaciones` (período + estado +
total) y `liquidacion_lineas` (detalle por turno atendido). Agrega la FK
`pacientes.obra_social_id → obras_sociales` que faltaba desde 002.

Decisiones aplicadas (design C-12):
- D1: montos en centavos; `PORCENTAJE` acotado 1–100 en DB y `valor > 0`.
- D3/D4: `UNIQUE(tenant_id, obra_social_id, periodo_desde, periodo_hasta)` y
  `periodo_desde <= periodo_hasta`; el estado sólo admite `BORRADOR`/`CERRADA`.
- D5: RLS `ENABLE` + `FORCE` fail-closed con
  `NULLIF(current_setting('app.tenant_id', true), '')::uuid` en las cuatro
  tablas, sin tenant ⇒ 0 filas y sin `42704`.
- D7/D8: grants por columna; `DELETE` sólo en `liquidacion_lineas` (regenerar
  un borrador), nunca en catálogo, coberturas ni cabeceras.

Downgrade reversible: elimina sólo lo de la 010 y la FK agregada; no toca
001–009 ni `pacientes.obra_social_id`.
"""
from __future__ import annotations

from alembic import op

revision = "010_obras_sociales_liquidacion"
down_revision = "009_senas_mercadopago"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # D1 — catálogo y coberturas
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE obras_sociales (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          nombre TEXT NOT NULL CHECK (nombre <> ''),
          activa BOOLEAN NOT NULL DEFAULT true,
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT obras_sociales_tenant_nombre_unique UNIQUE (tenant_id, nombre)
        )
        """
    )
    op.execute(
        "CREATE INDEX obras_sociales_tenant_activa_idx ON obras_sociales (tenant_id, activa)"
    )

    op.execute(
        """
        CREATE TABLE coberturas (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          obra_social_id UUID NOT NULL REFERENCES obras_sociales(id) ON DELETE CASCADE,
          prestacion_id UUID NOT NULL REFERENCES prestaciones(id) ON DELETE CASCADE,
          modo TEXT NOT NULL,
          valor INTEGER NOT NULL CHECK (valor > 0),
          tope_centavos INTEGER CHECK (tope_centavos IS NULL OR tope_centavos >= 0),
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT coberturas_modo_valido CHECK (modo IN ('PORCENTAJE','MONTO')),
          CONSTRAINT coberturas_porcentaje_rango
            CHECK (modo <> 'PORCENTAJE' OR valor BETWEEN 1 AND 100),
          CONSTRAINT coberturas_tenant_os_prestacion_unique
            UNIQUE (tenant_id, obra_social_id, prestacion_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX coberturas_tenant_obra_social_idx ON coberturas (tenant_id, obra_social_id)"
    )

    # FK que faltaba desde 002. `SET NULL` evita romper pacientes si se borra la OS.
    # Antes de crearla se limpian referencias huérfanas (p. ej. una OS borrada en un
    # ciclo downgrade/upgrade): la FK no puede validar datos que ya no existen y el
    # paciente queda sin obra social en vez de romper la migración.
    op.execute(
        """
        UPDATE pacientes p
           SET obra_social_id = NULL
         WHERE p.obra_social_id IS NOT NULL
           AND NOT EXISTS (
             SELECT 1 FROM obras_sociales os WHERE os.id = p.obra_social_id
           )
        """
    )
    op.execute(
        """
        ALTER TABLE pacientes
          ADD CONSTRAINT pacientes_obra_social_fk
          FOREIGN KEY (obra_social_id) REFERENCES obras_sociales(id) ON DELETE SET NULL
        """
    )
    op.execute(
        "CREATE INDEX pacientes_tenant_obra_social_idx ON pacientes (tenant_id, obra_social_id)"
    )

    # ------------------------------------------------------------------
    # D4 — liquidación y su detalle
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE liquidaciones (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          obra_social_id UUID NOT NULL REFERENCES obras_sociales(id) ON DELETE RESTRICT,
          periodo_desde DATE NOT NULL,
          periodo_hasta DATE NOT NULL,
          estado TEXT NOT NULL DEFAULT 'BORRADOR',
          total_centavos INTEGER NOT NULL DEFAULT 0 CHECK (total_centavos >= 0),
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          cerrada_en TIMESTAMPTZ,
          CONSTRAINT liquidaciones_periodo_valido CHECK (periodo_desde <= periodo_hasta),
          CONSTRAINT liquidaciones_estado_valido CHECK (estado IN ('BORRADOR','CERRADA')),
          CONSTRAINT liquidaciones_tenant_os_periodo_unique
            UNIQUE (tenant_id, obra_social_id, periodo_desde, periodo_hasta)
        )
        """
    )
    op.execute(
        "CREATE INDEX liquidaciones_tenant_os_idx ON liquidaciones"
        " (tenant_id, obra_social_id, periodo_desde)"
    )

    op.execute(
        """
        CREATE TABLE liquidacion_lineas (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          liquidacion_id UUID NOT NULL REFERENCES liquidaciones(id) ON DELETE CASCADE,
          turno_id UUID NOT NULL REFERENCES turnos(id) ON DELETE RESTRICT,
          paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE RESTRICT,
          prestacion_id UUID NOT NULL REFERENCES prestaciones(id) ON DELETE RESTRICT,
          fecha TIMESTAMPTZ NOT NULL,
          monto_centavos INTEGER NOT NULL,
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT liquidacion_lineas_monto_positivo CHECK (monto_centavos > 0),
          CONSTRAINT liquidacion_lineas_tenant_liquidacion_turno_unique
            UNIQUE (tenant_id, liquidacion_id, turno_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX liquidacion_lineas_tenant_liquidacion_idx"
        " ON liquidacion_lineas (tenant_id, liquidacion_id)"
    )

    # ------------------------------------------------------------------
    # D5 — RLS forzada por tenant
    # ------------------------------------------------------------------
    for tabla in ("obras_sociales", "coberturas", "liquidaciones", "liquidacion_lineas"):
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {tabla}_tenant_aislamiento ON {tabla}
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            """
        )

    # ------------------------------------------------------------------
    # D7 — grants por columna
    # ------------------------------------------------------------------
    op.execute("GRANT SELECT, INSERT ON obras_sociales TO turnos_app")
    op.execute("GRANT UPDATE (nombre, activa, actualizado_en) ON obras_sociales TO turnos_app")
    op.execute("REVOKE UPDATE, DELETE ON obras_sociales FROM turnos_app")

    op.execute("GRANT SELECT, INSERT ON coberturas TO turnos_app")
    op.execute(
        "GRANT UPDATE (modo, valor, tope_centavos, actualizado_en) ON coberturas TO turnos_app"
    )
    op.execute("REVOKE UPDATE, DELETE ON coberturas FROM turnos_app")

    op.execute("GRANT SELECT, INSERT ON liquidaciones TO turnos_app")
    op.execute(
        "GRANT UPDATE (estado, total_centavos, cerrada_en) ON liquidaciones TO turnos_app"
    )
    op.execute("REVOKE UPDATE, DELETE ON liquidaciones FROM turnos_app")

    op.execute("GRANT SELECT, INSERT, DELETE ON liquidacion_lineas TO turnos_app")
    op.execute("REVOKE UPDATE ON liquidacion_lineas FROM turnos_app")


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS liquidacion_lineas_tenant_aislamiento ON liquidacion_lineas"
    )
    op.execute("DROP TABLE IF EXISTS liquidacion_lineas")
    op.execute("DROP POLICY IF EXISTS liquidaciones_tenant_aislamiento ON liquidaciones")
    op.execute("DROP TABLE IF EXISTS liquidaciones")
    op.execute("DROP POLICY IF EXISTS coberturas_tenant_aislamiento ON coberturas")
    op.execute("DROP TABLE IF EXISTS coberturas")
    op.execute("DROP INDEX IF EXISTS pacientes_tenant_obra_social_idx")
    op.execute("ALTER TABLE pacientes DROP CONSTRAINT IF EXISTS pacientes_obra_social_fk")
    op.execute("DROP POLICY IF EXISTS obras_sociales_tenant_aislamiento ON obras_sociales")
    op.execute("DROP TABLE IF EXISTS obras_sociales")
