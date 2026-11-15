"""C-12 obras sociales y liquidación — modelos SQLAlchemy.

Espeja la migración 010: catálogo de obras sociales por tenant, cobertura
configurada por `(obra social × prestación)` con modo `PORCENTAJE`/`MONTO` y
tope opcional, liquidación por período con detalle inmutable al cerrar.

Reglas aplicadas (RN-OS-01/02/03, DD-04):
- montos enteros en centavos y `cobertura_os <= precio_base` se valida en el
  servicio (la DB no conoce el precio de la prestación en la línea);
- `UNIQUE(tenant_id, nombre)` evita obras sociales duplicadas;
- `UNIQUE(tenant_id, obra_social_id, prestacion_id)` hace de la cobertura un
  upsert por par;
- `UNIQUE(tenant_id, obra_social_id, periodo_desde, periodo_hasta)` evita dos
  liquidaciones del mismo período;
- todas las tablas quedan bajo RLS forzada por tenant.
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
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

__all__ = [
    "Cobertura",
    "Liquidacion",
    "LiquidacionLinea",
    "ObraSocial",
]

_MODOS = "modo IN ('PORCENTAJE','MONTO')"
_ESTADOS = "estado IN ('BORRADOR','CERRADA')"


class ObraSocial(Base):
    """Obra social declarada por el tenant (catálogo, no validación en vivo)."""

    __tablename__ = "obras_sociales"
    __table_args__ = (
        UniqueConstraint("tenant_id", "nombre", name="obras_sociales_tenant_nombre_unique"),
        CheckConstraint("nombre <> ''", name="obras_sociales_nombre_no_vacio"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Cobertura(Base):
    """Cobertura por `(obra social × prestación)`; upsert por par (RN-OS-01)."""

    __tablename__ = "coberturas"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "obra_social_id",
            "prestacion_id",
            name="coberturas_tenant_os_prestacion_unique",
        ),
        CheckConstraint(_MODOS, name="coberturas_modo_valido"),
        CheckConstraint("valor > 0", name="coberturas_valor_positivo"),
        CheckConstraint(
            "modo <> 'PORCENTAJE' OR valor BETWEEN 1 AND 100",
            name="coberturas_porcentaje_rango",
        ),
        CheckConstraint(
            "tope_centavos IS NULL OR tope_centavos >= 0",
            name="coberturas_tope_no_negativo",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    obra_social_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("obras_sociales.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prestacion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("prestaciones.id", ondelete="CASCADE"), nullable=False
    )
    modo: Mapped[str] = mapped_column(Text, nullable=False)
    valor: Mapped[int] = mapped_column(Integer, nullable=False)
    tope_centavos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Liquidacion(Base):
    """Liquidación por `(obra social, período)`; `BORRADOR` regenerable."""

    __tablename__ = "liquidaciones"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "obra_social_id",
            "periodo_desde",
            "periodo_hasta",
            name="liquidaciones_tenant_os_periodo_unique",
        ),
        CheckConstraint(_ESTADOS, name="liquidaciones_estado_valido"),
        CheckConstraint("periodo_desde <= periodo_hasta", name="liquidaciones_periodo_valido"),
        CheckConstraint("total_centavos >= 0", name="liquidaciones_total_no_negativo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    obra_social_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("obras_sociales.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    periodo_desde: Mapped[date] = mapped_column(Date, nullable=False)
    periodo_hasta: Mapped[date] = mapped_column(Date, nullable=False)
    estado: Mapped[str] = mapped_column(Text, nullable=False, default="BORRADOR")
    total_centavos: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    cerrada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LiquidacionLinea(Base):
    """Detalle inmutable de la liquidación: una línea por turno atendido."""

    __tablename__ = "liquidacion_lineas"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "liquidacion_id",
            "turno_id",
            name="liquidacion_lineas_tenant_liquidacion_turno_unique",
        ),
        CheckConstraint("monto_centavos > 0", name="liquidacion_lineas_monto_positivo"),
        Index("liquidacion_lineas_tenant_liquidacion_idx", "tenant_id", "liquidacion_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    liquidacion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("liquidaciones.id", ondelete="CASCADE"), nullable=False
    )
    turno_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("turnos.id", ondelete="RESTRICT"), nullable=False
    )
    paciente_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pacientes.id", ondelete="RESTRICT"), nullable=False
    )
    prestacion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("prestaciones.id", ondelete="RESTRICT"), nullable=False
    )
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    monto_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
