"""Tasks 8.1–8.7 — carreras de la seña contra PostgreSQL real (D11/D16).

Ninguna de estas pruebas se puede hacer con adaptadores en memoria: la garantía
es el `SELECT … FOR UPDATE` sobre la fila de la **seña** más las transiciones
condicionales (`UPDATE … WHERE estado = <esperado>`). Gana la primera
transacción que **commitea**; la perdedora ve el estado nuevo y no escribe.

Cada escenario corre con dos conexiones independientes y la ganadora queda
pausada **con el lock ya tomado**, así la otra lo espera de verdad y no se prueba
un orden accidental por tiempos de arranque (mismo patrón que C-10 §6).

Datos ficticios (RN-GL-03). Se salta todo sin `C02_DATABASE_URL`.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

from _caja_sql import UowObservada, cablear_caja, sembrar_caja
from _senas_helpers import firmar
from _senas_pg import (
    AHORA,
    INICIO_NUEVO,
    INICIO_TURNO,
    MONTO,
    PAYMENT_ID,
    REQUEST_ID,
    SECRETO,
    cablear_aplicacion,
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
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.caja.repositorios import AuditoriaSQL
from app.core.transaccion import TransaccionSQL
from app.routers.webhooks_mp import crear_app_webhooks
from app.senas.puertos import AdaptadorPasarelaFake, ConfiguracionSenaMemoria
from app.senas.repositorios import SenaRepositorioSQL
from app.senas.servicio import ConflictoSena, ServicioSenas
from app.turnos.servicio import Actor, TurnoError

pytestmark = requiere_pg

URL = "/api/webhooks/mercadopago?data.id=PAG-CARRERA&type=payment"
DEMORA = 0.3


# ---------------------------------------------------------------------------
# Sembrado
# ---------------------------------------------------------------------------


def _sembrar(engine: Engine, *, estado: str = "PENDIENTE", expira_at: datetime | None = None,
             turno_estado: str = "PENDIENTE") -> dict[str, str]:
    with engine.connect() as conn:
        tx = conn.begin()
        ids = sembrar_tenant(conn, prefijo="c11cr")
        turno = sembrar_turno(conn, ids, estado=turno_estado)
        sena = sembrar_sena(
            conn,
            ids,
            turno_id=turno,
            estado=estado,
            expira_at=expira_at if expira_at is not None else AHORA,
        )
        tx.commit()
    ids["turno"] = turno
    ids["sena"] = sena
    return ids


def _estado(engine: Engine, ids: dict[str, str]) -> dict[str, Any]:
    """Estado final de la seña, el turno y los pagos (lectura independiente)."""
    with engine.connect() as conn:
        sena = conn.execute(
            text(
                "SELECT estado, turno_id, acreditada_en, liberada_en, devuelta_en,"
                "       motivo_liberacion, motivo_devolucion"
                "  FROM senas WHERE tenant_id = :t AND id = :s"
            ),
            {"t": ids["tenant"], "s": ids["sena"]},
        ).one()
        turno = conn.execute(
            text("SELECT estado FROM turnos WHERE id = :id"), {"id": ids["turno"]}
        ).one()
        pagos = conn.execute(
            text(
                "SELECT mp_payment_id, estado, resultado FROM pagos_mp"
                " WHERE tenant_id = :t ORDER BY recibido_en"
            ),
            {"t": ids["tenant"]},
        ).all()
        auditoria = conn.execute(
            text(
                "SELECT accion, count(*) AS n FROM auditoria WHERE tenant_id = :t"
                " GROUP BY accion"
            ),
            {"t": ids["tenant"]},
        ).all()
    return {
        "sena": sena,
        "turno": turno.estado,
        "pagos": [tuple(p) for p in pagos],
        "auditoria": {a.accion: a.n for a in auditoria},
    }


# ---------------------------------------------------------------------------
# Acciones
# ---------------------------------------------------------------------------


def _webhook_accion(ids: dict[str, str], *, eventos: dict[str, Any]) -> Callable[..., str]:
    def accion(session: Session, hook: Callable[[], None] | None) -> str:
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
        eventos["huecos"] = list(cableado.huecos.llamadas)
        return f"{respuesta.status_code}:{respuesta.json().get('resultado')}"

    return accion


def _worker_accion(ids: dict[str, str], *, eventos: dict[str, Any]) -> Callable[..., str]:
    def accion(session: Session, hook: Callable[[], None] | None) -> str:
        cableado = cablear_senas(session, al_bloquear=hook)
        liberadas = cableado.worker.procesar_expiraciones(
            tenant_id=ids["tenant"], ahora=AHORA
        )
        eventos["huecos"] = list(cableado.huecos.llamadas)
        return f"liberadas:{len(liberadas)}"

    return accion


# ---------------------------------------------------------------------------
# 8.1 / 8.2 / 8.3 — acreditación vs expiración
# ---------------------------------------------------------------------------


def test_acreditacion_gana_la_carrera() -> None:
    """8.1 — la acreditación commitea primero: ACREDITADA, CONFIRMADO y sin oferta.

    La seña está **vencida** a propósito: el worker tiene trabajo pendiente y se
    bloquea en el `FOR UPDATE` de la transacción ganadora.
    """
    engine = motor()
    ids: dict[str, str] = {}
    try:
        ids = _sembrar(engine, expira_at=AHORA)
        eventos_webhook: dict[str, Any] = {}
        eventos_worker: dict[str, Any] = {}
        resultados, esperas, errores = correr_en_paralelo(
            engine,
            primero="acreditacion",
            acciones={
                "acreditacion": _webhook_accion(ids, eventos=eventos_webhook),
                "expiracion": _worker_accion(ids, eventos=eventos_worker),
            },
        )

        assert errores == []
        assert resultados["acreditacion"] == "200:ACREDITADA"
        assert resultados["expiracion"] == "liberadas:0"
        assert esperas["expiracion"] >= DEMORA / 2
        assert eventos_webhook["huecos"] == []
        assert eventos_worker["huecos"] == []

        final = _estado(engine, ids)
        assert final["sena"].estado == "ACREDITADA"
        assert final["sena"].acreditada_en is not None
        assert final["sena"].liberada_en is None
        assert final["turno"] == "CONFIRMADO"
        assert final["pagos"] == [(PAYMENT_ID, "APPROVED", "ACREDITADA")]
        assert final["auditoria"].get("SENA_ACREDITADA") == 1
        assert "SENA_LIBERADA" not in final["auditoria"]
    finally:
        limpiar(engine, [ids] if ids else [])


def test_expiracion_gana_la_carrera() -> None:
    """8.2 — la expiración commitea primero: 200 `FUERA_DE_TIEMPO`, nunca 500.

    La seña queda `DEVUELTA` (la plata no puede quedar retenida, D4) pero con
    `liberada_en` del barrido: la expiración **ganó** y el webhook sólo registró
    la obligación de devolución sin reabrir el turno ni emitir un segundo hueco.
    """
    engine = motor()
    ids: dict[str, str] = {}
    try:
        ids = _sembrar(engine, expira_at=AHORA)
        eventos_webhook: dict[str, Any] = {}
        eventos_worker: dict[str, Any] = {}
        resultados, esperas, errores = correr_en_paralelo(
            engine,
            primero="expiracion",
            acciones={
                "acreditacion": _webhook_accion(ids, eventos=eventos_webhook),
                "expiracion": _worker_accion(ids, eventos=eventos_worker),
            },
        )

        assert errores == []
        assert resultados["expiracion"] == "liberadas:1"
        assert resultados["acreditacion"] == "200:FUERA_DE_TIEMPO"
        assert "DUPLICADO" not in resultados["acreditacion"]
        assert not resultados["acreditacion"].startswith("500")
        assert esperas["acreditacion"] >= DEMORA / 2

        final = _estado(engine, ids)
        assert final["sena"].estado == "DEVUELTA"
        assert final["sena"].liberada_en is not None  # la expiración ganó
        assert final["sena"].acreditada_en is None
        assert final["sena"].devuelta_en is not None
        assert final["sena"].motivo_liberacion == "EXPIRACION"
        assert final["sena"].motivo_devolucion == "PAGO_FUERA_DE_TIEMPO"
        assert final["turno"] == "CANCELADO"
        assert final["pagos"] == [(PAYMENT_ID, "APPROVED", "FUERA_DE_TIEMPO")]
        # Un solo evento de hueco: el de la expiración. El webhook no reabre nada.
        assert eventos_worker["huecos"] == [(ids["tenant"], ids["turno"])]
        assert eventos_webhook["huecos"] == []
        assert final["auditoria"].get("SENA_LIBERADA") == 1
        assert "SENA_ACREDITADA" not in final["auditoria"]
    finally:
        limpiar(engine, [ids] if ids else [])


def test_el_perdedor_no_pisa() -> None:
    """8.3 — una sola transición, un solo instante ganador, nada lo cambia después."""
    engine = motor()
    ids: dict[str, str] = {}
    try:
        ids = _sembrar(engine, expira_at=AHORA)
        eventos_webhook: dict[str, Any] = {}
        eventos_worker: dict[str, Any] = {}
        correr_en_paralelo(
            engine,
            primero="expiracion",
            acciones={
                "acreditacion": _webhook_accion(ids, eventos=eventos_webhook),
                "expiracion": _worker_accion(ids, eventos=eventos_worker),
            },
        )
        antes = _estado(engine, ids)
        assert antes["sena"].estado == "DEVUELTA"
        assert antes["auditoria"].get("SENA_LIBERADA") == 1

        # Segunda corrida del barrido: no transiciona ni emite un segundo hueco.
        with Session(engine) as session:
            cableado = cablear_senas(session)
            segunda = cableado.worker.procesar_expiraciones(
                tenant_id=ids["tenant"], ahora=AHORA
            )
        assert segunda == []
        assert cableado.huecos.llamadas == []

        # Una notificación posterior con estado "menor" no reescribe el hecho.
        with Session(engine) as session:
            cableado = cablear_senas(session)
            cableado.pasarela.programar(
                mp_payment_id=PAYMENT_ID,
                estado="PENDING",
                sena_id=ids["sena"],
                monto_centavos=MONTO,
                tenant_id=ids["tenant"],
                turno_id=ids["turno"],
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
        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json()["resultado"] == "DUPLICADO"

        despues = _estado(engine, ids)
        assert despues["sena"].estado == antes["sena"].estado
        assert despues["sena"].liberada_en == antes["sena"].liberada_en
        assert despues["sena"].devuelta_en == antes["sena"].devuelta_en
        assert despues["sena"].acreditada_en is None
        assert despues["turno"] == antes["turno"] == "CANCELADO"
        # El ranking no degrada el estado del pago ni duplica la auditoría.
        assert despues["pagos"] == [(PAYMENT_ID, "APPROVED", "FUERA_DE_TIEMPO")]
        assert despues["auditoria"] == antes["auditoria"]
    finally:
        limpiar(engine, [ids] if ids else [])


# ---------------------------------------------------------------------------
# 8.4 — dos reservas del mismo hueco
# ---------------------------------------------------------------------------


def test_dos_reservas_del_mismo_hueco_una_sena() -> None:
    """8.4 — dos reservas al mismo hueco: una gana (201) y una es 409, sin huérfanas.

    Este es el único caso que conserva SQL crudo a propósito: la garantía es el
    `EXCLUDE` de la 003 sobre `turnos`, y el alta pública de C-06 corre sobre
    adaptadores en memoria (su wiring a PostgreSQL es un follow-up declarado de
    C-06), así que no existe un caso de uso con el que ejercerla contra la base.
    Se observa la única forma de ver el UNIQUE/EXCLUDE real: insertar el turno y
    la seña en dos conexiones y comprobar que la perdedora no deja una seña
    apuntando a un turno inexistente.
    """
    engine = motor()
    ids: dict[str, str] = {}
    try:
        with engine.connect() as conn:
            tx = conn.begin()
            ids = sembrar_tenant(conn, prefijo="c11rs")
            tx.commit()
        profesional = str(uuid.uuid4())
        sillon = str(uuid.uuid4())

        def reservar(session: Session, hook: Callable[[], None] | None) -> str:
            turno = str(uuid.uuid4())
            try:
                session.execute(
                    text(
                        "INSERT INTO turnos"
                        " (id, tenant_id, profesional_id, sillon_id, paciente_id,"
                        "  prestacion_id, inicio, fin, estado, origen)"
                        " VALUES (:id, :t, :prof, :sil, :pac, :pres, :inicio, :fin,"
                        "  'PENDIENTE', 'RESERVA_ONLINE')"
                    ),
                    {
                        "id": turno,
                        "t": ids["tenant"],
                        "prof": profesional,
                        "sil": sillon,
                        "pac": ids["paciente"],
                        "pres": ids["prestacion"],
                        "inicio": INICIO_TURNO,
                        "fin": INICIO_TURNO + timedelta(minutes=30),
                    },
                )
                if hook is not None:
                    hook()
                session.execute(
                    text(
                        "INSERT INTO senas"
                        " (id, tenant_id, turno_id, monto_centavos, estado, regla_modo,"
                        "  regla_valor, precio_base_centavos, anticipacion_cancelacion_h,"
                        "  expira_at, token_hash, creado_en)"
                        " VALUES (:id, :t, :turno, :monto, 'PENDIENTE', 'PORCENTAJE', 30,"
                        "  10000, 24, :expira, :token, :creado)"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "t": ids["tenant"],
                        "turno": turno,
                        "monto": MONTO,
                        "expira": AHORA + timedelta(days=1),
                        "token": uuid.uuid4().hex,
                        "creado": AHORA,
                    },
                )
                session.commit()
                return "201"
            except DBAPIError as exc:
                session.rollback()
                estado_sql = getattr(exc.orig, "sqlstate", None) or getattr(
                    exc.orig, "pgcode", None
                )
                if estado_sql == "23P01" or "exclusion" in str(exc.orig).lower():
                    return "409"
                return "500"

        resultados, esperas, errores = correr_en_paralelo(
            engine,
            primero="primera",
            acciones={
                "primera": reservar,
                "segunda": reservar,
            },
        )

        assert errores == []
        assert resultados["primera"] == "201"
        assert resultados["segunda"] == "409"
        assert esperas["segunda"] >= DEMORA / 2
        with engine.connect() as conn:
            turnos = conn.execute(
                text("SELECT count(*) FROM turnos WHERE tenant_id = :t"),
                {"t": ids["tenant"]},
            ).scalar_one()
            senas = conn.execute(
                text("SELECT count(*) FROM senas WHERE tenant_id = :t"),
                {"t": ids["tenant"]},
            ).scalar_one()
            huerfanas = conn.execute(
                text(
                    "SELECT count(*) FROM senas s LEFT JOIN turnos t ON t.id = s.turno_id"
                    " WHERE s.tenant_id = :t AND t.id IS NULL"
                ),
                {"t": ids["tenant"]},
            ).scalar_one()
        assert (turnos, senas, huerfanas) == (1, 1, 0)
    finally:
        limpiar(engine, [ids] if ids else [])


# ---------------------------------------------------------------------------
# 8.5 — dos `aplicar` sobre la misma seña
# ---------------------------------------------------------------------------


def _actor(ids: dict[str, str]) -> Actor:
    return Actor(tenant_id=ids["tenant"], rol="RECEPCION", user_id=ids["usuario"])


def test_dos_aplicar_un_movimiento() -> None:
    """8.5 — caso de uso real de §9: una seña aplicada, un solo `INGRESO MP`.

    Ya no se prueba el contrato SQL: corre `ServicioSenasAplicacion.aplicar`
    (C-11) con la persistencia real y el alta de C-10 sobre la **misma**
    `Session`. El `FOR UPDATE` de la seña es el punto de serialización; la
    perdedora ve `APLICADA` y no crea un segundo movimiento.
    """
    engine = motor()
    ids: dict[str, str] = {}
    try:
        ids = _sembrar(engine, estado="ACREDITADA", expira_at=AHORA + timedelta(days=1))
        with engine.connect() as conn:
            tx = conn.begin()
            conn.execute(
                text("UPDATE turnos SET estado = 'CONFIRMADO' WHERE id = :id"),
                {"id": ids["turno"]},
            )
            tx.commit()

        def aplicar(session: Session, hook: Callable[[], None] | None) -> str:
            caja = cablear_caja(session, ahora=AHORA).servicio
            servicio = cablear_aplicacion(
                session, caja=caja, al_bloquear=hook, ahora=AHORA
            )
            try:
                servicio.aplicar(
                    tenant_id=ids["tenant"],
                    sena_id=ids["sena"],
                    actor=_actor(ids),
                    ahora=AHORA,
                )
                return "200"
            except ConflictoSena as exc:
                return f"409:{exc.codigo_dominio}"

        resultados, esperas, errores = correr_en_paralelo(
            engine,
            primero="uno",
            acciones={"uno": aplicar, "dos": aplicar},
        )

        assert errores == []
        assert resultados == {"uno": "200", "dos": "409:SENA_YA_APLICADA"}
        assert esperas["dos"] >= DEMORA / 2
        with engine.connect() as conn:
            movimientos = conn.execute(
                text(
                    "SELECT medio, monto, tipo FROM movimientos_caja"
                    " WHERE tenant_id = :t"
                ),
                {"t": ids["tenant"]},
            ).all()
            sena = conn.execute(
                text("SELECT estado, movimiento_caja_id FROM senas WHERE id = :s"),
                {"s": ids["sena"]},
            ).one()
        assert [tuple(m) for m in movimientos] == [("MP", MONTO, "INGRESO")]
        assert sena.estado == "APLICADA"
        assert sena.movimiento_caja_id is not None
    finally:
        limpiar(engine, [ids] if ids else [])


# ---------------------------------------------------------------------------
# 8.6 — `aplicar` vs cierre del día
# ---------------------------------------------------------------------------


def test_aplicar_vs_cierre() -> None:
    """8.6 — o el movimiento entra y el cierre lo cuenta, o el cierre gana (409).

    `aplicar` es el caso de uso de §9: delega el hecho de caja en C-10, que toma
    el mismo advisory lock por `(tenant, fecha)` que el cierre, dentro de la
    misma transacción. La seña y el movimiento commitean o revierten juntos.
    """
    engine = motor()
    ids: dict[str, str] = {}
    try:
        with engine.connect() as conn:
            tx = conn.begin()
            ids = sembrar_caja(conn)
            sena = sembrar_sena(
                conn,
                ids,
                turno_id=ids["turno"],
                estado="ACREDITADA",
                expira_at=AHORA + timedelta(days=1),
            )
            ids["sena"] = sena
            tx.commit()
        dia = AHORA.date()

        def aplicar(session: Session, hook: Callable[[], None] | None) -> str:
            def al_bloquear_dia(_fecha: date) -> None:
                if hook is not None:
                    hook()

            caja = cablear_caja(
                session,
                ahora=AHORA,
                uow_factory=lambda: UowObservada(
                    session, al_bloquear=al_bloquear_dia
                ),
            ).servicio
            servicio = cablear_aplicacion(session, caja=caja, ahora=AHORA)
            try:
                servicio.aplicar(
                    tenant_id=ids["tenant"],
                    sena_id=ids["sena"],
                    actor=_actor(ids),
                    ahora=AHORA,
                )
                return "200"
            except TurnoError as exc:
                return f"409:{exc.codigo_dominio}"

        def cerrar(session: Session, hook: Callable[[], None] | None) -> str:
            def al_bloquear_dia(_fecha: date) -> None:
                if hook is not None:
                    hook()

            cableado = cablear_caja(
                session,
                ahora=AHORA,
                uow_factory=lambda: UowObservada(
                    session, al_bloquear=al_bloquear_dia
                ),
            )
            with TransaccionSQL(session):
                cableado.servicio.cerrar_dia(
                    _actor(ids),
                    fecha=dia,
                    efectivo_contado=0,
                    responsable_id=ids["usuario"],
                )
            return "201"

        for primero in ("aplicar", "cierre"):
            with engine.connect() as conn:
                tx = conn.begin()
                conn.execute(
                    text("DELETE FROM auditoria WHERE tenant_id = :t"),
                    {"t": ids["tenant"]},
                )
                # Primero se libera la FK de la seña, después se borran los hechos.
                conn.execute(
                    text(
                        "UPDATE senas SET estado = 'ACREDITADA', aplicada_en = NULL,"
                        " movimiento_caja_id = NULL, concepto_aplicacion = NULL"
                        " WHERE id = :s"
                    ),
                    {"s": ids["sena"]},
                )
                conn.execute(
                    text("DELETE FROM movimientos_caja WHERE tenant_id = :t"),
                    {"t": ids["tenant"]},
                )
                conn.execute(
                    text("DELETE FROM cierres_diarios WHERE tenant_id = :t"),
                    {"t": ids["tenant"]},
                )
                tx.commit()

            resultados, esperas, errores = correr_en_paralelo(
                engine,
                primero=primero,
                acciones={"aplicar": aplicar, "cierre": cerrar},
            )

            assert errores == []
            assert resultados["cierre"] == "201"
            assert esperas["cierre" if primero == "aplicar" else "aplicar"] >= DEMORA / 2
            with engine.connect() as conn:
                cierre = conn.execute(
                    text(
                        "SELECT total_mp FROM cierres_diarios"
                        " WHERE tenant_id = :t AND fecha = :f"
                    ),
                    {"t": ids["tenant"], "f": dia},
                ).one()
                movimientos = conn.execute(
                    text(
                        "SELECT monto FROM movimientos_caja"
                        " WHERE tenant_id = :t AND fecha = :f AND medio = 'MP'"
                        "  AND anulado = false"
                    ),
                    {"t": ids["tenant"], "f": dia},
                ).all()
                sena = conn.execute(
                    text("SELECT estado FROM senas WHERE id = :s"),
                    {"s": ids["sena"]},
                ).scalar_one()

            if primero == "aplicar":
                assert resultados["aplicar"] == "200"
                assert cierre.total_mp == MONTO
                assert [m.monto for m in movimientos] == [MONTO]
                assert sena == "APLICADA"
            else:
                assert resultados["aplicar"] == "409:CIERRE_CERRADO"
                assert cierre.total_mp == 0
                assert movimientos == []
                assert sena == "ACREDITADA"
            # Invariante central: el cierre cuenta exactamente lo del día.
            assert cierre.total_mp == sum(m.monto for m in movimientos)
    finally:
        limpiar(engine, [ids] if ids else [])


# ---------------------------------------------------------------------------
# 8.7 — reprogramación vs webhook
# ---------------------------------------------------------------------------


def test_reprogramacion_vs_webhook() -> None:
    """8.7 — la seña queda atada al turno nuevo; el webhook confirma **ese**.

    El handler lee `senas.turno_id` **después** del `FOR UPDATE`, nunca el
    `turno_id` de la metadata (D11). Si la reprogramación commitea primero, el
    pago confirma el turno nuevo; si el webhook commitea primero, acredita el
    turno vigente en ese instante y la transferencia posterior mueve la seña
    `ACREDITADA` (contrato de §10), sin reescribir el turno ya confirmado.
    """
    for primero in ("reprogramacion", "webhook"):
        engine = motor()
        ids: dict[str, str] = {}
        try:
            with engine.connect() as conn:
                tx = conn.begin()
                ids = sembrar_tenant(conn, prefijo="c11rp")
                turno = sembrar_turno(conn, ids, inicio=INICIO_TURNO)
                nuevo = sembrar_turno(conn, ids, inicio=INICIO_NUEVO)
                sena = sembrar_sena(
                    conn,
                    ids,
                    turno_id=turno,
                    expira_at=AHORA + timedelta(days=10),
                )
                tx.commit()
            ids["turno"] = turno
            ids["nuevo"] = nuevo
            ids["sena"] = sena

            def reprogramar(session: Session, hook: Callable[[], None] | None, ids: dict[str, str] = ids) -> str:
                servicio = ServicioSenas(
                    SenaRepositorioSQL(session),
                    ConfiguracionSenaMemoria(),
                    AdaptadorPasarelaFake(),
                    AuditoriaSQL(session),
                    reloj=lambda: AHORA,
                    uow_factory=lambda: TransaccionSQL(session),
                )
                with TransaccionSQL(session):
                    SenaRepositorioSQL(session).bloquear(
                        tenant_id=ids["tenant"], sena_id=ids["sena"]
                    )
                    if hook is not None:
                        hook()
                    session.execute(
                        text(
                            "UPDATE turnos SET estado = 'REPROGRAMADO' WHERE id = :id"
                        ),
                        {"id": ids["turno"]},
                    )
                    # Caso de uso real de §10: transfiere la seña al turno nuevo.
                    transferida = servicio.transferir_a_turno(
                        tenant_id=ids["tenant"],
                        turno_anterior=ids["turno"],
                        turno_nuevo=ids["nuevo"],
                        turno_inicio=INICIO_NUEVO,
                        ahora=AHORA,
                    )
                    assert transferida is not None
                return "200"

            eventos: dict[str, Any] = {}
            resultados, esperas, errores = correr_en_paralelo(
                engine,
                primero=primero,
                acciones={
                    "webhook": _webhook_accion(ids, eventos=eventos),
                    "reprogramacion": reprogramar,
                },
            )

            assert errores == []
            assert resultados["reprogramacion"] == "200"
            assert resultados["webhook"] == "200:ACREDITADA"
            assert esperas["webhook" if primero == "reprogramacion" else "reprogramacion"] >= DEMORA / 2

            with engine.connect() as conn:
                sena_final = conn.execute(
                    text("SELECT estado, turno_id FROM senas WHERE id = :s"),
                    {"s": ids["sena"]},
                ).one()
                estados = {
                    str(fila.id): fila.estado
                    for fila in conn.execute(
                        text(
                            "SELECT id, estado FROM turnos WHERE tenant_id = :t"
                        ),
                        {"t": ids["tenant"]},
                    ).all()
                }

            # La seña termina atada al turno nuevo, nunca al original.
            assert sena_final.estado == "ACREDITADA"
            assert str(sena_final.turno_id) == ids["nuevo"]
            assert estados[ids["turno"]] == "REPROGRAMADO"
            if primero == "reprogramacion":
                # El webhook leyó `turno_id` después del lock: confirmó el nuevo.
                assert estados[ids["nuevo"]] == "CONFIRMADO"
            else:
                # El pago acreditó el turno vigente en ese instante; la
                # transferencia posterior mueve la seña ACREDITADA (§10) y no
                # reescribe el turno ya confirmado.
                assert estados[ids["nuevo"]] == "PENDIENTE"
        finally:
            limpiar(engine, [ids] if ids else [])
