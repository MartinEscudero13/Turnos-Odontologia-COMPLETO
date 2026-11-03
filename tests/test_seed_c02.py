"""C-02 idempotent tenant seed."""
from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.base import Base
from app.models.tenant import ParametroTenant, Tenant
from app.seed import DEMO_TENANT_ID, SEED_DEFAULTS, seed_tenant


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[Tenant.__table__, ParametroTenant.__table__],
    )
    return Session(engine)


def test_first_seed_creates_defaults() -> None:
    with make_session() as session:
        result = seed_tenant(session)
        assert result.tenant_created is True
        assert result.parametros_insertados == len(SEED_DEFAULTS)
        tenant = session.get(Tenant, result.tenant_id)
        assert tenant is not None
        assert tenant.slug == "demo"
        values = {
            row.clave: row.valor
            for row in session.scalars(select(ParametroTenant)).all()
        }
        assert values["roles"] == ["ADMIN", "RECEPCION", "ODONTOLOGO"]
        assert values["sillon_demo"] == "Sillón 1"
        assert values["prestaciones_base"] == ["Consulta", "Limpieza"]
        assert values["cancelacion_anticipacion_h"] == "24"


def test_second_seed_is_a_noop() -> None:
    with make_session() as session:
        first = seed_tenant(session)
        second = seed_tenant(session)
        assert second.tenant_created is False
        assert second.parametros_insertados == 0
        assert first.tenant_id == second.tenant_id
        count = len(session.scalars(select(ParametroTenant)).all())
        assert count == len(SEED_DEFAULTS)


def test_seed_does_not_overwrite_existing_value() -> None:
    with make_session() as session:
        result = seed_tenant(session)
        row = session.get(ParametroTenant, (result.tenant_id, "sillon_demo"))
        assert row is not None
        row.valor = "Box personalizado"
        session.commit()

        seed_tenant(session)
        assert session.get(ParametroTenant, (result.tenant_id, "sillon_demo")).valor == "Box personalizado"


def test_demo_tenant_id_is_uuid() -> None:
    assert DEMO_TENANT_ID.count("-") == 4
