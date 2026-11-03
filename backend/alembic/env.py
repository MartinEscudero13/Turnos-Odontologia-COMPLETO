"""Alembic environment for Turnos-Odontologia.

The application database URL lives outside the repository. This module reads DATABASE_URL
from the environment and otherwise falls back to the non-secret placeholder in alembic.ini.
"""
from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

repo_root = Path(__file__).resolve().parents[2]
backend_root = repo_root / "backend"
if backend_root.exists():
    import sys

    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

from app.models.turno import Base  # noqa: E402

target_metadata = Base.metadata
fallback_url = config.get_main_option("sqlalchemy.url")
url = os.environ.get("DATABASE_OWNER_URL") or os.environ.get("DATABASE_URL") or fallback_url


def run_migrations_offline() -> None:
    assert url is not None
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    assert url is not None
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = url
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
