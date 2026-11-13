"""Task 6.15 — dos webhooks simultáneos del mismo pago contra PostgreSQL real.

No se simula con adaptadores en memoria: la garantía es el `UNIQUE
(mp_payment_id)` de la 009 más el `SELECT … FOR UPDATE` sobre la seña (D8/D11).
Una conexión acredita; la otra, que leyó el pago **después** del lock, responde
`200` con `DUPLICADO`. Un solo `PagoMP`, una sola acreditación y una sola
confirmación del turno.

Se salta sin `C02_DATABASE_URL`. Datos ficticios (RN-GL-03).
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from _senas_helpers import firmar
from _senas_pg import (
    AHORA,
    MONTO,
    PAYMENT_ID,
    REQUEST_ID,
    SECRETO,
    cablear_senas,
    correr_en_paralelo,
    limpiar,
    motor,
    requiere_pg,
    sembrar_sena,
    sembrar_tenant,
    sembrar_turno,
)
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.routers.webhooks_mp import crear_app_webhooks

pytestmark = requiere_pg

URL = "/api/webhooks/mercadopago?data.id=PAG-CARRERA&type=payment"


def _sembrar(engine: Engine) -> dict[str, str]:
    with engine.connect() as conn:
        tx = conn.begin()
        ids = sembrar_tenant(conn, prefijo="c11wh")
        turno = sembrar_turno(conn, ids)
        sena = sembrar_sena(
            conn, ids, turno_id=turno, expira_at=AHORA + timedelta(days=1)
        )
        tx.commit()
    ids["turno"] = turno
    ids["sena"] = sena
    return ids


def _webhook(ids: dict[str, str], session: Session, hook: Any) -> str:
    cableado = cablear_senas(session, al_bloquear=hook)
    cableado.pasarela.aprobar(
        PAYMENT_ID,
        sena_id=ids["sena"],
        monto_centavos=MONTO,
        tenant_id=ids["tenant"],
        turno_id=ids["turno"],
        aprobado_en=AHORA,
    )
    cliente = TestClient(crear_app_webhooks(cableado.webhook))
    respuesta = cliente.post(
        URL,
        json={"type": "payment", "data": {"id": PAYMENT_ID}},
        headers={
            "x-request-id": REQUEST_ID,
            "x-signature": firmar(
                PAYMENT_ID, request_id=REQUEST_ID, secreto=SECRETO
            ),
        },
    )
    return f"{respuesta.status_code}:{respuesta.json().get('resultado')}"


def test_dos_webhooks_simultaneos_acreditan_una_vez() -> None:
    engine = motor()
    ids: dict[str, str] = {}
    try:
        ids = _sembrar(engine)
        resultados, esperas, errores = correr_en_paralelo(
            engine,
            primero="uno",
            acciones={
                "uno": lambda session, hook: _webhook(ids, session, hook),
                "dos": lambda session, hook: _webhook(ids, session, hook),
            },
        )

        assert errores == []
        assert resultados == {
            "uno": "200:ACREDITADA",
            "dos": "200:DUPLICADO",
        }
        # La segunda conexión esperó de verdad al lock de la primera.
        assert esperas["dos"] >= 0.15

        with engine.connect() as inspector:
            pagos = inspector.execute(
                text(
                    "SELECT mp_payment_id, estado, resultado, moneda FROM pagos_mp"
                    " WHERE tenant_id = :t"
                ),
                {"t": ids["tenant"]},
            ).all()
            sena = inspector.execute(
                text(
                    "SELECT estado, acreditada_en FROM senas"
                    " WHERE tenant_id = :t AND id = :s"
                ),
                {"t": ids["tenant"], "s": ids["sena"]},
            ).one()
            turno = inspector.execute(
                text("SELECT estado FROM turnos WHERE id = :id"), {"id": ids["turno"]}
            ).scalar_one()
            auditoria = inspector.execute(
                text(
                    "SELECT count(*) FROM auditoria"
                    " WHERE tenant_id = :t AND accion = 'SENA_ACREDITADA'"
                ),
                {"t": ids["tenant"]},
            ).scalar_one()

        assert [(p.mp_payment_id, p.estado, p.resultado, p.moneda) for p in pagos] == [
            (PAYMENT_ID, "APPROVED", "ACREDITADA", "ARS")
        ]
        assert sena.estado == "ACREDITADA"
        assert sena.acreditada_en is not None
        assert turno == "CONFIRMADO"
        assert auditoria == 1
    finally:
        limpiar(engine, [ids] if ids else [])
