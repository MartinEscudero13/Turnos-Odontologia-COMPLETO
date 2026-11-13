"""Migración 008 — C-10 caja y cierre diario (Alembic).

Crea `movimientos_caja` (hecho de caja inmutable salvo las 4 columnas de
anulación), `cierres_diarios` (snapshot por día), `cobros_pendientes` (medio
`NULL` de C-09), `ajustes_post_cierre` (ledger que explica la corrección sin
editar el cierre) y `cuentas_por_cobrar_os` (devengado informativo de OS).

Decisiones aplicadas (design C-10):
- D1: `fecha` operativa `DATE`; instantes `TIMESTAMPTZ`.
- D2: `anulado` exige motivo, actor e instante en la misma operación; el CHECK
  incluye `motivo_anulacion IS NOT NULL` porque en SQL `NULL <> ''` no es
  verdadero y un CHECK con NULL se aceptaría.
- D7: RLS `ENABLE` + `FORCE` con `NULLIF(current_setting('app.tenant_id', true),
  '')::uuid` en `USING` y `WITH CHECK` (sin tenant ⇒ 0 filas, sin 42704).
- D8: CHECKs de dominio, UNIQUE `(tenant_id, fecha)` del cierre, UNIQUE parcial
  `(tenant_id, linea_id, tramo) WHERE linea_id IS NOT NULL AND origen =
  'IMPUTACION'` (el medio NO integra la clave) y UNIQUE pleno
  `(tenant_id, linea_id)` de pendientes y cuentas por cobrar.
- D14: el advisory lock por `(tenant, fecha)` no vive en la DDL; lo toma el
  repositorio/unidad de trabajo en la misma transacción.

No se agrega ninguna columna a `aceptaciones` (M7): el medio de pago vive sólo
en `movimientos_caja`. Downgrade reversible: sólo elimina lo de la 008.
"""
from __future__ import annotations

from alembic import op

revision = "008_caja_cierre_diario"
down_revision = "007_odontograma_presupuesto"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # D8 — tablas
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE movimientos_caja (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          fecha DATE NOT NULL,
          medio TEXT NOT NULL CHECK (medio IN ('EFECTIVO','TRANSFERENCIA','MP','OS')),
          monto INTEGER NOT NULL CHECK (monto > 0),
          tipo TEXT NOT NULL CHECK (tipo IN ('INGRESO','EGRESO')),
          tramo TEXT,
          turno_id UUID REFERENCES turnos(id) ON DELETE RESTRICT,
          usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
          anulado BOOLEAN NOT NULL DEFAULT false,
          motivo_anulacion TEXT,
          anulado_por UUID REFERENCES usuarios(id) ON DELETE RESTRICT,
          anulado_en TIMESTAMPTZ,
          compensa_a_id UUID REFERENCES movimientos_caja(id) ON DELETE RESTRICT,
          presupuesto_id UUID REFERENCES presupuestos(id) ON DELETE RESTRICT,
          linea_id UUID REFERENCES presupuesto_lineas(id) ON DELETE RESTRICT,
          paciente_id UUID REFERENCES pacientes(id) ON DELETE RESTRICT,
          origen TEXT NOT NULL DEFAULT 'MANUAL'
            CHECK (origen IN ('MANUAL','IMPUTACION','COMPENSACION')),
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT movimientos_caja_tramo_valido
            CHECK (tramo IS NULL OR tramo IN ('PACIENTE','OS')),
          CONSTRAINT movimientos_caja_imputacion_exige_tramo
            CHECK (origen <> 'IMPUTACION' OR tramo IS NOT NULL),
          CONSTRAINT movimientos_caja_compensacion_exige_original
            CHECK (origen <> 'COMPENSACION' OR compensa_a_id IS NOT NULL),
          CONSTRAINT movimientos_caja_anulacion_completa
            CHECK (anulado = false OR (motivo_anulacion IS NOT NULL AND motivo_anulacion <> '' AND anulado_por IS NOT NULL AND anulado_en IS NOT NULL))
        )
        """
    )

    op.execute(
        """
        CREATE TABLE cierres_diarios (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          fecha DATE NOT NULL,
          total_efectivo INTEGER NOT NULL,
          total_transferencia INTEGER NOT NULL,
          total_mp INTEGER NOT NULL,
          total_os_cobrado INTEGER NOT NULL,
          total_os INTEGER NOT NULL DEFAULT 0,
          efectivo_contado INTEGER NOT NULL CHECK (efectivo_contado >= 0),
          diferencia INTEGER NOT NULL,
          responsable_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
          motivo_diferencia TEXT,
          observacion TEXT,
          cerrado_at TIMESTAMPTZ NOT NULL,
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT cierres_diarios_tenant_fecha_unique UNIQUE (tenant_id, fecha),
          CONSTRAINT cierres_diarios_diferencia_exacta
            CHECK (diferencia = efectivo_contado - total_efectivo),
          CONSTRAINT cierres_diarios_diferencia_explicada
            CHECK (diferencia = 0 OR (motivo_diferencia IS NOT NULL AND motivo_diferencia <> '')),
          CONSTRAINT cierres_diarios_motivo_no_vacio
            CHECK (motivo_diferencia IS NULL OR motivo_diferencia <> ''),
          CONSTRAINT cierres_diarios_observacion_no_vacia
            CHECK (observacion IS NULL OR observacion <> '')
        )
        """
    )

    op.execute(
        """
        CREATE TABLE cobros_pendientes (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          fecha DATE NOT NULL,
          presupuesto_id UUID NOT NULL REFERENCES presupuestos(id) ON DELETE RESTRICT,
          linea_id UUID NOT NULL REFERENCES presupuesto_lineas(id) ON DELETE RESTRICT,
          paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE RESTRICT,
          monto_centavos INTEGER NOT NULL CHECK (monto_centavos > 0),
          actor_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
          turno_id UUID REFERENCES turnos(id) ON DELETE RESTRICT,
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          resuelto_en TIMESTAMPTZ,
          movimiento_id UUID REFERENCES movimientos_caja(id) ON DELETE RESTRICT,
          CONSTRAINT cobros_pendientes_tenant_linea_unique UNIQUE (tenant_id, linea_id),
          CONSTRAINT cobros_pendientes_resolucion_completa
            CHECK ((resuelto_en IS NULL) = (movimiento_id IS NULL))
        )
        """
    )

    op.execute(
        """
        CREATE TABLE ajustes_post_cierre (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          cierre_id UUID NOT NULL REFERENCES cierres_diarios(id) ON DELETE RESTRICT,
          tipo TEXT NOT NULL CHECK (tipo IN ('AJUSTE_ANULACION','COBRO_PENDIENTE')),
          movimiento_original_id UUID REFERENCES movimientos_caja(id) ON DELETE RESTRICT,
          cobro_pendiente_id UUID REFERENCES cobros_pendientes(id) ON DELETE RESTRICT,
          monto INTEGER NOT NULL CHECK (monto > 0),
          medio TEXT NOT NULL CHECK (medio IN ('EFECTIVO','TRANSFERENCIA','MP','OS')),
          motivo TEXT,
          actor_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
          compensatorio_id UUID NOT NULL REFERENCES movimientos_caja(id) ON DELETE RESTRICT,
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT ajustes_post_cierre_referencia_valida
            CHECK ((tipo = 'AJUSTE_ANULACION' AND movimiento_original_id IS NOT NULL AND cobro_pendiente_id IS NULL) OR (tipo = 'COBRO_PENDIENTE' AND cobro_pendiente_id IS NOT NULL AND movimiento_original_id IS NULL)),
          CONSTRAINT ajustes_post_cierre_motivo_obligatorio
            CHECK (tipo <> 'AJUSTE_ANULACION' OR (motivo IS NOT NULL AND motivo <> '')),
          CONSTRAINT ajustes_post_cierre_motivo_no_vacio
            CHECK (motivo IS NULL OR motivo <> '')
        )
        """
    )

    op.execute(
        """
        CREATE TABLE cuentas_por_cobrar_os (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          fecha DATE NOT NULL,
          presupuesto_id UUID NOT NULL REFERENCES presupuestos(id) ON DELETE RESTRICT,
          linea_id UUID NOT NULL REFERENCES presupuesto_lineas(id) ON DELETE RESTRICT,
          paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE RESTRICT,
          monto_centavos INTEGER NOT NULL CHECK (monto_centavos > 0),
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT cuentas_por_cobrar_os_tenant_linea_unique UNIQUE (tenant_id, linea_id)
        )
        """
    )

    # ------------------------------------------------------------------
    # D8 — índices por tenant
    # ------------------------------------------------------------------
    op.execute(
        "CREATE INDEX movimientos_caja_tenant_fecha_idx"
        " ON movimientos_caja (tenant_id, fecha)"
    )
    op.execute(
        "CREATE INDEX movimientos_caja_tenant_fecha_medio_idx"
        " ON movimientos_caja (tenant_id, fecha, medio)"
    )
    op.execute(
        "CREATE INDEX movimientos_caja_tenant_turno_idx"
        " ON movimientos_caja (tenant_id, turno_id)"
    )
    op.execute(
        "CREATE INDEX cobros_pendientes_tenant_resuelto_idx"
        " ON cobros_pendientes (tenant_id, resuelto_en)"
    )
    op.execute(
        "CREATE INDEX ajustes_post_cierre_tenant_cierre_idx"
        " ON ajustes_post_cierre (tenant_id, cierre_id)"
    )
    op.execute(
        "CREATE INDEX cuentas_por_cobrar_os_tenant_fecha_idx"
        " ON cuentas_por_cobrar_os (tenant_id, fecha)"
    )

    # D6/H1 — idempotencia de imputación por tramo (el medio no integra la clave).
    op.execute(
        "CREATE UNIQUE INDEX movimientos_caja_tenant_linea_tramo_unique ON movimientos_caja (tenant_id, linea_id, tramo) WHERE linea_id IS NOT NULL AND origen = 'IMPUTACION'"
    )
    # D1 — un ajuste por hecho corregido.
    op.execute(
        "CREATE UNIQUE INDEX ajustes_post_cierre_tenant_movimiento_unique ON ajustes_post_cierre (tenant_id, movimiento_original_id) WHERE movimiento_original_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX ajustes_post_cierre_tenant_pendiente_unique ON ajustes_post_cierre (tenant_id, cobro_pendiente_id) WHERE cobro_pendiente_id IS NOT NULL"
    )

    # ------------------------------------------------------------------
    # D7 — RLS forzada fail-closed en las 5 tablas
    # ------------------------------------------------------------------
    for tabla in (
        "movimientos_caja",
        "cierres_diarios",
        "cobros_pendientes",
        "ajustes_post_cierre",
        "cuentas_por_cobrar_os",
    ):
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
    # Grants explícitos por tabla (cada una con su superficie mutable)
    # ------------------------------------------------------------------
    for tabla in (
        "movimientos_caja",
        "cierres_diarios",
        "cobros_pendientes",
        "ajustes_post_cierre",
        "cuentas_por_cobrar_os",
    ):
        op.execute(f"GRANT SELECT, INSERT ON {tabla} TO turnos_app")

    # D2/RN-CJ-03 — un movimiento no se edita ni se borra; sólo se anula.
    op.execute("REVOKE UPDATE, DELETE ON movimientos_caja FROM turnos_app")
    op.execute(
        "GRANT UPDATE (anulado, motivo_anulacion, anulado_por, anulado_en)"
        " ON movimientos_caja TO turnos_app"
    )

    # D4 — el cierre es un snapshot inmutable.
    op.execute("REVOKE UPDATE, DELETE ON cierres_diarios FROM turnos_app")

    # D5 — un pendiente sólo se resuelve.
    op.execute("REVOKE UPDATE, DELETE ON cobros_pendientes FROM turnos_app")
    op.execute(
        "GRANT UPDATE (resuelto_en, movimiento_id) ON cobros_pendientes TO turnos_app"
    )

    # D3 — el ledger de ajustes y el devengado de OS son append-only.
    op.execute("REVOKE UPDATE, DELETE ON ajustes_post_cierre FROM turnos_app")
    op.execute("REVOKE UPDATE, DELETE ON cuentas_por_cobrar_os FROM turnos_app")


def downgrade() -> None:
    # El orden respeta las FKs: hijas antes que padres. Sólo se elimina lo de la 008.
    op.execute("DROP POLICY IF EXISTS ajustes_post_cierre_tenant_aislamiento ON ajustes_post_cierre")
    op.execute("DROP TABLE IF EXISTS ajustes_post_cierre")
    op.execute(
        "DROP POLICY IF EXISTS cuentas_por_cobrar_os_tenant_aislamiento ON cuentas_por_cobrar_os"
    )
    op.execute("DROP TABLE IF EXISTS cuentas_por_cobrar_os")
    op.execute("DROP POLICY IF EXISTS cobros_pendientes_tenant_aislamiento ON cobros_pendientes")
    op.execute("DROP TABLE IF EXISTS cobros_pendientes")
    op.execute("DROP POLICY IF EXISTS movimientos_caja_tenant_aislamiento ON movimientos_caja")
    op.execute("DROP TABLE IF EXISTS movimientos_caja")
    op.execute("DROP POLICY IF EXISTS cierres_diarios_tenant_aislamiento ON cierres_diarios")
    op.execute("DROP TABLE IF EXISTS cierres_diarios")
