"""Core configuration for Turnos-Odontologia (C-01 foundation).

This module is intentionally independent from domain modules so that it can be used by
migrations, CLI tools and API startup with exactly the same validation rules.
"""
from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Runtime settings with fail-fast validation.

    Only technical configuration is held here. Domain and integration secrets are copied
    from the environment and never embedded in code or tests.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = Field(default=Environment.DEVELOPMENT, validation_alias="APP_ENV")
    database_url: str = Field(validation_alias="DATABASE_URL")
    redis_url: str = Field(validation_alias="REDIS_URL")
    jwt_secret: str = Field(validation_alias="JWT_SECRET")
    app_url: str = Field(validation_alias="APP_URL")
    app_name: str = Field(default="turnos-api", validation_alias="APP_NAME")
    app_version: str = Field(default="0.1.0", validation_alias="APP_VERSION")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    @field_validator("database_url")
    @classmethod
    def _database_is_postgresql(cls, value: str) -> str:
        allowed_prefixes = ("postgresql+psycopg://", "postgresql+psycopg2://", "postgresql://", "sqlite://")
        if not value.startswith(allowed_prefixes):
            raise ValueError("DATABASE_URL debe usar PostgreSQL (psycopg) o sqlite solo para tests")
        return value.rstrip("/")

    @field_validator("redis_url")
    @classmethod
    def _redis_is_url(cls, value: str) -> str:
        if not value.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL debe ser una URL redis:// o rediss://")
        return value

    @field_validator("app_url")
    @classmethod
    def _app_url_has_scheme(cls, value: str) -> str:
        if not value.startswith(("https://", "http://")):
            raise ValueError("APP_URL debe incluir http:// o https://")
        return value.rstrip("/")

    @model_validator(mode="after")
    def _production_secrets(self) -> Settings:
        placeholder_prefixes = (
            "change-me",
            "jwt-change-me",
            "example-",
            "placeholder",
            "shhh",
        )
        secret = self.jwt_secret.lower()
        if self.environment is Environment.PRODUCTION:
            if len(self.jwt_secret) < 32 or secret.startswith(placeholder_prefixes):
                raise ValueError("JWT_SECRET no es un secreto real para production")
            if not self.app_url.startswith("https://"):
                raise ValueError("APP_URL debe usar https:// en production")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION


@lru_cache
def get_settings() -> Settings:
    """Return one shared Settings instance for the process."""

    return Settings()
