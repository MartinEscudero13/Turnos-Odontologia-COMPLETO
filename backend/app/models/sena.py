"""C-11 señas con Mercado Pago — modelos SQLAlchemy.

Espeja la migración 009: `senas` (obligación de pago 1──1 con el turno, con los
snapshots de la regla que produjo el monto) y `pagos_mp` (libro de idempotencia
del webhook, `mp_payment_id` único global).

Reglas duras:
- `tenant_id` NOT NULL con RLS forzada (la política vive en la migración).
- Instantes `timestamptz`; montos enteros en centavos.
- CHECKs estado↔instante en la base: ningún estado sin su hecho.
- `token_hash` único global: un token de pago no existe en dos tenants.
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
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
from app.models.types import jsonb_type

__all__ = ["PagoMP", "Sena"]

_ESTADOS_SENA = "estado IN ('PENDIENTE','ACREDITADA','LIBERADA','APLICADA','DEVUELTA')"
_ESTADOS_PAGO = (
    "estado IN ('APPROVED','PENDING','IN_PROCESS','REJECTED',"
    "'CANCELLED','REFUNDED','OTHER')"
)
_RESULTADOS = (
    "resultado IN ('ACREDITADA','DEVUELTA','IGNORADO','MONTO_DISTINTO',"
    "'PAGO_EXCEDENTE','TURNO_NO_CONFIRMABLE','FUERA_DE_TIEMPO','DUPLICADO',"
    "'REEMBOLSADO','REEMBOLSO_AJUSTE_CAJA')"
)


class Sena(Base):
    """Obligación de pago de una reserva; el monto y la regla son snapshots."""

    __tablename__ = "senas"
    __table_args__ = (
        UniqueConstraint("tenant_id", "turno_id", name="senas_tenant_turno_unique"),
        CheckConstraint("monto_centavos > 0", name="senas_monto_positivo"),
        CheckConstraint(_ESTADOS_SENA, name="senas_estado_valido"),
        CheckConstraint(
            "regla_modo IN ('PORCENTAJE','MONTO_FIJO')", name="senas_regla_modo_valido"
        ),
        CheckConstraint("regla_valor > 0", name="senas_regla_valor_positivo"),
        CheckConstraint(
            "precio_base_centavos >= 0", name="senas_precio_base_no_negativo"
        ),
        CheckConstraint(
            "anticipacion_cancelacion_h >= 0", name="senas_anticipacion_no_negativa"
        ),
        CheckConstraint(
            "preferencia_estado IN ('POR_CREAR','CREADA','FALLIDA')",
            name="senas_preferencia_estado_valido",
        ),
        CheckConstraint(
            "intentos_preferencia >= 0", name="senas_intentos_no_negativos"
        ),
        CheckConstraint(
            "motivo_liberacion IS NULL OR motivo_liberacion IN ('EXPIRACION','CANCELACION')",
            name="senas_motivo_liberacion_valido",
        ),
        CheckConstraint(
            "concepto_aplicacion IS NULL OR concepto_aplicacion IN "
            "('TRATAMIENTO','CANCELACION_TARDIA')",
            name="senas_concepto_aplicacion_valido",
        ),
        CheckConstraint(
            "estado <> 'ACREDITADA' OR acreditada_en IS NOT NULL",
            name="senas_acreditada_coherente",
        ),
        CheckConstraint(
            "estado <> 'APLICADA' OR (aplicada_en IS NOT NULL"
            " AND movimiento_caja_id IS NOT NULL AND concepto_aplicacion IS NOT NULL)",
            name="senas_aplicada_coherente",
        ),
        CheckConstraint(
            "estado <> 'LIBERADA' OR (liberada_en IS NOT NULL"
            " AND motivo_liberacion IS NOT NULL)",
            name="senas_liberada_coherente",
        ),
        CheckConstraint(
            "estado <> 'DEVUELTA' OR (devuelta_en IS NOT NULL"
            " AND motivo_devolucion IS NOT NULL AND motivo_devolucion <> '')",
            name="senas_devuelta_coherente",
        ),
        CheckConstraint(
            "preferencia_estado <> 'CREADA' OR (mp_preference_id IS NOT NULL"
            " AND mp_init_point IS NOT NULL)",
            name="senas_preferencia_coherente",
        ),
        Index(
            "senas_tenant_mp_preference_unique",
            "tenant_id",
            "mp_preference_id",
            unique=True,
            postgresql_where=text("mp_preference_id IS NOT NULL"),
        ),
        Index(
            "senas_tenant_movimiento_unique",
            "tenant_id",
            "movimiento_caja_id",
            unique=True,
            postgresql_where=text("movimiento_caja_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    turno_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("turnos.id", ondelete="RESTRICT"), nullable=False
    )
    monto_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[str] = mapped_column(Text, nullable=False, default="PENDIENTE")
    regla_modo: Mapped[str] = mapped_column(Text, nullable=False)
    regla_valor: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_base_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    anticipacion_cancelacion_h: Mapped[int] = mapped_column(Integer, nullable=False)
    mp_preference_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    mp_init_point: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferencia_estado: Mapped[str] = mapped_column(
        Text, nullable=False, default="POR_CREAR"
    )
    intentos_preferencia: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    proximo_reintento_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expira_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    token_rotado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acreditada_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    aplicada_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    liberada_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    devuelta_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    motivo_liberacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    concepto_aplicacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    devuelta_por: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True
    )
    motivo_devolucion: Mapped[str | None] = mapped_column(Text, nullable=True)
    movimiento_caja_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("movimientos_caja.id", ondelete="RESTRICT"),
        nullable=True,
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PagoMP(Base):
    """Un pago notificado por Mercado Pago; `mp_payment_id` es la clave global."""

    __tablename__ = "pagos_mp"
    __table_args__ = (
        CheckConstraint("monto_centavos > 0", name="pagos_mp_monto_positivo"),
        # La moneda es la **real** que informa la pasarela (ARS, USD, …): el
        # pago en otra moneda se registra con `MONTO_DISTINTO` y deja la
        # obligación de devolución visible. La exigencia de `ARS` para acreditar
        # es una regla de aplicación, no un CHECK de base (corrección 2026-11-13).
        CheckConstraint(
            "btrim(moneda) <> '' AND moneda = upper(moneda)",
            name="pagos_mp_moneda_normalizada",
        ),
        CheckConstraint(_ESTADOS_PAGO, name="pagos_mp_estado_valido"),
        CheckConstraint(_RESULTADOS, name="pagos_mp_resultado_valido"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    mp_payment_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    sena_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("senas.id", ondelete="RESTRICT"), nullable=False
    )
    monto_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    moneda: Mapped[str] = mapped_column(Text, nullable=False, default="ARS")
    estado: Mapped[str] = mapped_column(Text, nullable=False)
    resultado: Mapped[str] = mapped_column(Text, nullable=False)
    raw_json: Mapped[Any] = mapped_column(jsonb_type(), nullable=False)
    recibido_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    aprobado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
