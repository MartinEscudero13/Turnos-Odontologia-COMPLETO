"""Wiring PostgreSQL real de señas para los tests de §6–§8 (C-11).

No es un helper de dominio: es el **cableado de persistencia** con los locks
reales (`SELECT … FOR UPDATE` + `UPDATE … WHERE estado = <esperado>`), más la
posibilidad de pausar la transacción ganadora **después** de tomar el lock de la
seña y antes de commitear, para que la otra conexión tenga que esperarlo de
verdad (mismo patrón que `_caja_sql.UowObservada` en C-10).

Se salta todo sin `C02_DATABASE_URL`. Datos ficticios (RN-GL-03): "Paciente
Demo", "Conducto Demo", `precio_base=10000`, `PORCENTAJE=30` ⇒ `3000`, turno del
`2026-11-20T10:00:00-03:00` y vencimiento `2026-11-14T09:00:00-03:00`.
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.caja.repositorios import AuditoriaSQL
from app.core.transaccion import TransaccionSQL
from app.senas.puertos import AdaptadorPasarelaFake
from app.senas.repositorios import (
    PagoMPRepositorioSQL,
    SenaRepositorioSQL,
    TurnosSenaSQL,
)
from app.senas.webhook import ServicioSenasWebhook
from app.senas.worker import ServicioSenasExpulsion

PG_URL = os.environ.get("C02_DATABASE_URL")
requiere_pg = pytest.mark.skipif(not PG_URL, reason="C02_DATABASE_URL no configurada")

TZ = timezone(timedelta(hours=-3))
AHORA = datetime(2026, 11, 14, 9, 0, tzinfo=TZ)  # el instante del vencimiento
INICIO_TURNO = datetime(2026, 11, 20, 10, 0, tzinfo=TZ)
INICIO_NUEVO = datetime(2026, 11, 25, 10, 0, tzinfo=TZ)
MONTO = 3000
PAYMENT_ID = "PAG-CARRERA"
SECRETO = "secreto-webhook-ficticio-pg"
REQUEST_ID = "req-ficticio-pg"
TS = "1763035200"


def motor() -> Engine:
    assert PG_URL is not None
    return create_engine(PG_URL, future=True)


def _telefono(paciente_id: str) -> str:
    digitos = int(paciente_id.replace("-", ""), 16) % 10**10
    return f"+5491{digitos:010d}"


def sembrar_tenant(conn: Connection, *, prefijo: str) -> dict[str, str]:
    """Tenant + usuario RECEPCION + paciente + prestación (datos ficticios)."""
    ids = {clave: str(uuid.uuid4()) for clave in ("tenant", "usuario", "paciente", "prestacion")}
    conn.execute(
        text("INSERT INTO tenants (id, nombre, slug) VALUES (:id, 'C11 ciclo', :slug)"),
        {"id": ids["tenant"], "slug": f"{prefijo}-{ids['tenant'][:8]}"},
    )
    conn.execute(
        text(
            "INSERT INTO usuarios (id, tenant_id, nombre, email, password_hash, rol)"
            " VALUES (:id, :t, 'Recepción Demo', :email, 'x', 'RECEPCION')"
        ),
        {
            "id": ids["usuario"],
            "t": ids["tenant"],
            "email": f"{prefijo}-{ids['usuario'][:8]}@demo.test",
        },
    )
    conn.execute(
        text(
            "INSERT INTO pacientes (id, tenant_id, nombre, telefono)"
            " VALUES (:id, :t, 'Paciente Demo', :tel)"
        ),
        {"id": ids["paciente"], "t": ids["tenant"], "tel": _telefono(ids["paciente"])},
    )
    conn.execute(
        text(
            "INSERT INTO prestaciones (id, tenant_id, nombre, duracion_min, precio_base)"
            " VALUES (:id, :t, 'Conducto Demo', 30, 10000)"
        ),
        {"id": ids["prestacion"], "t": ids["tenant"]},
    )
    return ids


def sembrar_turno(
    conn: Connection,
    ids: dict[str, str],
    *,
    inicio: datetime = INICIO_TURNO,
    estado: str = "PENDIENTE",
    turno_id: str | None = None,
) -> str:
    turno = turno_id or str(uuid.uuid4())
    conn.execute(
        text(
            "INSERT INTO turnos"
            " (id, tenant_id, profesional_id, sillon_id, paciente_id, prestacion_id,"
            "  inicio, fin, estado, origen)"
            " VALUES (:id, :t, :prof, :sil, :pac, :pres, :inicio, :fin, :estado, 'RESERVA_ONLINE')"
        ),
        {
            "id": turno,
            "t": ids["tenant"],
            "prof": str(uuid.uuid4()),
            "sil": str(uuid.uuid4()),
            "pac": ids["paciente"],
            "pres": ids["prestacion"],
            "inicio": inicio,
            "fin": inicio + timedelta(minutes=30),
            "estado": estado,
        },
    )
    return turno


def sembrar_sena(
    conn: Connection,
    ids: dict[str, str],
    *,
    turno_id: str,
    estado: str = "PENDIENTE",
    expira_at: datetime = AHORA,
    monto: int = MONTO,
    token_hash: str | None = None,
) -> str:
    """Seña coherente con los CHECKs de la 009 (cada estado con su instante)."""
    sena_id = str(uuid.uuid4())
    campos: dict[str, object] = {
        "acreditada_en": None,
        "aplicada_en": None,
        "liberada_en": None,
        "devuelta_en": None,
        "motivo_liberacion": None,
        "concepto_aplicacion": None,
        "movimiento_caja_id": None,
        "motivo_devolucion": None,
    }
    if estado == "ACREDITADA":
        campos["acreditada_en"] = AHORA - timedelta(days=3)
    elif estado == "LIBERADA":
        campos["liberada_en"] = AHORA
        campos["motivo_liberacion"] = "EXPIRACION"
    elif estado == "DEVUELTA":
        campos["devuelta_en"] = AHORA
        campos["motivo_devolucion"] = "POLITICA_CANCELACION"
    conn.execute(
        text(
            "INSERT INTO senas"
            " (id, tenant_id, turno_id, monto_centavos, estado, regla_modo, regla_valor,"
            "  precio_base_centavos, anticipacion_cancelacion_h, expira_at, token_hash,"
            "  acreditada_en, aplicada_en, liberada_en, devuelta_en, motivo_liberacion,"
            "  concepto_aplicacion, motivo_devolucion, movimiento_caja_id, creado_en)"
            " VALUES (:id, :t, :turno, :monto, :estado, 'PORCENTAJE', 30,"
            "  10000, 24, :expira, :token, :acreditada_en, :aplicada_en, :liberada_en,"
            "  :devuelta_en, :motivo_liberacion, :concepto_aplicacion, :motivo_devolucion,"
            "  :movimiento_caja_id, :creado)"
        ),
        {
            "id": sena_id,
            "t": ids["tenant"],
            "turno": turno_id,
            "monto": monto,
            "estado": estado,
            "expira": expira_at,
            "token": token_hash or uuid.uuid4().hex,
            "creado": AHORA - timedelta(days=4),
            **campos,
        },
    )
    return sena_id


@dataclass
class HuecoEspia:
    """`HuecoLiberadoPort` de prueba: cuenta eventos y puede fallar."""

    llamadas: list[tuple[str, str]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def emitir(self, *, tenant_id: str, turno_id: str) -> None:
        with self._lock:
            self.llamadas.append((tenant_id, turno_id))


class SenasObservadas(SenaRepositorioSQL):
    """`SenaRepositorioSQL` que avisa después de tomar el `FOR UPDATE`."""

    def __init__(
        self, session: Session, *, al_bloquear: Callable[[], None] | None = None
    ) -> None:
        super().__init__(session)
        self._al_bloquear = al_bloquear

    def bloquear(self, *, tenant_id: str, sena_id: str):  # type: ignore[no-untyped-def]
        sena = super().bloquear(tenant_id=tenant_id, sena_id=sena_id)
        if self._al_bloquear is not None:
            self._al_bloquear()
        return sena


@dataclass(frozen=True)
class CableadoSenas:
    senas: SenasObservadas
    pagos: PagoMPRepositorioSQL
    turnos: TurnosSenaSQL
    pasarela: AdaptadorPasarelaFake
    auditoria: AuditoriaSQL
    huecos: HuecoEspia
    webhook: ServicioSenasWebhook
    worker: ServicioSenasExpulsion


def cablear_senas(
    session: Session,
    *,
    al_bloquear: Callable[[], None] | None = None,
    huecos: HuecoEspia | None = None,
) -> CableadoSenas:
    """Cablea webhook y expiración con persistencia real sobre `session`."""
    senas = SenasObservadas(session, al_bloquear=al_bloquear)
    pagos = PagoMPRepositorioSQL(session)
    turnos = TurnosSenaSQL(session)
    auditoria = AuditoriaSQL(session)
    pasarela = AdaptadorPasarelaFake()
    espia = huecos if huecos is not None else HuecoEspia()
    webhook = ServicioSenasWebhook(
        senas,
        pagos,
        turnos,
        pasarela,
        auditoria,
        secreto=SECRETO,
        reloj=lambda: AHORA,
        uow_factory=lambda: TransaccionSQL(session),
    )
    worker = ServicioSenasExpulsion(
        senas,
        turnos,
        espia,
        auditoria,
        reloj=lambda: AHORA,
        uow_factory=lambda: TransaccionSQL(session),
    )
    return CableadoSenas(
        senas=senas,
        pagos=pagos,
        turnos=turnos,
        pasarela=pasarela,
        auditoria=auditoria,
        huecos=espia,
        webhook=webhook,
        worker=worker,
    )


def limpiar(engine: Engine, ids: list[dict[str, str]]) -> None:
    """Borra los tenants sembrados (cascade) y libera el engine."""
    if ids:
        with engine.connect() as owner:
            tx = owner.begin()
            for grupo in ids:
                owner.execute(
                    text("DELETE FROM tenants WHERE id = :id"), {"id": grupo["tenant"]}
                )
            tx.commit()
    engine.dispose()


# ---------------------------------------------------------------------------
# Carrera de dos conexiones reales
# ---------------------------------------------------------------------------

ESPERA_MAXIMA = 30
DEMORA_ANTES_DE_LIBERAR = 0.3

Accion = Callable[[Session, Callable[[], None] | None], str]


def correr_en_paralelo(
    engine: Engine, *, primero: str, acciones: dict[str, Accion]
) -> tuple[dict[str, str], dict[str, float], list[BaseException]]:
    """Corre dos acciones con el **primero** pausado con el lock ya tomado.

    El `hook` que recibe cada acción se llama después de `bloquear` la seña: la
    primera transacción se queda con el lock y avisa; la segunda arranca recién
    entonces y tiene que esperar de verdad. Así se prueba la serialización, no un
    orden accidental por tiempos de arranque.
    """
    segundo = next(clave for clave in acciones if clave != primero)
    listo = threading.Event()
    liberar = threading.Event()
    resultados: dict[str, str] = {}
    esperas: dict[str, float] = {}
    errores: list[BaseException] = []

    def correr(clave: str, *, pausa: bool, esperar_primero: bool) -> None:
        try:
            if esperar_primero:
                assert listo.wait(ESPERA_MAXIMA), f"{primero} nunca tomó el lock"
            with Session(engine) as session:

                def al_bloquear() -> None:
                    if pausa:
                        listo.set()
                        if not liberar.wait(ESPERA_MAXIMA):
                            raise RuntimeError("la prueba no liberó el lock")

                inicio = time.monotonic()
                resultados[clave] = acciones[clave](
                    session, al_bloquear if pausa else None
                )
                esperas[clave] = time.monotonic() - inicio
        except BaseException as exc:  # noqa: BLE001 - se reporta en el test
            errores.append(exc)

    hilos = [
        threading.Thread(
            target=correr,
            args=(primero,),
            kwargs={"pausa": True, "esperar_primero": False},
            daemon=True,
        ),
        threading.Thread(
            target=correr,
            args=(segundo,),
            kwargs={"pausa": False, "esperar_primero": True},
            daemon=True,
        ),
    ]
    for hilo in hilos:
        hilo.start()
    assert listo.wait(ESPERA_MAXIMA), f"{primero} nunca tomó el lock"
    time.sleep(DEMORA_ANTES_DE_LIBERAR)
    liberar.set()
    for hilo in hilos:
        hilo.join(timeout=ESPERA_MAXIMA)
        assert not hilo.is_alive()
    return resultados, esperas, errores
