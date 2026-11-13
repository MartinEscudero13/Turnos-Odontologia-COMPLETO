"""C-09 odontograma — modelo SQLAlchemy del hallazgo clínico.

Espeja la migración 007: grilla FDI por cuadrante/diente, texto y superficie no
vacíos, `resuelto` como único estado mutable (fuente de verdad del grant
`UPDATE (resuelto)`), fechas `timestamptz` y RLS por tenant.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, SmallInteger, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

__all__ = ["OdontogramaHallazgo"]

_FDI_GRILLA = "(pieza_fdi / 10) BETWEEN 1 AND 4 AND (pieza_fdi % 10) BETWEEN 1 AND 8"


class OdontogramaHallazgo(Base):
    """Hallazgo odontológico FDI fechado e inmutable (corrección = hallazgo nuevo)."""

    __tablename__ = "odontograma_hallazgos"
    __table_args__ = (
        CheckConstraint(_FDI_GRILLA, name="odontograma_hallazgos_fdi_grilla"),
        CheckConstraint("hallazgo <> ''", name="odontograma_hallazgos_texto_no_vacio"),
        CheckConstraint(
            "superficie IS NULL OR superficie <> ''",
            name="odontograma_hallazgos_superficie_no_vacia",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    paciente_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False
    )
    pieza_fdi: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    superficie: Mapped[str | None] = mapped_column(Text, nullable=True)
    hallazgo: Mapped[str] = mapped_column(Text, nullable=False)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    profesional_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profesionales.id", ondelete="RESTRICT"), nullable=False
    )
    resuelto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
