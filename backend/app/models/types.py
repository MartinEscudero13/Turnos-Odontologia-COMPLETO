"""SQLAlchemy type helpers (SQLite test / PostgreSQL JSONB production)."""
from typing import Any

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB


def jsonb_type() -> Any:
    """Return JSONB on PostgreSQL and JSON on SQLite test databases."""
    return JSON().with_variant(JSONB(), "postgresql")  # type: ignore[no-untyped-call]
