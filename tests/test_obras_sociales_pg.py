"""C-12 contra PostgreSQL real: RLS, roundtrip de repositorios y liquidación.

Cada test usa tenants nuevos con ids aleatorios, así no depende de datos previos.
Se salta todo sin `C02_DATABASE_URL`.
"""
from __future__ import annotations

from datetime import date

import pytest
from _obras_sociales_pg import AHORA, motor, requiere_pg, sembrar
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.caja.repositorios import AuditoriaSQL
from app.obras_sociales.puertos import ObraSocialDuplicada
from app.obras_sociales.repositorios import (
    CoberturaSQL,
    LiquidacionSQL,
    ObraSocialSQL,
    PacienteObraSocialSQL,
    PrestacionPrecioSQL,
    TurnosAtendidosSQL,
)
from app.obras_sociales.servicio import ServicioObrasSociales
from app.turnos.servicio import Actor, NoEncontrado

pytestmark = requiere_pg


def _actor(tenant_id: str, rol: str = "ADMIN") -> Actor:
    return Actor(tenant_id=tenant_id, rol=rol, user_id="usuario-pg")


def _servicio(session: Session) -> ServicioObrasSociales:
    return ServicioObrasSociales(
        ObraSocialSQL(session),
        CoberturaSQL(session),
        LiquidacionSQL(session),
        TurnosAtendidosSQL(session),
        PacienteObraSocialSQL(session),
        PrestacionPrecioSQL(session),
        AuditoriaSQL(session),
        reloj=lambda: AHORA,
    )


def test_rls_sin_tenant_no_devuelve_filas() -> None:
    engine = motor()
    with engine.connect() as conn:
        tx = conn.begin()
        sembrar(conn, prefijo="c12rls")
        tx.commit()

    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM obras_sociales")).scalar() == 0
        assert conn.execute(text("SELECT count(*) FROM coberturas")).scalar() == 0
        assert conn.execute(text("SELECT count(*) FROM liquidaciones")).scalar() == 0


def test_roundtrip_y_aislamiento_entre_tenants() -> None:
    engine = motor()
    with engine.connect() as conn:
        tx = conn.begin()
        a = sembrar(conn, prefijo="c12a")
        b = sembrar(conn, prefijo="c12b")
        tx.commit()

    # Tenant A: OS + cobertura 50% con tope 4000 y link del paciente.
    with Session(engine) as session:
        obras = ObraSocialSQL(session)
        os_a = obras.crear(tenant_id=a["tenant"], nombre="OS PG A", ahora=AHORA)
        CoberturaSQL(session).upsert(
            tenant_id=a["tenant"],
            obra_social_id=os_a.id,
            prestacion_id=a["prestacion"],
            modo="PORCENTAJE",
            valor=50,
            tope_centavos=4000,
            ahora=AHORA,
        )
        session.execute(
            text("UPDATE pacientes SET obra_social_id = :os WHERE id = :id"),
            {"os": os_a.id, "id": a["paciente"]},
        )
        session.commit()

    with Session(engine) as session:
        svc = _servicio(session)
        liquidacion = svc.generar_liquidacion(
            _actor(a["tenant"]),
            obra_social_id=os_a.id,
            desde=date(2026, 11, 1),
            hasta=date(2026, 12, 1),
        )
        session.commit()

        assert liquidacion.total_centavos == 4000
        assert [linea.monto_centavos for linea in liquidacion.lineas] == [4000]

        # Un actor del tenant B no ve nada del tenant A.
        assert svc.listar_obras_sociales(_actor(b["tenant"])) == []
        with pytest.raises(NoEncontrado):
            svc.obtener_liquidacion(_actor(b["tenant"]), liquidacion_id=liquidacion.id)


def test_unique_de_obra_social_no_rompe_la_sesion() -> None:
    engine = motor()
    with engine.connect() as conn:
        tx = conn.begin()
        a = sembrar(conn, prefijo="c12dup")
        tx.commit()

    with Session(engine) as session:
        obras = ObraSocialSQL(session)
        obras.crear(tenant_id=a["tenant"], nombre="OS Duplicada", ahora=AHORA)
        session.commit()
        with pytest.raises(ObraSocialDuplicada):
            obras.crear(tenant_id=a["tenant"], nombre="OS Duplicada", ahora=AHORA)
        session.commit()
        assert [obra.nombre for obra in obras.listar(tenant_id=a["tenant"])] == [
            "OS Duplicada"
        ]
