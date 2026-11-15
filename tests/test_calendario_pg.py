"""C-14 contra PostgreSQL real: RLS y roundtrip de repositorios."""
from __future__ import annotations

import pytest
from _calendario_pg import AHORA, INICIO, motor, requiere_pg, sembrar
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.calendario.puertos import CODIGO_LINK_DUPLICADO, ConflictoCalendario
from app.calendario.repositorios import ColaCalendarioSQL, EventoSQL, LinkSQL

pytestmark = requiere_pg


def test_rls_sin_tenant_no_devuelve_filas() -> None:
    engine = motor()
    with engine.connect() as conn:
        tx = conn.begin()
        sembrar(conn, prefijo="c14rls")
        tx.commit()

    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM calendar_links")).scalar() == 0
        assert conn.execute(text("SELECT count(*) FROM calendar_eventos")).scalar() == 0
        assert conn.execute(text("SELECT count(*) FROM calendar_envios")).scalar() == 0


def test_roundtrip_link_evento_y_envio() -> None:
    engine = motor()
    with engine.connect() as conn:
        tx = conn.begin()
        ids = sembrar(conn, prefijo="c14a")
        tx.commit()

    with Session(engine) as session:
        links = LinkSQL(session)
        link = links.crear(
            tenant_id=ids["tenant"],
            profesional_id=ids["profesional"],
            gcal_calendar_id="cal@test",
            oauth_ref="ref-test",
            ahora=AHORA,
        )
        session.commit()
        with pytest.raises(ConflictoCalendario) as excinfo:
            links.crear(
                tenant_id=ids["tenant"],
                profesional_id=ids["profesional"],
                gcal_calendar_id="otro@test",
                oauth_ref="ref-2",
                ahora=AHORA,
            )
        assert excinfo.value.codigo_dominio == CODIGO_LINK_DUPLICADO
        session.commit()

        evento = EventoSQL(session).upsert(
            tenant_id=ids["tenant"],
            link_id=link.id,
            turno_id=None,
            gcal_event_id="gcal-pg-1",
            origen="EXTERNO",
            estado="BLOQUEADO",
            inicio=INICIO,
            fin=INICIO.replace(minute=30),
            resumen="Bloqueo PG",
            ahora=AHORA,
        )
        envio = ColaCalendarioSQL(session).encolar(
            tenant_id=ids["tenant"],
            link_id=link.id,
            evento_id=evento.id,
            accion="PUSH",
            ahora=AHORA,
        )
        session.commit()

        assert [
            e.id
            for e in EventoSQL(session).listar_bloqueos(
                tenant_id=ids["tenant"], desde=INICIO, hasta=INICIO.replace(minute=45)
            )
        ] == [evento.id]
        assert [e.id for e in ColaCalendarioSQL(session).pendientes(tenant_id=ids["tenant"])] == [
            envio.id
        ]
        assert links.obtener(tenant_id=ids["tenant"], link_id=link.id) is not None
