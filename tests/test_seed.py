"""Task 2.4 — seed ficticio de test, idempotente y reutilizable: RED primero."""
from __future__ import annotations

from datetime import timedelta

from seed_test import SEED_TEST, aplicar_seed, seed_sql

from app.turnos.servicio import Actor, ServicioTurnos


def test_seed_idempotente_y_reutilizable():
    svc = ServicioTurnos()
    r1 = aplicar_seed(svc)
    r2 = aplicar_seed(svc)
    assert r1["creado"] is True and r2["creado"] is False
    turnos = svc.listar(Actor(tenant_id=SEED_TEST["tenant_id"], rol="RECEPCION", user_id="recep-1"))
    assert len(turnos) == 1
    assert turnos[0].fin == turnos[0].inicio + timedelta(minutes=30)


def test_seed_solo_datos_ficticios_y_sql_con_conflict_nothing():
    assert SEED_TEST["tenant_id"] == "tenant-demo-c05"
    sql = seed_sql()
    assert "ON CONFLICT (id) DO NOTHING" in sql
    assert "set_config('app.tenant_id'" in sql
