"""Schemas Pydantic de la superficie pública de la seña — C-11 §5.

Allow-list estricta (D6/D13): la respuesta pública lleva ids, estado, monto,
instantes, `init_point` y política; **nunca** nombre, teléfono, DNI,
`paciente_id` ni `tenant_id`. El bloque de la reserva agrega `token_sena`, que se
entrega una sola vez.

La superficie **interna** (§11) reusa `PoliticaOut` y `TurnoSenaOut`, agrega la
obligación de devolución y mantiene la misma regla de no-PHI. Sus payloads de
entrada son estrictos (`extra="forbid"`): un `tenant_id` o un
`paciente_nombre` en el cuerpo responden `422` y no se procesan.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EstadoSenaOut = Literal["PENDIENTE", "ACREDITADA", "LIBERADA", "APLICADA", "DEVUELTA"]
EstadoPreferenciaOut = Literal["POR_CREAR", "CREADA", "FALLIDA"]
ConceptoAplicacionOut = Literal["TRATAMIENTO", "CANCELACION_TARDIA"]
OrigenObligacionOut = Literal["SENA", "PAGO"]
TipoObligacionOut = Literal["REINTEGRO", "AJUSTE_CAJA"]


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


# ---------------------------------------------------------------------------
# Superficie interna (§11): RBAC, agenda y cola de obligaciones
# ---------------------------------------------------------------------------


class ObligacionOut(BaseModel):
    """Plata que no puede quedar invisible: reintegro o ajuste de caja."""

    origen: OrigenObligacionOut
    tipo: TipoObligacionOut
    monto_centavos: int
    motivo: str | None = None
    mp_payment_id: str | None = None


class SenaInternaOut(BaseModel):
    """`GET /api/senas` y `GET /api/senas/{id}`: allow-list sin PHI (D13)."""

    sena_id: str
    turno_id: str
    turno: TurnoSenaOut | None
    estado: EstadoSenaOut
    monto_centavos: int
    expira_at: datetime
    preferencia_estado: EstadoPreferenciaOut
    politica: PoliticaOut
    obligaciones: list[ObligacionOut]
    acreditada_en: datetime | None = None
    aplicada_en: datetime | None = None
    liberada_en: datetime | None = None
    devuelta_en: datetime | None = None
    motivo_liberacion: str | None = None
    motivo_devolucion: str | None = None
    concepto_aplicacion: ConceptoAplicacionOut | None = None
    devuelta_por: str | None = None
    movimiento_caja_id: str | None = None
    creado_en: datetime


class AplicarEntrada(BaseModel):
    """`POST /api/senas/{id}/aplicar`: sólo el concepto (strict, `extra=forbid`)."""

    model_config = ConfigDict(extra="forbid")

    concepto: ConceptoAplicacionOut = "TRATAMIENTO"


class DevolverEntrada(BaseModel):
    """`POST /api/senas/{id}/devolver`: el motivo es obligatorio (RN-SE-04)."""

    model_config = ConfigDict(extra="forbid")

    motivo: str = Field(min_length=1)


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
