"""C-10 caja — modelos SQLAlchemy (movimientos, cierres, pendientes y ajustes).

Espeja la migración 008: fecha operativa `Date` (D1), instantes `timestamptz`,
montos enteros en centavos, CHECKs de dominio en DB, UNIQUE del cierre, UNIQUE
parcial de idempotencia por `(tenant_id, linea_id, tramo)` (el medio no integra
la clave, H1) y tablas hijas con `tenant_id` propio. Todas las tablas quedan
bajo RLS forzada por tenant.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

__all__ = [
    "AjustePostCierre",
    "CierreDiario",
    "CobroPendiente",
    "CuentaPorCobrarOS",
    "MovimientoCaja",
]

_MEDIOS = "medio IN ('EFECTIVO','TRANSFERENCIA','MP','OS')"


class MovimientoCaja(Base):
    """Hecho de caja: inmutable salvo las 4 columnas de anulación (D2)."""

    __tablename__ = "movimientos_caja"
    __table_args__ = (
        CheckConstraint(_MEDIOS, name="movimientos_caja_medio_valido"),
        CheckConstraint("monto > 0", name="movimientos_caja_monto_positivo"),
        CheckConstraint("tipo IN ('INGRESO','EGRESO')", name="movimientos_caja_tipo_valido"),
        CheckConstraint(
            "tramo IS NULL OR tramo IN ('PACIENTE','OS')",
            name="movimientos_caja_tramo_valido",
        ),
        CheckConstraint(
            "origen <> 'IMPUTACION' OR tramo IS NOT NULL",
            name="movimientos_caja_imputacion_exige_tramo",
        ),
        CheckConstraint(
            "origen IN ('MANUAL','IMPUTACION','COMPENSACION')",
            name="movimientos_caja_origen_valido",
        ),
        CheckConstraint(
            "origen <> 'COMPENSACION' OR compensa_a_id IS NOT NULL",
            name="movimientos_caja_compensacion_exige_original",
        ),
        CheckConstraint(
            "anulado = false OR (motivo_anulacion IS NOT NULL"
            " AND motivo_anulacion <> ''"
            " AND anulado_por IS NOT NULL AND anulado_en IS NOT NULL)",
            name="movimientos_caja_anulacion_completa",
        ),
        Index(
            "movimientos_caja_tenant_linea_tramo_unique",
            "tenant_id",
            "linea_id",
            "tramo",
            unique=True,
            postgresql_where=text("linea_id IS NOT NULL AND origen = 'IMPUTACION'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    medio: Mapped[str] = mapped_column(Text, nullable=False)
    monto: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    tramo: Mapped[str | None] = mapped_column(Text, nullable=True)
    turno_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("turnos.id", ondelete="RESTRICT"), nullable=True
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    anulado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    motivo_anulacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    anulado_por: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True
    )
    anulado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    compensa_a_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("movimientos_caja.id", ondelete="RESTRICT"), nullable=True
    )
    presupuesto_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("presupuestos.id", ondelete="RESTRICT"), nullable=True
    )
    linea_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("presupuesto_lineas.id", ondelete="RESTRICT"), nullable=True
    )
    paciente_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pacientes.id", ondelete="RESTRICT"), nullable=True
    )
    origen: Mapped[str] = mapped_column(Text, nullable=False, default="MANUAL")
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CierreDiario(Base):
    """Snapshot inmutable del día: totales por medio, diferencia y responsable."""

    __tablename__ = "cierres_diarios"
    __table_args__ = (
        UniqueConstraint("tenant_id", "fecha", name="cierres_diarios_tenant_fecha_unique"),
        CheckConstraint(
            "efectivo_contado >= 0", name="cierres_diarios_efectivo_no_negativo"
        ),
        CheckConstraint(
            "diferencia = efectivo_contado - total_efectivo",
            name="cierres_diarios_diferencia_exacta",
        ),
        CheckConstraint(
            "diferencia = 0 OR (motivo_diferencia IS NOT NULL AND motivo_diferencia <> '')",
            name="cierres_diarios_diferencia_explicada",
        ),
        CheckConstraint(
            "motivo_diferencia IS NULL OR motivo_diferencia <> ''",
            name="cierres_diarios_motivo_no_vacio",
        ),
        CheckConstraint(
            "observacion IS NULL OR observacion <> ''",
            name="cierres_diarios_observacion_no_vacia",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    total_efectivo: Mapped[int] = mapped_column(Integer, nullable=False)
    total_transferencia: Mapped[int] = mapped_column(Integer, nullable=False)
    total_mp: Mapped[int] = mapped_column(Integer, nullable=False)
    total_os_cobrado: Mapped[int] = mapped_column(Integer, nullable=False)
    total_os: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    efectivo_contado: Mapped[int] = mapped_column(Integer, nullable=False)
    diferencia: Mapped[int] = mapped_column(Integer, nullable=False)
    responsable_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    motivo_diferencia: Mapped[str | None] = mapped_column(Text, nullable=True)
    observacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    cerrado_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CobroPendiente(Base):
    """Imputación sin medio (C-09): único por línea, incluso ya resuelto."""

    __tablename__ = "cobros_pendientes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "linea_id", name="cobros_pendientes_tenant_linea_unique"),
        CheckConstraint(
            "monto_centavos > 0", name="cobros_pendientes_monto_positivo"
        ),
        CheckConstraint(
            "(resuelto_en IS NULL) = (movimiento_id IS NULL)",
            name="cobros_pendientes_resolucion_completa",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    presupuesto_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("presupuestos.id", ondelete="RESTRICT"), nullable=False
    )
    linea_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("presupuesto_lineas.id", ondelete="RESTRICT"), nullable=False
    )
    paciente_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pacientes.id", ondelete="RESTRICT"), nullable=False
    )
    monto_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    turno_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("turnos.id", ondelete="RESTRICT"), nullable=True
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resuelto_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    movimiento_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("movimientos_caja.id", ondelete="RESTRICT"), nullable=True
    )


class AjustePostCierre(Base):
    """Ledger que explica la corrección sin editar el cierre (append-only)."""

    __tablename__ = "ajustes_post_cierre"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('AJUSTE_ANULACION','COBRO_PENDIENTE')",
            name="ajustes_post_cierre_tipo_valido",
        ),
        CheckConstraint("monto > 0", name="ajustes_post_cierre_monto_positivo"),
        CheckConstraint(_MEDIOS, name="ajustes_post_cierre_medio_valido"),
        CheckConstraint(
            "(tipo = 'AJUSTE_ANULACION' AND movimiento_original_id IS NOT NULL"
            " AND cobro_pendiente_id IS NULL)"
            " OR (tipo = 'COBRO_PENDIENTE' AND cobro_pendiente_id IS NOT NULL"
            " AND movimiento_original_id IS NULL)",
            name="ajustes_post_cierre_referencia_valida",
        ),
        CheckConstraint(
            "tipo <> 'AJUSTE_ANULACION' OR (motivo IS NOT NULL AND motivo <> '')",
            name="ajustes_post_cierre_motivo_obligatorio",
        ),
        CheckConstraint(
            "motivo IS NULL OR motivo <> ''",
            name="ajustes_post_cierre_motivo_no_vacio",
        ),
        Index(
            "ajustes_post_cierre_tenant_movimiento_unique",
            "tenant_id",
            "movimiento_original_id",
            unique=True,
            postgresql_where=text("movimiento_original_id IS NOT NULL"),
        ),
        Index(
            "ajustes_post_cierre_tenant_pendiente_unique",
            "tenant_id",
            "cobro_pendiente_id",
            unique=True,
            postgresql_where=text("cobro_pendiente_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cierre_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("cierres_diarios.id", ondelete="RESTRICT"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    movimiento_original_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("movimientos_caja.id", ondelete="RESTRICT"), nullable=True
    )
    cobro_pendiente_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("cobros_pendientes.id", ondelete="RESTRICT"), nullable=True
    )
    monto: Mapped[int] = mapped_column(Integer, nullable=False)
    medio: Mapped[str] = mapped_column(Text, nullable=False)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    compensatorio_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("movimientos_caja.id", ondelete="RESTRICT"), nullable=False
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CuentaPorCobrarOS(Base):
    """Devengado informativo del tramo OS; nunca suma en los totales de caja."""

    __tablename__ = "cuentas_por_cobrar_os"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "linea_id", name="cuentas_por_cobrar_os_tenant_linea_unique"
        ),
        CheckConstraint(
            "monto_centavos > 0", name="cuentas_por_cobrar_os_monto_positivo"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    presupuesto_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("presupuestos.id", ondelete="RESTRICT"), nullable=False
    )
    linea_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("presupuesto_lineas.id", ondelete="RESTRICT"), nullable=False
    )
    paciente_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pacientes.id", ondelete="RESTRICT"), nullable=False
    )
    monto_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
