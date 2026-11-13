"""Migración 007 — C-09 odontograma y presupuesto (Alembic).

Crea `odontograma_hallazgos` (hallazgo clínico FDI inmutable salvo `resuelto`),
`presupuestos` (estado + `vence_en`), `presupuesto_lineas` (montos en centavos,
cobertura persistida e `idempotency_key`) y `aceptaciones` (ledger append-only).

Decisiones aplicadas (design C-09):
- D1: CHECK de grilla FDI por división entera (cuadrante 1–4 × diente 1–8);
  no se usa un rango plano que aceptaría dientes inexistentes.
- D2: contenido clínico inmutable: `GRANT UPDATE (resuelto)` por columna y
  `REVOKE UPDATE`/`REVOKE DELETE` sobre `odontograma_hallazgos`.
- D3.1: UNIQUE parcial `(tenant_id, idempotency_key)` en `presupuesto_lineas`.
- D7: RLS `ENABLE` + `FORCE` con política fail-closed
  `tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid` en
  `USING` y `WITH CHECK` (sin tenant ⇒ 0 filas, sin error 42704).
- D8: `timestamptz`, PK uuid, CHECKs en DB, FK con `ON DELETE RESTRICT` en las
  tablas que sostienen trazabilidad clínica/comercial.
- D8.1: `presupuesto_lineas` y `aceptaciones` sin UPDATE ni DELETE en v1.

No crea tablas de caja (C-10) ni de obras sociales/coberturas (C-12).
Downgrade reversible: sólo elimina las 4 tablas y políticas de la 007.
"""
from __future__ import annotations

from alembic import op

revision = "007_odontograma_presupuesto"
down_revision = "006_ficha_clinica"
branch_labels = None
depends_on = None

_FDI_GRILLA = "(pieza_fdi / 10) BETWEEN 1 AND 4 AND (pieza_fdi % 10) BETWEEN 1 AND 8"


def upgrade() -> None:
    # ------------------------------------------------------------------
    # D8 — tablas
    # ------------------------------------------------------------------
    op.execute(
        f"""
        CREATE TABLE odontograma_hallazgos (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
          pieza_fdi SMALLINT NOT NULL,
          superficie TEXT,
          hallazgo TEXT NOT NULL,
          fecha TIMESTAMPTZ NOT NULL,
          profesional_id UUID NOT NULL REFERENCES profesionales(id) ON DELETE RESTRICT,
          resuelto BOOLEAN NOT NULL DEFAULT false,
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT odontograma_hallazgos_fdi_grilla
            CHECK ({_FDI_GRILLA}),
          CONSTRAINT odontograma_hallazgos_texto_no_vacio
            CHECK (hallazgo <> ''),
          CONSTRAINT odontograma_hallazgos_superficie_no_vacia
            CHECK (superficie IS NULL OR superficie <> '')
        )
        """
    )

    op.execute(
        """
        CREATE TABLE presupuestos (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
          estado TEXT NOT NULL DEFAULT 'BORRADOR'
            CHECK (estado IN ('BORRADOR','VIGENTE','PARCIAL','ACEPTADO','VENCIDO')),
          vence_en TIMESTAMPTZ,
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE presupuesto_lineas (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          presupuesto_id UUID NOT NULL REFERENCES presupuestos(id) ON DELETE RESTRICT,
          hallazgo_id UUID REFERENCES odontograma_hallazgos(id) ON DELETE RESTRICT,
          pieza_fdi SMALLINT,
          prestacion_id UUID NOT NULL REFERENCES prestaciones(id) ON DELETE RESTRICT,
          monto INTEGER NOT NULL CHECK (monto >= 0),
          cobertura_os INTEGER NOT NULL DEFAULT 0 CHECK (cobertura_os >= 0),
          a_cargo_paciente INTEGER NOT NULL DEFAULT 0 CHECK (a_cargo_paciente >= 0),
          origen_cobertura TEXT NOT NULL DEFAULT 'SIN_COBERTURA'
            CHECK (origen_cobertura IN ('CONFIGURADA','SIN_COBERTURA')),
          validada_en_vivo BOOLEAN NOT NULL DEFAULT false,
          idempotency_key UUID,
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT presupuesto_lineas_suma
            CHECK (cobertura_os + a_cargo_paciente = monto),
          CONSTRAINT presupuesto_lineas_fdi_grilla
            CHECK (pieza_fdi IS NULL OR ({_FDI_GRILLA}))
        )
        """
    )

    op.execute(
        """
        CREATE TABLE aceptaciones (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          linea_id UUID NOT NULL REFERENCES presupuesto_lineas(id) ON DELETE RESTRICT,
          acepta BOOLEAN NOT NULL,
          fecha TIMESTAMPTZ NOT NULL,
          canal TEXT NOT NULL CHECK (canal <> ''),
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    # ------------------------------------------------------------------
    # D8 — índices por tenant + UNIQUE parcial de idempotencia (D3.1)
    # ------------------------------------------------------------------
    op.execute(
        "CREATE INDEX odontograma_hallazgos_tenant_paciente_pieza_idx"
        " ON odontograma_hallazgos (tenant_id, paciente_id, pieza_fdi)"
    )
    op.execute(
        "CREATE INDEX presupuestos_tenant_paciente_estado_idx"
        " ON presupuestos (tenant_id, paciente_id, estado)"
    )
    op.execute(
        "CREATE INDEX presupuesto_lineas_tenant_presupuesto_idx"
        " ON presupuesto_lineas (tenant_id, presupuesto_id)"
    )
    op.execute(
        "CREATE INDEX aceptaciones_tenant_linea_idx"
        " ON aceptaciones (tenant_id, linea_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX presupuesto_lineas_tenant_idempotency_key_unique"
        " ON presupuesto_lineas (tenant_id, idempotency_key)"
        " WHERE idempotency_key IS NOT NULL"
    )

    # ------------------------------------------------------------------
    # D7 — RLS forzada fail-closed en las 4 tablas
    # ------------------------------------------------------------------
    for table in (
        "odontograma_hallazgos",
        "presupuestos",
        "presupuesto_lineas",
        "aceptaciones",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_aislamiento ON {table}
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            """
        )

    # Grants explícitos por tabla (cada una con su propia superficie mutable).
    op.execute("GRANT SELECT, INSERT ON odontograma_hallazgos TO turnos_app")
    op.execute("GRANT SELECT, INSERT ON presupuestos TO turnos_app")
    op.execute("GRANT SELECT, INSERT ON presupuesto_lineas TO turnos_app")
    op.execute("GRANT SELECT, INSERT ON aceptaciones TO turnos_app")

    # D2 — inmutable salvo `resuelto` (grant por columna, PostgreSQL).
    op.execute("REVOKE UPDATE ON odontograma_hallazgos FROM turnos_app")
    op.execute("REVOKE DELETE ON odontograma_hallazgos FROM turnos_app")
    op.execute("GRANT UPDATE (resuelto) ON odontograma_hallazgos TO turnos_app")

    # D5 — el presupuesto sólo cambia estado y vencimiento.
    op.execute("REVOKE UPDATE ON presupuestos FROM turnos_app")
    op.execute("REVOKE DELETE ON presupuestos FROM turnos_app")
    op.execute("GRANT UPDATE (estado, vence_en) ON presupuestos TO turnos_app")

    # D8.1 — líneas y aceptaciones son inmutables en v1.
    op.execute("REVOKE UPDATE, DELETE ON presupuesto_lineas FROM turnos_app")
    op.execute("REVOKE UPDATE, DELETE ON aceptaciones FROM turnos_app")


def downgrade() -> None:
    # El orden respeta las FKs: hijas antes que padres.
    op.execute("DROP POLICY IF EXISTS aceptaciones_tenant_aislamiento ON aceptaciones")
    op.execute("DROP TABLE IF EXISTS aceptaciones")
    op.execute(
        "DROP POLICY IF EXISTS presupuesto_lineas_tenant_aislamiento ON presupuesto_lineas"
    )
    op.execute("DROP TABLE IF EXISTS presupuesto_lineas")
    op.execute("DROP POLICY IF EXISTS presupuestos_tenant_aislamiento ON presupuestos")
    op.execute("DROP TABLE IF EXISTS presupuestos")
    op.execute("DROP POLICY IF EXISTS odontograma_hallazgos_tenant_aislamiento ON odontograma_hallazgos")
    op.execute("DROP TABLE IF EXISTS odontograma_hallazgos")
