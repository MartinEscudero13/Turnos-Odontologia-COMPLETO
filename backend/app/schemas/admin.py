"""Schemas Pydantic del borde admin — C-15."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

RolOut = Literal["ADMIN", "RECEPCION", "ODONTOLOGO"]


class ConfigIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anticipacion_cancelacion_h: StrictInt | None = Field(default=None, ge=0, le=168)
    sena_modo: Literal["SIN_SENA", "PORCENTAJE", "MONTO_FIJO"] | None = None
    sena_valor: StrictInt | None = Field(default=None, ge=0)
    recordatorios_habilitados: StrictBool | None = None


class UsuarioIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)
    rol: RolOut


class UsuarioEstadoIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activo: StrictBool


class UsuarioOut(BaseModel):
    id: str
    nombre: str
    email: str
    rol: RolOut
    activo: bool
    creado_en: datetime


class KpisOut(BaseModel):
    desde: str
    hasta: str
    total_turnos: int
    turnos_por_estado: dict[str, int]
    ausentismo_pct: float
    reservas_online_pct: float
    facturacion_por_profesional: list[tuple[str, int]]
    reasignados_2h: int
    ocupacion_pct: float


class ErrorOut(BaseModel):
    detalle: str
    codigo: str | None = None


ConfigDictAny = dict[str, Any]
