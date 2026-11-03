"""Seed ficticio de test — task 2.4. Datos 100 % ficticios (sin PHI).

`aplicar_seed()` siembra sobre un ServicioTurnos (reutilizable en tests,
idempotente: la segunda corrida es no-op). `seed_sql()` genera el SQL
idempotente para PostgreSQL real (`ON CONFLICT DO NOTHING` + RLS tenant).
"""
from __future__ import annotations

from datetime import UTC, datetime

from app.turnos.servicio import Actor, ServicioTurnos

SEED_TEST: dict[str, object] = {
    "tenant_id": "tenant-demo-c05",
    "profesional_id": "11111111-1111-4111-8111-111111111111",
    "sillon_id": "22222222-2222-4222-8222-222222222222",
    "paciente_id": "33333333-3333-4333-8333-333333333333",
    "prestacion_id": "44444444-4444-4444-8444-444444444444",
    "duracion_min": 30,
    "inicio": datetime(2026, 10, 6, 13, 0, tzinfo=UTC),
}


def aplicar_seed(svc: ServicioTurnos) -> dict[str, bool]:
    """Siembra el turno demo si no existe (idempotente por tenant+recurso+hueco)."""
    actor = Actor(tenant_id=str(SEED_TEST["tenant_id"]), rol="RECEPCION", user_id="seed")
    inicio = SEED_TEST["inicio"]
    assert isinstance(inicio, datetime)
    for t in svc.listar(actor):
        if (
            t.profesional_id == SEED_TEST["profesional_id"]
            and t.sillon_id == SEED_TEST["sillon_id"]
            and t.inicio == inicio
        ):
            return {"creado": False}
    svc.crear(
        actor,
        profesional_id=str(SEED_TEST["profesional_id"]),
        sillon_id=str(SEED_TEST["sillon_id"]),
        paciente_id=str(SEED_TEST["paciente_id"]),
        prestacion_id=str(SEED_TEST["prestacion_id"]),
        inicio=inicio,
        duracion_min=int(SEED_TEST["duracion_min"]),
    )
    return {"creado": True}


def seed_sql() -> str:
    """SQL idempotente para PG real (fija app.tenant_id: opera bajo RLS)."""
    s = SEED_TEST
    return "\n".join(
        [
            f"SELECT set_config('app.tenant_id', '{s['tenant_id']}', false);",
            "INSERT INTO turnos (id, tenant_id, profesional_id, sillon_id,"
            " paciente_id, prestacion_id, inicio, fin, estado, sobreturno, origen)",
            f"VALUES ('55555555-5555-4555-8555-555555555555', '{s['tenant_id']}',"
            f" '{s['profesional_id']}', '{s['sillon_id']}', '{s['paciente_id']}',"
            f" '{s['prestacion_id']}', '2026-10-06T13:00:00Z', '2026-10-06T13:30:00Z',"
            " 'PENDIENTE', false, 'RECEPCION')",
            "ON CONFLICT (id) DO NOTHING;",
            "-- Seed ficticio demo c05: sin datos personales reales (sin PHI).",
        ]
    )
