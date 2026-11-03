"""C-04 seed materialization from C-02 tenant parameters."""
from __future__ import annotations

import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.base import Base
from app.models.catalogos import Prestacion, Sillon
from app.models.tenant import Tenant
from app.seed import seed_catalogo

TENANT_ID = "a0000000-0000-4000-8000-000000000001"


def test_seed_catalogo_is_idempotent() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[Tenant.__table__, Sillon.__table__, Prestacion.__table__],
    )
    with Session(engine) as session:
        session.add(Tenant(id=uuid.UUID(TENANT_ID), nombre="Demo", slug="demo"))
        session.commit()
        first = seed_catalogo(session, TENANT_ID)
        second = seed_catalogo(session, TENANT_ID)
        assert first == {"sillones": 1, "prestaciones": 2}
        assert second == {"sillones": 0, "prestaciones": 0}
        assert len(session.scalars(select(Sillon)).all()) == 1
        assert len(session.scalars(select(Prestacion)).all()) == 2
