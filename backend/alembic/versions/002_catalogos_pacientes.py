"""Migration 002 — C-04 catalogos-pacientes (order-placeholder revision).

This revision establishes the migration chain required by C-05's 003 dependency.
Its tables/indexes/RLS are implemented as part of C-04; no business schema is
created here yet.
"""
from __future__ import annotations

revision = "002_catalogos_pacientes"
down_revision = "001_core_multitenant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
