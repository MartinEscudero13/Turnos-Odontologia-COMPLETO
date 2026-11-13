"""Task 5.12 — aceptación concurrente de la misma línea contra PostgreSQL real.

Esta prueba **no se simula con adaptadores en memoria**: sin `SELECT ... FOR
UPDATE` real no existe la garantía. Se salta sin `C02_DATABASE_URL`.

Alcance honesto: el wiring SQLAlchemy de los repositorios de C-09 es un
follow-up declarado (igual que C-06/C-07/C-08). Acá se prueba la garantía de
base que sostiene el `409` de la segunda transacción —dos conexiones
independientes, una toma el lock y acepta, la otra no puede tomarlo y, después
del commit, revalida y ya ve la decisión—; el mapeo de esa revalidación a `409`
sin registrar aceptación está cubierto en el dominio por
`test_aceptacion_presupuesto.py::test_decision_de_otra_transaccion_se_ve_despues_del_lock`.
Cuando exista el repositorio SQLAlchemy se reemplaza el armado manual por el
servicio y la prueba sigue valiendo.
"""
from __future__ import annotations

import pytest
from _presupuesto_pg import AHORA, limpiar, motor, requiere_pg, sembrar_base
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

pytestmark = requiere_pg


def test_dos_conexiones_independientes_imputan_una_vez():
    """Primera toma el lock y acepta; la segunda revalida post-lock y no imputa."""
    engine = motor()
    ids: dict[str, str] = {}
    try:
        with engine.connect() as owner:
            tx = owner.begin()
            ids = sembrar_base(owner)
            tx.commit()

        params = {"l": ids["linea"], "t": ids["tenant"]}
        insertar_aceptacion = text(
            "INSERT INTO aceptaciones (tenant_id, linea_id, acepta, fecha, canal)"
            " VALUES (:t, :l, true, :fecha, 'CONSULTORIO')"
        )
        bloquear = text(
            "SELECT id FROM presupuesto_lineas WHERE tenant_id = :t AND id = :l FOR UPDATE"
        )
        bloquear_sin_esperar = text(
            "SELECT id FROM presupuesto_lineas"
            " WHERE tenant_id = :t AND id = :l FOR UPDATE NOWAIT"
        )
        contar_aceptaciones = text(
            "SELECT count(*) FROM aceptaciones WHERE tenant_id = :t AND linea_id = :l"
        )

        primera = engine.connect()
        segunda = engine.connect()
        try:
            tx1 = primera.begin()
            primera.execute(bloquear, params)
            primera.execute(insertar_aceptacion, {**params, "fecha": AHORA})

            # La segunda conexión no puede tomar el mismo lock: la exclusión es
            # real, no un chequeo previo en el mismo proceso.
            tx2 = segunda.begin()
            with pytest.raises(OperationalError):
                segunda.execute(bloquear_sin_esperar, params)
            tx2.rollback()

            tx1.commit()

            # Post-lock: la segunda revalida y ya ve la decisión persistida
            # (el servicio respondería 409 sin registrar ni imputar).
            tx3 = segunda.begin()
            segunda.execute(bloquear, params)
            ya_decididas = segunda.execute(contar_aceptaciones, params).scalar_one()
            tx3.rollback()
            assert ya_decididas == 1
        finally:
            primera.close()
            segunda.close()

        with engine.connect() as owner:
            assert owner.execute(contar_aceptaciones, params).scalar_one() == 1
    finally:
        limpiar(engine, ids)
