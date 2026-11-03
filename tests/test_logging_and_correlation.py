"""Structured logging and correlation ID behaviour."""
from __future__ import annotations

import json
import logging

from app.core.logging import JsonFormatter


def test_json_formatter_redacts_sensitive_values() -> None:
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="startup",
        args=(),
        exc_info=None,
    )
    record.correlation_id = "corr-123"
    record.password = "secret-value"
    record.phone = "+5491100000000"
    output = JsonFormatter().format(record)
    data = json.loads(output)
    assert data["correlation_id"] == "corr-123"
    assert data["context"]["password"] == "[REDACTED]"
    assert data["context"]["phone"] == "[REDACTED]"
    assert "secret-value" not in output
    assert "+5491100000000" not in output
