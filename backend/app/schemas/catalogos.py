"""Pydantic schemas for C-04 catalogs and patients."""
from __future__ import annotations

import re
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

E164_RE = re.compile(r"^\+[1-9][0-9]{7,14}$")


class SillonIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)


class SillonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nombre: str
    activo: bool


class PrestacionIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    duracion_min: int = Field(gt=0, le=480)
    precio_base: int = Field(default=0, ge=0)
    requiere_sena: bool = False
    monto_sena: int | None = Field(default=None, ge=0)


class PrestacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nombre: str
    duracion_min: int
    precio_base: int
    requiere_sena: bool
    monto_sena: int | None
    activa: bool


class ProfesionalIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    especialidad: str = Field(min_length=1, max_length=120)
    matricula: str | None = Field(default=None, max_length=60)
    color_agenda: str = Field(default="#3b82f6", max_length=20)
    usuario_id: uuid.UUID | None = None


class ProfesionalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nombre: str
    especialidad: str
    matricula: str | None
    color_agenda: str
    activo: bool


class PacienteIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=160)
    telefono: str = Field(min_length=8, max_length=20)
    email: str | None = Field(default=None, max_length=320)
    nro_afiliado: str | None = Field(default=None, max_length=80)
    consentimiento_ok: bool = False

    @field_validator("telefono")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        compact = re.sub(r"[\s()-]", "", value)
        if not E164_RE.fullmatch(compact):
            raise ValueError("telefono debe estar en formato E.164 (+54...)")
        return compact


class PacienteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nombre: str
    telefono: str
    email: str | None
    nro_afiliado: str | None
    consentimiento_ok: bool
