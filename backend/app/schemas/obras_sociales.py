"""Schemas Pydantic del borde de obras sociales — C-12 (allow-list)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

ModoCoberturaOut = Literal["PORCENTAJE", "MONTO"]
EstadoLiquidacionOut = Literal["BORRADOR", "CERRADA"]


class ObraSocialIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=1, max_length=120)


class EstadoObraSocialIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activa: bool


class ObraSocialOut(BaseModel):
    id: str
    nombre: str
    activa: bool
    creado_en: datetime


class CoberturaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    obra_social_id: str = Field(min_length=1)
    prestacion_id: str = Field(min_length=1)
    modo: ModoCoberturaOut
    valor: StrictInt = Field(gt=0)
    tope_centavos: StrictInt | None = Field(default=None, ge=0)


class CoberturaOut(BaseModel):
    id: str
    obra_social_id: str
    prestacion_id: str
    modo: ModoCoberturaOut
    valor: int
    tope_centavos: int | None
    validada_en_vivo: bool
    creado_en: datetime


class TramoCoberturaOut(BaseModel):
    precio_base_centavos: int
    cobertura_os: int
    a_cargo_paciente: int
    origen: Literal["CONFIGURADA", "SIN_COBERTURA"]
    validada_en_vivo: bool


class LiquidacionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    obra_social_id: str = Field(min_length=1)
    desde: date
    hasta: date


class LineaLiquidacionOut(BaseModel):
    turno_id: str
    paciente_id: str
    prestacion_id: str
    fecha: datetime
    monto_centavos: int


class LiquidacionOut(BaseModel):
    id: str
    obra_social_id: str
    periodo_desde: date
    periodo_hasta: date
    estado: EstadoLiquidacionOut
    total_centavos: int
    creado_en: datetime
    cerrada_en: datetime | None = None
    lineas: list[LineaLiquidacionOut] = Field(default_factory=list)


class ErrorOut(BaseModel):
    detalle: str
    codigo: str | None = None
