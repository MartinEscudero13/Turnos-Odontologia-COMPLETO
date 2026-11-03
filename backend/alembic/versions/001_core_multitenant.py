"""Migración 001 — C-02 core-models-multitenant (placeholder de orden).

C-01 inicializa el grafo Alembic y mantiene la dependencia histórica de
003_turnos_anti_solape. El contenido de esta revisión se implementa al
llevar C-02 (`Tenant`, `Usuario`, auditoría, RLS y seed vacío).
"""
from __future__ import annotations

revision = "001_core_multitenant"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
