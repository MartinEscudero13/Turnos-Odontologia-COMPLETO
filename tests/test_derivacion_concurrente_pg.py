"""Task 3.11 — derivación concurrente con la misma key contra PostgreSQL real.

Esta prueba **no se simula con adaptadores en memoria**: sin un UNIQUE parcial
real no existe la garantía. Se salta sin `C02_DATABASE_URL`.

Alcance honesto: el wiring SQLAlchemy de los repositorios de C-09 es un
follow-up declarado (igual que C-06/C-07/C-08), así que acá se prueba la
garantía de base que sostiene el `200` replay —dos conexiones independientes
que intentan insertar la misma `(tenant_id, idempotency_key)` y sólo una gana—.
La traducción de esa violación a `200` con los mismos ids está cubierta en el
dominio por `test_replay_misma_key_mismo_payload_200_mismos_ids`; cuando exista
el repositorio SQLAlchemy se reemplaza el INSERT directo por la llamada al
servicio y se conserva esta prueba.
"""
from __future__ import annotations

import os
import threading
import time
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

PG_URL = os.environ.get("C02_DATABASE_URL")
pytestmark = pytest.mark.skipif(not PG_URL, reason="C02_DATABASE_URL no configurada")

KEY = "550e8400-e29b-41d4-a716-446655440000"


def test_dos_derivaciones_misma_key_crean_una_sola():
    assert PG_URL is not None
    engine = create_engine(PG_URL, future=True)
    ids = {k: str(uuid.uuid4()) for k in ("t1", "pac", "prof", "pres", "presu")}
    insert = text(
        "INSERT INTO presupuesto_lineas"
        " (tenant_id, presupuesto_id, prestacion_id, monto, cobertura_os,"
        "  a_cargo_paciente, idempotency_key)"
        " VALUES (:t, :p, :pr, 150000, 0, 150000, :key)"
    )
    try:
        with engine.connect() as owner:
            tx = owner.begin()
            owner.execute(
                text("INSERT INTO tenants (id, nombre, slug) VALUES (:id, 'T7', :slug)"),
                {"id": ids["t1"], "slug": f"c09c-{ids['t1'][:8]}"},
            )
            owner.execute(
                text(
                    "INSERT INTO pacientes (id, tenant_id, nombre, telefono)"
                    " VALUES (:id, :t, 'Paciente Demo', :tel)"
                ),
                {
                    "id": ids["pac"],
                    "t": ids["t1"],
                    # E.164 ficticio (el CHECK de 002 exige `+` y 8–15 dígitos).
                    "tel": f"+5491{int(ids['pac'].replace('-', ''), 16) % 10**10:010d}",
                },
            )
            owner.execute(
                text(
                    "INSERT INTO prestaciones (id, tenant_id, nombre, duracion_min, precio_base)"
                    " VALUES (:id, :t, 'Conducto Demo', 30, 150000)"
                ),
                {"id": ids["pres"], "t": ids["t1"]},
            )
            owner.execute(
                text("INSERT INTO presupuestos (id, tenant_id, paciente_id) VALUES (:id, :t, :p)"),
                {"id": ids["presu"], "t": ids["t1"], "p": ids["pac"]},
            )
            tx.commit()

        params = {
            "t": ids["t1"], "p": ids["presu"], "pr": ids["pres"], "key": KEY
        }
        # Dos transacciones reales y simultáneas: la primera inserta y mantiene
        # la transacción abierta; la segunda queda bloqueada en el UNIQUE hasta
        # el commit de la primera y recién ahí recibe la violación. Se acota el
        # `statement_timeout` para que un fallo se vea como error y no cuelgue.
        listo = threading.Event()
        resultados: dict[str, str] = {}

        def primera_derivacion() -> None:
            with engine.connect() as conn:
                tx = conn.begin()
                conn.execute(insert, params)
                listo.set()
                time.sleep(0.3)
                tx.commit()
                resultados["primera"] = "creada"

        def segunda_derivacion() -> None:
            assert listo.wait(timeout=10)
            with engine.connect() as conn:
                tx = conn.begin()
                conn.execute(text("SET LOCAL statement_timeout = '5000'"))
                try:
                    conn.execute(insert, params)
                except IntegrityError:
                    resultados["segunda"] = "conflicto"
                else:
                    resultados["segunda"] = "inesperado"
                finally:
                    tx.rollback()

        hilos = [
            threading.Thread(target=primera_derivacion, daemon=True),
            threading.Thread(target=segunda_derivacion, daemon=True),
        ]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=20)
            assert not hilo.is_alive()

        assert resultados == {"primera": "creada", "segunda": "conflicto"}
        with engine.connect() as owner:
            cantidad = owner.execute(
                text(
                    "SELECT count(*) FROM presupuesto_lineas"
                    " WHERE tenant_id = :t AND idempotency_key = :key"
                ),
                {"t": ids["t1"], "key": KEY},
            ).scalar_one()
        assert cantidad == 1
    finally:
        with engine.connect() as owner:
            tx = owner.begin()
            owner.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": ids["t1"]})
            tx.commit()
        engine.dispose()
