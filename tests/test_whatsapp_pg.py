"""C-13 contra PostgreSQL real: RLS y roundtrip de mensajes."""
from __future__ import annotations

from _admin_pg import AHORA, motor, requiere_pg, sembrar
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.whatsapp.repositorios import ConfigWhatsAppSQL, MensajeSQL

pytestmark = requiere_pg


def test_rls_sin_tenant_no_devuelve_mensajes() -> None:
    engine = motor()
    with engine.connect() as conn:
        tx = conn.begin()
        sembrar(conn, prefijo="c13rls")
        tx.commit()

    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM mensajes_wa")).scalar() == 0


def test_roundtrip_de_mensaje_y_config() -> None:
    engine = motor()
    with engine.connect() as conn:
        tx = conn.begin()
        ids = sembrar(conn, prefijo="c13msg")
        tx.commit()

    with Session(engine) as session:
        mensajes = MensajeSQL(session)
        mensaje = mensajes.crear(
            tenant_id=ids["tenant"],
            paciente_id=ids["paciente"],
            turno_id=None,
            plantilla="RECORDATORIO",
            canal="WA",
            cuerpo="Recordatorio de prueba",
            ahora=AHORA,
        )
        session.commit()
        actualizado = mensajes.actualizar(
            tenant_id=ids["tenant"],
            mensaje_id=mensaje.id,
            estado="ENVIADO",
            provider_message_id="SM-PG-1",
            ahora=AHORA,
        )
        session.commit()

        assert actualizado.estado == "ENVIADO"
        assert mensajes.por_provider(
            provider_message_id="SM-PG-1", tenant_id=ids["tenant"]
        ).id == mensaje.id
        assert [m.id for m in mensajes.listar(tenant_id=ids["tenant"])] == [mensaje.id]

        config = ConfigWhatsAppSQL(session)
        assert config.habilitado(tenant_id=ids["tenant"]) is True
        assert config.anticipacion_h(tenant_id=ids["tenant"]) == 24
