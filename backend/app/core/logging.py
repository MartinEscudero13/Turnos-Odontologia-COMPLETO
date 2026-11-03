"""Structured JSON logging with conservative PHI redaction."""
from __future__ import annotations

import json
import logging
import sys
from typing import Any

SENSITIVE_KEYS = (
    "password",
    "password_hash",
    "token",
    "jwt",
    "secret",
    "api_key",
    "authorization",
    "email",
    "phone",
    "telefono",
    "dni",
    "name",
    "nombre",
)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("[REDACTED]" if key.lower() in SENSITIVE_KEYS else _redact(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str) and len(value) > 32:
        lowered = value.lower()
        if any(marker in lowered for marker in ("bearer ", "token=", "secret=", "password=")):
            return "[REDACTED]"
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", "-"),
        }
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in logging.makeLogRecord({}).__dict__ and key != "correlation_id"
        }
        payload["context"] = _redact(extras)
        return json.dumps(payload, default=str, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.setLevel(level.upper())
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
