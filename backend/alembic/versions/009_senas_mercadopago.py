"""Migración 009 — C-11 señas con Mercado Pago (Alembic).

Crea `senas` (obligación de pago 1──1 con el turno) y `pagos_mp` (libro de
idempotencia del webhook) y agrega el override por prestación de la regla de
seña (`prestaciones.sena_modo`/`sena_valor`).

Decisiones aplicadas (design C-11):
- D1/D14: `tenant_parametros` es clave/valor y **no** se altera; la regla del
  tenant vive como datos (`sena_modo`/`sena_valor` jsonb), no como DDL.
- D2: estados, snapshots y CHECKs estado↔instante; `UNIQUE (tenant_id,
  turno_id)` (1──1 con la reserva); `token_hash` único **global**; UNIQUE
  parciales de preferencia y de movimiento de caja.
- D3: `mp_payment_id` único **global** (RN-SE-03), resultado propio y moneda
  `ARS` (C11-OQ-12).
- D7: RLS `ENABLE` + `FORCE` fail-closed con
  `NULLIF(current_setting('app.tenant_id', true), '')::uuid`: sin tenant la
  consulta devuelve 0 filas y no lanza `42704`.
- D14: grants por columna, `REVOKE DELETE` y backfill legacy conservador
  (`requiere_sena = true AND monto_sena > 0`), sin inventar configuración.

Reversible: el downgrade elimina sólo lo de la 009 y no toca 001–008,
`movimientos_caja`, `cierres_diarios`, `tenant_parametros` ni las columnas
legacy `prestaciones.requiere_sena`/`monto_sena`.
"""
from __future__ import annotations

from alembic import op

revision = "009_senas_mercadopago"
down_revision = "008_caja_cierre_diario"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # D2 — la seña: obligación de pago 1──1 con la reserva
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE senas (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          turno_id UUID NOT NULL REFERENCES turnos(id) ON DELETE RESTRICT,
          monto_centavos INTEGER NOT NULL CHECK (monto_centavos > 0),
          estado TEXT NOT NULL CHECK (estado IN ('PENDIENTE','ACREDITADA','LIBERADA','APLICADA','DEVUELTA')),
          regla_modo TEXT NOT NULL CHECK (regla_modo IN ('PORCENTAJE','MONTO_FIJO')),
          regla_valor INTEGER NOT NULL CHECK (regla_valor > 0),
          precio_base_centavos INTEGER NOT NULL CHECK (precio_base_centavos >= 0),
          anticipacion_cancelacion_h INTEGER NOT NULL CHECK (anticipacion_cancelacion_h >= 0),
          mp_preference_id TEXT,
          mp_init_point TEXT,
          preferencia_estado TEXT NOT NULL DEFAULT 'POR_CREAR' CHECK (preferencia_estado IN ('POR_CREAR','CREADA','FALLIDA')),
          intentos_preferencia INTEGER NOT NULL DEFAULT 0 CHECK (intentos_preferencia >= 0),
          proximo_reintento_at TIMESTAMPTZ,
          expira_at TIMESTAMPTZ NOT NULL,
          token_hash TEXT NOT NULL,
          token_rotado_en TIMESTAMPTZ,
          acreditada_en TIMESTAMPTZ,
          aplicada_en TIMESTAMPTZ,
          liberada_en TIMESTAMPTZ,
          devuelta_en TIMESTAMPTZ,
          motivo_liberacion TEXT CHECK (motivo_liberacion IS NULL OR motivo_liberacion IN ('EXPIRACION','CANCELACION')),
          concepto_aplicacion TEXT CHECK (concepto_aplicacion IS NULL OR concepto_aplicacion IN ('TRATAMIENTO','CANCELACION_TARDIA')),
          devuelta_por UUID REFERENCES usuarios(id) ON DELETE RESTRICT,
          motivo_devolucion TEXT,
          movimiento_caja_id UUID REFERENCES movimientos_caja(id) ON DELETE RESTRICT,
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT senas_tenant_turno_unique UNIQUE (tenant_id, turno_id),
          CONSTRAINT senas_token_hash_unique UNIQUE (token_hash),
          CONSTRAINT senas_acreditada_coherente CHECK (estado <> 'ACREDITADA' OR acreditada_en IS NOT NULL),
          CONSTRAINT senas_aplicada_coherente CHECK (estado <> 'APLICADA' OR (aplicada_en IS NOT NULL AND movimiento_caja_id IS NOT NULL AND concepto_aplicacion IS NOT NULL)),
          CONSTRAINT senas_liberada_coherente CHECK (estado <> 'LIBERADA' OR (liberada_en IS NOT NULL AND motivo_liberacion IS NOT NULL)),
          CONSTRAINT senas_devuelta_coherente CHECK (estado <> 'DEVUELTA' OR (devuelta_en IS NOT NULL AND motivo_devolucion IS NOT NULL AND motivo_devolucion <> '')),
          CONSTRAINT senas_preferencia_coherente CHECK (preferencia_estado <> 'CREADA' OR (mp_preference_id IS NOT NULL AND mp_init_point IS NOT NULL))
        )
        """
    )

    # ------------------------------------------------------------------
    # D3 — el libro de idempotencia del webhook
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE pagos_mp (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          mp_payment_id TEXT NOT NULL,
          sena_id UUID NOT NULL REFERENCES senas(id) ON DELETE RESTRICT,
          monto_centavos INTEGER NOT NULL CHECK (monto_centavos > 0),
          moneda TEXT NOT NULL DEFAULT 'ARS' CHECK (moneda = 'ARS'),
          estado TEXT NOT NULL CHECK (estado IN ('APPROVED','PENDING','IN_PROCESS','REJECTED','CANCELLED','REFUNDED','OTHER')),
          resultado TEXT NOT NULL CHECK (resultado IN ('ACREDITADA','DEVUELTA','IGNORADO','MONTO_DISTINTO','PAGO_EXCEDENTE','TURNO_NO_CONFIRMABLE','FUERA_DE_TIEMPO','DUPLICADO','REEMBOLSADO','REEMBOLSO_AJUSTE_CAJA')),
          raw_json JSONB NOT NULL,
          recibido_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          aprobado_en TIMESTAMPTZ,
          CONSTRAINT pagos_mp_mp_payment_id_unique UNIQUE (mp_payment_id)
        )
        """
    )

    # ------------------------------------------------------------------
    # D2/D3 — índices por tenant y UNIQUE parciales
    # ------------------------------------------------------------------
    op.execute(
        "CREATE INDEX senas_tenant_estado_expira_idx"
        " ON senas (tenant_id, estado, expira_at)"
    )
    op.execute("CREATE INDEX senas_tenant_creado_idx ON senas (tenant_id, creado_en)")
    op.execute(
        "CREATE UNIQUE INDEX senas_tenant_mp_preference_unique ON senas (tenant_id, mp_preference_id) WHERE mp_preference_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX senas_tenant_movimiento_unique ON senas (tenant_id, movimiento_caja_id) WHERE movimiento_caja_id IS NOT NULL"
    )
    op.execute("CREATE INDEX pagos_mp_tenant_sena_idx ON pagos_mp (tenant_id, sena_id)")
    op.execute("CREATE INDEX pagos_mp_tenant_recibido_idx ON pagos_mp (tenant_id, recibido_en)")

    # ------------------------------------------------------------------
    # D1/D14 — override por prestación (nullable = hereda del tenant)
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE prestaciones ADD COLUMN sena_modo TEXT")
    op.execute("ALTER TABLE prestaciones ADD COLUMN sena_valor INTEGER")
    op.execute(
        "ALTER TABLE prestaciones ADD CONSTRAINT prestaciones_sena_modo_valido CHECK (sena_modo IS NULL OR sena_modo IN ('SIN_SENA','PORCENTAJE','MONTO_FIJO'))"
    )
    op.execute(
        "ALTER TABLE prestaciones ADD CONSTRAINT prestaciones_sena_valor_no_negativo CHECK (sena_valor IS NULL OR sena_valor >= 0)"
    )
    # `SIN_SENA` nunca lleva valor; un modo que cobra siempre lo exige.
    op.execute(
        "ALTER TABLE prestaciones ADD CONSTRAINT prestaciones_sin_sena_sin_valor CHECK (sena_modo <> 'SIN_SENA' OR sena_valor IS NULL)"
    )
    op.execute(
        "ALTER TABLE prestaciones ADD CONSTRAINT prestaciones_sena_valor_requerido CHECK (sena_modo IS NULL OR sena_modo = 'SIN_SENA' OR sena_valor IS NOT NULL)"
    )

    # ------------------------------------------------------------------
    # D14 — backfill legacy conservador (no se inventa configuración)
    # ------------------------------------------------------------------
    op.execute(
        """
        UPDATE prestaciones
           SET sena_modo = 'MONTO_FIJO',
               sena_valor = monto_sena
         WHERE requiere_sena = true
           AND monto_sena IS NOT NULL
           AND monto_sena > 0
        """
    )
    op.execute(
        """
        DO $$
        DECLARE fila RECORD;
        BEGIN
          FOR fila IN
            SELECT id, tenant_id
              FROM prestaciones
             WHERE requiere_sena = true
               AND (monto_sena IS NULL OR monto_sena <= 0)
          LOOP
            RAISE NOTICE 'C-11: prestación % del tenant % requiere revisión de seña (requiere_sena=true sin monto válido)', fila.id, fila.tenant_id;
          END LOOP;
        END
        $$;
        """
    )

    # ------------------------------------------------------------------
    # D7 — RLS forzada fail-closed en las dos tablas
    # ------------------------------------------------------------------
    for tabla in (
        "senas",
        "pagos_mp",
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
    # D14 — grants por columna: la seña no se edita ni se borra
    # ------------------------------------------------------------------
    op.execute("GRANT SELECT, INSERT ON senas TO turnos_app")
    op.execute("REVOKE UPDATE, DELETE ON senas FROM turnos_app")
    # Superficie mutable: estado e instantes, preferencia y rotación de token.
    # `monto_centavos`, `turno_id`, `regla_*`, `precio_base_centavos` y
    # `expira_at` quedan fuera: el monto cobrado no se reescribe (D2).
    op.execute(
        "GRANT UPDATE (estado, acreditada_en, aplicada_en, liberada_en, devuelta_en,"
        " motivo_liberacion, concepto_aplicacion, devuelta_por, motivo_devolucion,"
        " movimiento_caja_id, mp_preference_id, mp_init_point, preferencia_estado,"
        " intentos_preferencia, proximo_reintento_at, token_hash, token_rotado_en)"
        " ON senas TO turnos_app"
    )

    op.execute("GRANT SELECT, INSERT ON pagos_mp TO turnos_app")
    op.execute("REVOKE UPDATE, DELETE ON pagos_mp FROM turnos_app")
    op.execute(
        "GRANT UPDATE (estado, resultado, raw_json, actualizado_en, aprobado_en) ON pagos_mp TO turnos_app"
    )


def downgrade() -> None:
    # Sólo se elimina lo de la 009; las hijas caen antes que las padres.
    op.execute("DROP POLICY IF EXISTS pagos_mp_tenant_aislamiento ON pagos_mp")
    op.execute("DROP TABLE IF EXISTS pagos_mp")
    op.execute("DROP POLICY IF EXISTS senas_tenant_aislamiento ON senas")
    op.execute("DROP TABLE IF EXISTS senas")

    # Override por prestación: primero las constraints, después las columnas.
    op.execute(
        "ALTER TABLE prestaciones DROP CONSTRAINT IF EXISTS prestaciones_sena_valor_requerido"
    )
    op.execute(
        "ALTER TABLE prestaciones DROP CONSTRAINT IF EXISTS prestaciones_sin_sena_sin_valor"
    )
    op.execute(
        "ALTER TABLE prestaciones DROP CONSTRAINT IF EXISTS prestaciones_sena_valor_no_negativo"
    )
    op.execute(
        "ALTER TABLE prestaciones DROP CONSTRAINT IF EXISTS prestaciones_sena_modo_valido"
    )
    op.execute("ALTER TABLE prestaciones DROP COLUMN IF EXISTS sena_valor")
    op.execute("ALTER TABLE prestaciones DROP COLUMN IF EXISTS sena_modo")
