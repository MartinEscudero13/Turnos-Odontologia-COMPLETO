"""Schemas Pydantic de la superficie pública de la seña — C-11 §5.

Allow-list estricta (D6/D13): la respuesta pública lleva ids, estado, monto,
instantes, `init_point` y política; **nunca** nombre, teléfono, DNI,
`paciente_id` ni `tenant_id`. El bloque de la reserva agrega `token_sena`, que se
entrega una sola vez.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EstadoSenaOut = Literal["PENDIENTE", "ACREDITADA", "LIBERADA", "APLICADA", "DEVUELTA"]
EstadoPreferenciaOut = Literal["POR_CREAR", "CREADA", "FALLIDA"]


class PoliticaOut(BaseModel):
    """Política visible (F-01): promesa de devolución + hecho actual."""

    anticipacion_cancelacion_h: int
    reembolsable: bool
    hay_pago_acreditado: bool


class TurnoSenaOut(BaseModel):
    """Turno de la seña, sin ids internos del paciente."""

    inicio: datetime
    fin: datetime
    prestacion: str


class SenaReservaOut(BaseModel):
    """Bloque `sena` del `201` de la reserva pública (token en claro, una vez)."""

    sena_id: str
    estado: EstadoSenaOut
    monto_centavos: int
    expira_at: datetime
    token_sena: str
    preferencia_estado: EstadoPreferenciaOut
    init_point: str | None
    politica: PoliticaOut


class SenaPublicaOut(BaseModel):
    """`GET /api/publico/{tokenTenant}/senas/{token}` — allow-list exacta."""

    sena_id: str
    estado: EstadoSenaOut
    monto_centavos: int
    expira_at: datetime
    preferencia_estado: EstadoPreferenciaOut
    init_point: str | None
    turno: TurnoSenaOut
    politica: PoliticaOut


class SenaPreferenciaOut(SenaPublicaOut):
    """Respuesta de la preferencia: misma vista + `reintentar_en` en el `202`."""

    reintentar_en: datetime | None = None


class ErrorSenaOut(BaseModel):
    """Body de error de la superficie pública de la seña."""

    detalle: str
    codigo: str | None = Field(default=None)


class WebhookSalida(BaseModel):
    """`200` de `POST /api/webhooks/mercadopago`: qué se hizo con la notificación.

    `resultado` es el efecto aplicado (`ACREDITADA`, `DUPLICADO`,
    `MONTO_DISTINTO`, `PAGO_EXCEDENTE`, `FUERA_DE_TIEMPO`, `IGNORADO`, …) para
    que la pasarela y operación vean que la plata no se descartó.
    """

    resultado: str
    mp_payment_id: str
    sena_id: str | None = None
    estado_pago: str | None = None
