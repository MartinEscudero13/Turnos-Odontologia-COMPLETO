"""Schemas Pydantic del borde de presupuesto — C-09 (montos enteros, allow-list).

Los payloads son strict (`extra="forbid"`): un `tenant_id` inyectado responde
`422`. `monto` y `pieza_fdi` son enteros estrictos, `canal` no puede venir vacío y
`vence_en` exige offset (`AwareDatetime`). Las respuestas no incluyen `tenant_id`,
`idempotency_key` ni datos personales.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt

MedioIn = Literal["EFECTIVO", "TRANSFERENCIA", "MP", "OS"]


class PresupuestoIn(BaseModel):
    """POST /api/presupuestos (el vencimiento se fija al emitir)."""

    model_config = ConfigDict(extra="forbid")

    paciente_id: str = Field(min_length=1)


class LineaIn(BaseModel):
    """POST /api/presupuestos/{id}/lineas (sólo alta en BORRADOR, D8.1)."""

    model_config = ConfigDict(extra="forbid")

    prestacion_id: str = Field(min_length=1)
    monto: StrictInt | None = Field(default=None, ge=0)
    pieza_fdi: StrictInt | None = None
    hallazgo_id: str | None = None


class EmisionIn(BaseModel):
    """POST /api/presupuestos/{id}/emitir (vence_en opcional y futuro)."""

    model_config = ConfigDict(extra="forbid")

    vence_en: AwareDatetime | None = None


class AceptacionIn(BaseModel):
    """POST /api/presupuestos/{id}/aceptar (canal no vacío, medio opcional)."""

    model_config = ConfigDict(extra="forbid")

    linea_id: str = Field(min_length=1)
    acepta: bool
    canal: str = Field(min_length=1)
    medio: MedioIn | None = None


class PresupuestoOut(BaseModel):
    """Presupuesto serializado (sin tenant_id)."""

    id: str
    paciente_id: str
    estado: str
    vence_en: datetime | None
    creado_en: datetime
    actualizado_en: datetime


class LineaOut(BaseModel):
    """Línea con montos en centavos y origen de cobertura persistido."""

    id: str
    presupuesto_id: str
    hallazgo_id: str | None
    pieza_fdi: int | None
    prestacion_id: str
    monto: int
    cobertura_os: int
    a_cargo_paciente: int
    origen_cobertura: str
    validada_en_vivo: bool
    creado_en: datetime


class AceptacionOut(BaseModel):
    """Decisión registrada de una línea (ledger append-only)."""

    id: str
    linea_id: str
    acepta: bool
    fecha: datetime
    canal: str
    medio: str | None


class LineaDecisionOut(BaseModel):
    """Línea junto a su última decisión (`None` = pendiente)."""

    linea: LineaOut
    aceptacion: AceptacionOut | None


class PresupuestoDetalleOut(BaseModel):
    """Lectura del presupuesto: `estado` es el reportado (VENCIDO sin persistir)."""

    id: str
    paciente_id: str
    estado: str
    vence_en: datetime | None
    creado_en: datetime
    actualizado_en: datetime
    lineas: list[LineaDecisionOut]


class DecisionOut(BaseModel):
    """Resultado de aceptar o rechazar una línea."""

    presupuesto_id: str
    estado: str
    actor_id: str
    linea_id: str
    acepta: bool
    fecha: datetime
    canal: str
    medio: str | None
