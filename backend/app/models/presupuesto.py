"""C-09 presupuesto — modelos SQLAlchemy (presupuesto, línea y aceptación).

Espeja la migración 007: estados de la KB, montos enteros en centavos con
`cobertura_os + a_cargo_paciente = monto`, `origen_cobertura` acotado,
`validada_en_vivo` con default false, UNIQUE parcial de `idempotency_key` por
tenant (D3.1) y `aceptaciones` como ledger append-only. Todas las tablas están
bajo RLS por tenant.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

__all__ = ["Aceptacion", "Presupuesto", "PresupuestoLinea"]

_FDI_GRILLA = "(pieza_fdi / 10) BETWEEN 1 AND 4 AND (pieza_fdi % 10) BETWEEN 1 AND 8"


class Presupuesto(Base):
    """Presupuesto del paciente; `vence_en` se fija al emitir (D5)."""

    __tablename__ = "presupuestos"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('BORRADOR','VIGENTE','PARCIAL','ACEPTADO','VENCIDO')",
            name="presupuestos_estado_valido",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    paciente_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False
    )
    estado: Mapped[str] = mapped_column(Text, nullable=False, default="BORRADOR")
    vence_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PresupuestoLinea(Base):
    """Línea con monto/cobertura persistidos; sin UPDATE ni DELETE en v1 (D8.1)."""

    __tablename__ = "presupuesto_lineas"
    __table_args__ = (
        CheckConstraint("monto >= 0", name="presupuesto_lineas_monto_no_negativo"),
        CheckConstraint("cobertura_os >= 0", name="presupuesto_lineas_cobertura_no_negativa"),
        CheckConstraint(
            "a_cargo_paciente >= 0", name="presupuesto_lineas_a_cargo_no_negativo"
        ),
        CheckConstraint(
            "cobertura_os + a_cargo_paciente = monto", name="presupuesto_lineas_suma"
        ),
        CheckConstraint(
            "origen_cobertura IN ('CONFIGURADA','SIN_COBERTURA')",
            name="presupuesto_lineas_origen_cobertura_valido",
        ),
        CheckConstraint(
            f"pieza_fdi IS NULL OR ({_FDI_GRILLA})",
            name="presupuesto_lineas_fdi_grilla",
        ),
        Index(
            "presupuesto_lineas_tenant_idempotency_key_unique",
            "tenant_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    presupuesto_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("presupuestos.id", ondelete="RESTRICT"), nullable=False
    )
    hallazgo_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("odontograma_hallazgos.id", ondelete="RESTRICT"),
        nullable=True,
    )
    pieza_fdi: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    prestacion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("prestaciones.id", ondelete="RESTRICT"), nullable=False
    )
    monto: Mapped[int] = mapped_column(Integer, nullable=False)
    cobertura_os: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    a_cargo_paciente: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    origen_cobertura: Mapped[str] = mapped_column(
        Text, nullable=False, default="SIN_COBERTURA"
    )
    validada_en_vivo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    idempotency_key: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Aceptacion(Base):
    """Decisión de una línea (ledger append-only, RN-CL-02/D4)."""

    __tablename__ = "aceptaciones"
    __table_args__ = (CheckConstraint("canal <> ''", name="aceptaciones_canal_no_vacio"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    linea_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("presupuesto_lineas.id", ondelete="RESTRICT"), nullable=False
    )
    acepta: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canal: Mapped[str] = mapped_column(Text, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
