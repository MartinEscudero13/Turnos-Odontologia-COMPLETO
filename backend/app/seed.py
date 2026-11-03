"""Idempotent tenant seed for C-02.

The seed stores the catalog contract as tenant parameters so C-04 can materialize
sillón/prestación records without duplicating C-04's schema here. No real patient
data or production passwords are created.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tenant import ParametroTenant, Tenant

DEMO_TENANT_ID = "a0000000-0000-4000-8000-000000000001"
DEMO_TENANT_SLUG = "demo"
DEMO_TENANT_NAME = "Consultorio Demo"

SEED_DEFAULTS: dict[str, Any] = {
    "roles": ["ADMIN", "RECEPCION", "ODONTOLOGO"],
    "estados_turno": ["PENDIENTE", "CONFIRMADO", "PRESENTE", "AUSENTE", "CANCELADO", "REPROGRAMADO"],
    "medios_pago": ["EFECTIVO", "TRANSFERENCIA", "MP", "OS"],
    "plantillas_whatsapp": ["confirmacion", "recordatorio", "cancelacion", "auto_oferta"],
    "sillon_demo": "Sillón 1",
    "prestaciones_base": ["Consulta", "Limpieza"],
    "cancelacion_anticipacion_h": "24",
    "politica_sena": "POR_PRESTACION",
}


@dataclass(frozen=True)
class SeedResult:
    tenant_id: uuid.UUID
    tenant_created: bool
    parametros_insertados: int


def seed_tenant(
    session: Session,
    *,
    tenant_id: str = DEMO_TENANT_ID,
    slug: str = DEMO_TENANT_SLUG,
    nombre: str = DEMO_TENANT_NAME,
    plan: str = "BASICO",
) -> SeedResult:
    """Upsert the demo tenant and seed defaults without overwriting existing values."""
    tenant_uuid = uuid.UUID(tenant_id)
    tenant = session.get(Tenant, tenant_uuid)
    if tenant is None:
        tenant = session.scalar(select(Tenant).where(Tenant.slug == slug))
    created = tenant is None
    if tenant is None:
        tenant = Tenant(id=tenant_uuid, nombre=nombre, slug=slug, plan=plan)
        session.add(tenant)
        session.flush()

    inserted = 0
    for clave, valor in SEED_DEFAULTS.items():
        exists = session.get(ParametroTenant, (tenant.id, clave))
        if exists is None:
            session.add(ParametroTenant(tenant_id=tenant.id, clave=clave, valor=valor))
            inserted += 1
    session.commit()
    return SeedResult(tenant_id=tenant.id, tenant_created=created, parametros_insertados=inserted)
