"""C-15 contra PostgreSQL real: config, usuarios, exportación y KPIs."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from _admin_pg import AHORA, TZ, motor, requiere_pg, sembrar, sembrar_turno
from sqlalchemy.orm import Session

from app.admin.puertos import UsuarioDuplicado
from app.admin.repositorios import ConfigSQL, ExportacionSQL, ReportesSQL, UsuariosSQL

pytestmark = requiere_pg

DESDE = date(2026, 11, 1)
HASTA = date(2026, 12, 1)


def test_config_roundtrip_y_aislamiento() -> None:
    engine = motor()
    with engine.connect() as conn:
        tx = conn.begin()
        a = sembrar(conn, prefijo="c15cfg-a")
        b = sembrar(conn, prefijo="c15cfg-b")
        tx.commit()

    with Session(engine) as session:
        config = ConfigSQL(session)
        config.actualizar(
            tenant_id=a["tenant"],
            valores={"anticipacion_cancelacion_h": 48},
            ahora=AHORA,
        )
        session.commit()
        assert config.obtener(tenant_id=a["tenant"]) == {"anticipacion_cancelacion_h": 48}
        assert config.obtener(tenant_id=b["tenant"]) == {}


def test_usuarios_roundtrip_y_duplicado() -> None:
    engine = motor()
    with engine.connect() as conn:
        tx = conn.begin()
        ids = sembrar(conn, prefijo="c15usr")
        tx.commit()

    with Session(engine) as session:
        usuarios = UsuariosSQL(session)
        creado = usuarios.crear(
            tenant_id=ids["tenant"],
            nombre="Recepción Demo",
            email="recepcion@c15.test",
            password_hash="hash-ficticio",
            rol="RECEPCION",
            ahora=AHORA,
        )
        session.commit()
        assert creado.activo is True
        emails = [u.email for u in usuarios.listar(tenant_id=ids["tenant"])]
        assert "recepcion@c15.test" in emails
        assert len(emails) == 2
        with pytest.raises(UsuarioDuplicado):
            usuarios.crear(
                tenant_id=ids["tenant"],
                nombre="Otra",
                email="recepcion@c15.test",
                password_hash="otro-hash",
                rol="ADMIN",
                ahora=AHORA,
            )
        session.commit()
        assert len(usuarios.listar(tenant_id=ids["tenant"])) == 2


def test_exportacion_solo_del_tenant() -> None:
    engine = motor()
    with engine.connect() as conn:
        tx = conn.begin()
        a = sembrar(conn, prefijo="c15exp-a")
        b = sembrar(conn, prefijo="c15exp-b")
        tx.commit()

    with Session(engine) as session:
        datos = ExportacionSQL(session).exportar(tenant_id=a["tenant"])

    pacientes = datos["pacientes"]
    assert [fila["id"] for fila in pacientes] == [a["paciente"]]
    assert b["paciente"] not in str(datos)
    texto = str(datos)
    assert "password_hash" not in texto
    assert "hash-ficticio" not in texto


def test_kpis_sql() -> None:
    engine = motor()
    with engine.connect() as conn:
        tx = conn.begin()
        ids = sembrar(conn, prefijo="c15kpi")
        base = datetime(2026, 11, 10, 10, 0, tzinfo=TZ)
        sembrar_turno(
            conn, ids, estado="PRESENTE", origen="RECEPCION",
            inicio=base, creado_en=base - timedelta(days=1),
        )
        sembrar_turno(
            conn, ids, estado="PRESENTE", origen="RESERVA_ONLINE",
            inicio=base + timedelta(hours=1), creado_en=base - timedelta(days=1),
        )
        sembrar_turno(
            conn, ids, estado="AUSENTE", origen="RECEPCION",
            inicio=base + timedelta(hours=2), creado_en=base - timedelta(days=1),
        )
        sembrar_turno(
            conn, ids, estado="PENDIENTE", origen="LISTA_ESPERA",
            inicio=base + timedelta(hours=3), creado_en=base + timedelta(hours=2, minutes=30),
        )
        tx.commit()

    with Session(engine) as session:
        datos = ReportesSQL(session).datos(
            tenant_id=ids["tenant"], desde=DESDE, hasta=HASTA
        )

    assert datos.total_turnos == 4
    assert datos.por_estado == {"PRESENTE": 2, "AUSENTE": 1, "PENDIENTE": 1}
    assert datos.online == 1
    assert datos.reasignados_2h == 1
