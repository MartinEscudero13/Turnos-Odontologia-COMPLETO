"""Append-only audit model shared by all bounded contexts."""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import jsonb_type


class Auditoria(Base):
    """Generic append-only audit entry (no UPDATE/DELETE privilege for the app role)."""

    __tablename__ = "auditoria"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    accion: Mapped[str] = mapped_column(Text, nullable=False)
    entidad: Mapped[str] = mapped_column(Text, nullable=False)
    entidad_id: Mapped[str] = mapped_column(Text, nullable=False)
    antes: Mapped[dict[str, Any]] = mapped_column(
        jsonb_type(), nullable=True
    )
    despues: Mapped[dict[str, Any]] = mapped_column(
        jsonb_type(), nullable=True
    )
    motivo: Mapped[str] = mapped_column(Text, nullable=True)
    registrado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )





