"""SQLAlchemy engine and session helpers.

This module is deliberately small; domain repositories can consume the session factory instead of
managing engines themselves.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import Settings, get_settings


def create_db_engine(settings: Settings | None = None, *, echo: bool = False) -> Engine:
    cfg = settings or get_settings()
    return create_engine(
        cfg.database_url,
        pool_pre_ping=True,
        echo=echo,
        future=True,
    )


def session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    engine_to_use = engine or create_db_engine()
    return sessionmaker(bind=engine_to_use, autoflush=False, expire_on_commit=False, class_=Session)


@contextmanager
def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    factory = session_factory(engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ping_database(engine: Engine | None = None) -> bool:
    engine_to_use = engine or create_db_engine()
    with engine_to_use.connect() as connection:
        return int(connection.execute(text("SELECT 1")).scalar_one()) == 1
