"""Migración 002 — C-04 catalogos-pacientes-base.

Implementa el catálogo operativo del tenant y la ficha base de paciente.
C-04 no crea clínica ni obras sociales; sólo referencias opcionales.
RLS forzada en todas las tablas tenant-scoped.
"""
from __future__ import annotations

from alembic import op

revision = "002_catalogos_pacientes"
down_revision = "001_core_multitenant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE sillones (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          nombre TEXT NOT NULL,
          activo BOOLEAN NOT NULL DEFAULT true,
          CONSTRAINT sillones_tenant_nombre_unique UNIQUE (tenant_id, nombre)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE prestaciones (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          nombre TEXT NOT NULL,
          duracion_min INTEGER NOT NULL CHECK (duracion_min > 0),
          precio_base INTEGER NOT NULL DEFAULT 0 CHECK (precio_base >= 0),
          requiere_sena BOOLEAN NOT NULL DEFAULT false,
          monto_sena INTEGER,
          activa BOOLEAN NOT NULL DEFAULT true,
          CONSTRAINT prestaciones_tenant_nombre_unique UNIQUE (tenant_id, nombre)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE profesionales (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          usuario_id UUID REFERENCES usuarios(id) ON DELETE SET NULL,
          nombre TEXT NOT NULL,
          especialidad TEXT NOT NULL,
          matricula TEXT,
          color_agenda TEXT NOT NULL DEFAULT '#3b82f6',
          activo BOOLEAN NOT NULL DEFAULT true
        )
        """
    )
    op.execute(
        """
        CREATE TABLE profesional_prestacion (
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          profesional_id UUID NOT NULL REFERENCES profesionales(id) ON DELETE CASCADE,
          prestacion_id UUID NOT NULL REFERENCES prestaciones(id) ON DELETE CASCADE,
          PRIMARY KEY (tenant_id, profesional_id, prestacion_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE horarios_semanales (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          profesional_id UUID NOT NULL REFERENCES profesionales(id) ON DELETE CASCADE,
          dia INTEGER NOT NULL CHECK (dia BETWEEN 1 AND 7),
          desde TIME NOT NULL,
          hasta TIME NOT NULL,
          CONSTRAINT horarios_rango_valido CHECK (hasta > desde)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE bloqueos (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          profesional_id UUID REFERENCES profesionales(id) ON DELETE CASCADE,
          sillon_id UUID REFERENCES sillones(id) ON DELETE CASCADE,
          desde TIMESTAMPTZ NOT NULL,
          hasta TIMESTAMPTZ NOT NULL,
          motivo TEXT NOT NULL,
          CONSTRAINT bloqueos_rango_valido CHECK (hasta > desde),
          CONSTRAINT bloqueos_destino_requerido CHECK (profesional_id IS NOT NULL OR sillon_id IS NOT NULL)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE pacientes (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          nombre TEXT NOT NULL,
          dni_cifrado TEXT,
          telefono TEXT NOT NULL CHECK (telefono ~ '^\\+[1-9][0-9]{7,14}$'),
          email TEXT,
          obra_social_id UUID,
          nro_afiliado TEXT,
          consentimiento_ok BOOLEAN NOT NULL DEFAULT false,
          creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT pacientes_tenant_telefono_unique UNIQUE (tenant_id, telefono)
        )
        """
    )
    op.execute("CREATE INDEX profesionales_tenant_activo_idx ON profesionales (tenant_id, activo)")
    op.execute("CREATE INDEX prestaciones_tenant_activa_idx ON prestaciones (tenant_id, activa)")
    op.execute("CREATE INDEX pacientes_tenant_telefono_idx ON pacientes (tenant_id, telefono)")
    op.execute("CREATE INDEX bloqueos_tenant_desde_idx ON bloqueos (tenant_id, desde)")

    for table in (
        "sillones",
        "prestaciones",
        "profesionales",
        "profesional_prestacion",
        "horarios_semanales",
        "bloqueos",
        "pacientes",
    ):
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
    for table in (
        "pacientes",
        "bloqueos",
        "horarios_semanales",
        "profesional_prestacion",
        "profesionales",
        "prestaciones",
        "sillones",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")
