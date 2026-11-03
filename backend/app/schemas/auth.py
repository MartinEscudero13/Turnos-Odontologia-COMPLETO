"""Pydantic schemas for authentication endpoints."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginIn(BaseModel):
    tenant_slug: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)
    two_factor_code: str | None = Field(default=None, min_length=6, max_length=8)

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return value.strip().lower()


class RefreshIn(BaseModel):
    tenant_slug: str = Field(min_length=1, max_length=80)
    refresh_token: str = Field(min_length=20)


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    nombre: str
    email: str
    rol: str
    two_factor: bool
