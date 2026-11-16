"""Superadmin cross-tenant por CLI.

La API es single-tenant por despliegue: cada request resuelve su ``tenant_id``
desde el JWT/headers y las políticas RLS impiden ver otros tenants. La operación
cross-tenant (listar, crear, activar o desactivar tenants) se hace fuera de la
API, con la credencial de dueño de la base.

Uso:
    py tools/superadmin.py list
    py tools/superadmin.py create <slug> "<nombre>" [plan]
    py tools/superadmin.py activate <slug>
    py tools/superadmin.py deactivate <slug>

Requiere ``DATABASE_URL`` (o ``C02_DATABASE_URL`` en local) apuntando a la base
con permisos de escritura sobre ``tenants``.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.models.tenant import Tenant  # noqa: E402


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL") or os.environ.get("C02_DATABASE_URL")
    if not url:
        raise SystemExit("definí DATABASE_URL (o C02_DATABASE_URL) con la base de datos")
    return url


def _listar(session: Session) -> int:
    tenants = session.scalars(select(Tenant).order_by(Tenant.slug)).all()
    if not tenants:
        print("no hay tenants")
        return 0
    for tenant in tenants:
        estado = "activo" if tenant.activo else "inactivo"
        print(
            f"{tenant.slug:<24} {tenant.id}  {tenant.nombre:<32} "
            f"plan={tenant.plan:<10} {estado:<8} creado={tenant.creado_en.isoformat()}"
        )
    return 0


def _crear(session: Session, slug: str, nombre: str, plan: str) -> int:
    existente = session.scalar(select(Tenant).where(Tenant.slug == slug))
    if existente is not None:
        raise SystemExit(f"el tenant '{slug}' ya existe ({existente.id})")
    tenant = Tenant(
        slug=slug,
        nombre=nombre,
        plan=plan,
        activo=True,
        creado_en=datetime.now().astimezone(),
    )
    session.add(tenant)
    session.commit()
    print(f"tenant '{slug}' creado: {tenant.id}")
    return 0


def _cambiar_estado(session: Session, slug: str, activo: bool) -> int:
    ten = session.scalar(select(Tenant).where(Tenant.slug == slug))
    if ten is None:
        raise SystemExit(f"no existe el tenant '{slug}'")
    ten.activo = activo
    session.commit()
    print(f"tenant '{slug}' {'activado' if activo else 'desactivado'}")
    return 0


def _esquema_existe(session: Session) -> bool:
    return bool(
        session.execute(
            text("SELECT to_regclass('public.tenants') IS NOT NULL")
        ).scalar()
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Superadmin cross-tenant por CLI")
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("list", help="lista todos los tenants")

    crear = sub.add_parser("create", help="crea un tenant")
    crear.add_argument("slug")
    crear.add_argument("nombre")
    crear.add_argument("plan", nargs="?", default="BASICO")

    activar = sub.add_parser("activate", help="activa un tenant")
    activar.add_argument("slug")

    desactivar = sub.add_parser("deactivate", help="desactiva un tenant")
    desactivar.add_argument("slug")

    args = parser.parse_args(argv)
    engine = create_engine(_database_url())
    with Session(engine) as session:
        if not _esquema_existe(session):
            raise SystemExit("la base no tiene el esquema: corré las migraciones primero")
        if args.comando == "list":
            return _listar(session)
        if args.comando == "create":
            return _crear(session, args.slug, args.nombre, args.plan)
        return _cambiar_estado(session, args.slug, args.comando == "activate")


if __name__ == "__main__":
    raise SystemExit(main())
