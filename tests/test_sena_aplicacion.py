"""Tasks 9.1–9.6, 9.8–9.10 — aplicación de la seña al cobro (§9, D9).

La plata de una seña `ACREDITADA` entra a la caja del día **por el alta de
C-10**: estos tests usan `ServicioCaja` real en memoria, así que verifican
código de producción en las dos puntas (C-11 y C-10) y no un contrato SQL.

Datos ficticios (RN-GL-03): T1, turno TUR-1, `Paciente Demo` PACI-1, usuarios
U1 (RECEPCION) y U2 (ADMIN), `monto=3000`, reloj `2026-11-13T09:00:00-03:00`.
"""
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from _senas_helpers import (
    AHORA,
    PACI1,
    T1,
    TUR1,
    U1,
    U2,
    HarnessSenaAplicacion,
)

from app.caja.servicio import ConflictoCaja
from app.senas.aplicacion import (
    CODIGO_PRESUPUESTO_CON_SENA,
    CODIGO_SENA_YA_APLICADA,
    ServicioSenasAplicacion,
)
from app.senas.puertos import AplicacionCajaMemoria, PresupuestosMemoria
from app.senas.servicio import CODIGO_ESTADO_INVALIDO, ConflictoSena
from app.turnos.servicio import Actor, Prohibido

RECEPCION = Actor(tenant_id=T1, rol="RECEPCION", user_id=U1)
ADMIN = Actor(tenant_id=T1, rol="ADMIN", user_id=U2)


# ---------------------------------------------------------------------------
# 9.1 — aplicar crea un movimiento MP del turno
# ---------------------------------------------------------------------------


def test_aplicar_crea_movimiento_mp() -> None:
    h = HarnessSenaAplicacion()
    sena = h.sembrar_sena(estado="ACREDITADA")

    aplicada = h.svc.aplicar(tenant_id=T1, sena_id=sena.id, actor=RECEPCION, ahora=AHORA)

    assert aplicada.estado == "APLICADA"
    assert aplicada.aplicada_en == AHORA
    assert aplicada.concepto_aplicacion == "TRATAMIENTO"
    assert aplicada.movimiento_caja_id is not None

    movimientos = h.movimientos_del_dia(AHORA.date())
    assert len(movimientos) == 1
    movimiento = movimientos[0]
    assert movimiento.id == aplicada.movimiento_caja_id
    assert movimiento.medio == "MP"
    assert movimiento.monto == 3000
    assert movimiento.tipo == "INGRESO"
    assert movimiento.turno_id == TUR1
    assert movimiento.usuario_id == U1
    assert movimiento.fecha == AHORA.date()


# ---------------------------------------------------------------------------
# 9.2 — un segundo aplicado no crea otro movimiento
# ---------------------------------------------------------------------------


def test_segundo_aplicar_409_sin_movimiento() -> None:
    h = HarnessSenaAplicacion()
    sena = h.sembrar_sena(estado="ACREDITADA")
    h.svc.aplicar(tenant_id=T1, sena_id=sena.id, actor=RECEPCION, ahora=AHORA)

    with pytest.raises(ConflictoSena) as excinfo:
        h.svc.aplicar(tenant_id=T1, sena_id=sena.id, actor=RECEPCION, ahora=AHORA)

    assert excinfo.value.codigo == 409
    assert excinfo.value.codigo_dominio == CODIGO_SENA_YA_APLICADA
    assert len(h.movimientos_del_dia(AHORA.date())) == 1
    assert h.sena(sena).estado == "APLICADA"


# ---------------------------------------------------------------------------
# 9.3 — con el día cerrado la seña no se aplica
# ---------------------------------------------------------------------------


def test_dia_cerrado_409_y_sigue_acreditada() -> None:
    h = HarnessSenaAplicacion()
    sena = h.sembrar_sena(estado="ACREDITADA")
    h.cerrar_dia(AHORA.date())

    with pytest.raises(ConflictoCaja) as excinfo:
        h.svc.aplicar(tenant_id=T1, sena_id=sena.id, actor=RECEPCION, ahora=AHORA)

    assert excinfo.value.codigo == 409
    assert excinfo.value.codigo_dominio == "CIERRE_CERRADO"
    assert h.movimientos_del_dia(AHORA.date()) == []
    assert h.sena(sena).estado == "ACREDITADA"
    assert h.sena(sena).movimiento_caja_id is None


# ---------------------------------------------------------------------------
# 9.4 — una seña pendiente no se aplica
# ---------------------------------------------------------------------------


def test_aplicar_desde_pendiente_409() -> None:
    h = HarnessSenaAplicacion()
    sena = h.sembrar_sena(estado="PENDIENTE")

    with pytest.raises(ConflictoSena) as excinfo:
        h.svc.aplicar(tenant_id=T1, sena_id=sena.id, actor=RECEPCION, ahora=AHORA)

    assert excinfo.value.codigo_dominio == CODIGO_ESTADO_INVALIDO
    assert h.movimientos_del_dia(AHORA.date()) == []
    assert h.sena(sena).estado == "PENDIENTE"


# ---------------------------------------------------------------------------
# 9.5 — el movimiento entra en los totales del día
# ---------------------------------------------------------------------------


def test_movimiento_suma_en_totales_del_dia() -> None:
    h = HarnessSenaAplicacion()
    sena = h.sembrar_sena(estado="ACREDITADA")
    h.svc.aplicar(tenant_id=T1, sena_id=sena.id, actor=RECEPCION, ahora=AHORA)

    respuesta = h.movimientos_http(AHORA.date())

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert [m["medio"] for m in cuerpo["movimientos"]] == ["MP"]
    assert cuerpo["movimientos"][0]["monto"] == 3000
    assert cuerpo["movimientos"][0]["turno_id"] == TUR1
    assert cuerpo["totales_vigentes"]["mp"] == 3000


# ---------------------------------------------------------------------------
# 9.6 — no escribe caja directo: el único camino es el puerto de C-10
# ---------------------------------------------------------------------------


def test_no_escribe_caja_directo() -> None:
    h = HarnessSenaAplicacion()
    sena = h.sembrar_sena(estado="ACREDITADA")
    espia = AplicacionCajaMemoria()
    servicio = ServicioSenasAplicacion(
        h.senas,
        h.turnos,
        espia,
        PresupuestosMemoria(),
        h.auditoria,
        reloj=lambda: AHORA,
    )

    aplicada = servicio.aplicar(
        tenant_id=T1, sena_id=sena.id, actor=RECEPCION, ahora=AHORA
    )

    # El único camino es el puerto: una llamada con los datos del turno.
    assert espia.llamadas == [
        {"tenant_id": T1, "turno_id": TUR1, "monto_centavos": 3000}
    ]
    assert aplicada.movimiento_caja_id == "movimiento-mp-1"
    # Nada se escribió en `movimientos_caja`: C-11 no toca el repositorio.
    assert h.movimientos.total(T1) == 0
    # Y el módulo de dominio no importa el repositorio de caja ni escribe SQL.
    from pathlib import Path

    fuente = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "app"
        / "senas"
        / "aplicacion.py"
    ).read_text(encoding="utf-8")
    assert "INSERT INTO movimientos_caja" not in fuente
    assert "app.caja.repositorios" not in fuente
    assert "MovimientosSQL" not in fuente


# ---------------------------------------------------------------------------
# 9.8 — la cancelación tardía sólo la aplica ADMIN
# ---------------------------------------------------------------------------


def test_cancelacion_tardia_solo_admin() -> None:
    h = HarnessSenaAplicacion()
    sena = h.sembrar_sena(estado="ACREDITADA", turno_estado="CANCELADO")

    with pytest.raises(Prohibido) as excinfo:
        h.svc.aplicar(
            tenant_id=T1,
            sena_id=sena.id,
            actor=RECEPCION,
            concepto="CANCELACION_TARDIA",
            ahora=AHORA,
        )

    assert excinfo.value.codigo == 403
    assert h.movimientos_del_dia(AHORA.date()) == []
    assert h.sena(sena).estado == "ACREDITADA"

    aplicada = h.svc.aplicar(
        tenant_id=T1,
        sena_id=sena.id,
        actor=ADMIN,
        concepto="CANCELACION_TARDIA",
        ahora=AHORA,
    )

    assert aplicada.estado == "APLICADA"
    assert aplicada.concepto_aplicacion == "CANCELACION_TARDIA"
    movimientos = h.movimientos_del_dia(AHORA.date())
    assert len(movimientos) == 1
    assert movimientos[0].medio == "MP"
    assert movimientos[0].turno_id == TUR1


# ---------------------------------------------------------------------------
# 9.9 — un presupuesto aceptado vigente bloquea aplicar
# ---------------------------------------------------------------------------


def test_presupuesto_aceptado_vigente_409() -> None:
    h = HarnessSenaAplicacion()
    sena = h.sembrar_sena(estado="ACREDITADA", paciente_id=PACI1)
    h.presupuestos.marcar(tenant_id=T1, paciente_id=PACI1)

    with pytest.raises(ConflictoSena) as excinfo:
        h.svc.aplicar(tenant_id=T1, sena_id=sena.id, actor=RECEPCION, ahora=AHORA)

    assert excinfo.value.codigo_dominio == CODIGO_PRESUPUESTO_CON_SENA
    assert h.movimientos_del_dia(AHORA.date()) == []
    assert h.sena(sena).estado == "ACREDITADA"
    assert h.sena(sena).movimiento_caja_id is None


# ---------------------------------------------------------------------------
# 9.10 — el ingreso usa el día de la aplicación
# ---------------------------------------------------------------------------

DIA_ACREDITACION = datetime(2026, 11, 10, 10, 0, tzinfo=AHORA.tzinfo)
DIA_APLICACION = datetime(2026, 11, 13, 15, 0, tzinfo=AHORA.tzinfo)


def test_ingreso_usa_el_dia_de_la_aplicacion() -> None:
    h = HarnessSenaAplicacion()
    sena = h.sembrar_sena(
        estado="ACREDITADA",
        acreditada_en=DIA_ACREDITACION,
        turno_inicio=datetime(2026, 11, 20, 9, 0, tzinfo=AHORA.tzinfo),
    )
    h.fijar_ahora(DIA_APLICACION)

    aplicada = h.svc.aplicar(
        tenant_id=T1, sena_id=sena.id, actor=RECEPCION, ahora=DIA_APLICACION
    )

    assert aplicada.estado == "APLICADA"
    movimientos = h.movimientos_del_dia(date(2026, 11, 13))
    assert [m.monto for m in movimientos] == [3000]
    assert movimientos[0].fecha == date(2026, 11, 13)
    # Ni el día de la acreditación ni el del turno.
    assert h.movimientos_del_dia(date(2026, 11, 10)) == []
    assert h.movimientos_del_dia(date(2026, 11, 20)) == []


def test_dia_de_aplicacion_cerrado_409_y_sigue_acreditada() -> None:
    h = HarnessSenaAplicacion()
    sena = h.sembrar_sena(
        estado="ACREDITADA",
        acreditada_en=DIA_ACREDITACION,
        turno_inicio=datetime(2026, 11, 20, 9, 0, tzinfo=AHORA.tzinfo),
    )
    h.fijar_ahora(DIA_APLICACION)
    h.cerrar_dia(date(2026, 11, 13))

    with pytest.raises(ConflictoCaja) as excinfo:
        h.svc.aplicar(
            tenant_id=T1, sena_id=sena.id, actor=RECEPCION, ahora=DIA_APLICACION
        )

    assert excinfo.value.codigo_dominio == "CIERRE_CERRADO"
    assert h.movimientos_del_dia(date(2026, 11, 13)) == []
    assert h.sena(sena).estado == "ACREDITADA"


# Guard de cordura: el día operativo se calcula en `-03:00`, no en UTC. Un
# instante UTC del 14 a las 02:00 es todavía el 13 en el consultorio.
def test_dia_operativo_se_calcula_en_menos_tres() -> None:
    h = HarnessSenaAplicacion()
    momento_utc = datetime(2026, 11, 14, 2, 0, tzinfo=UTC)
    sena = h.sembrar_sena(estado="ACREDITADA")

    h.svc.aplicar(tenant_id=T1, sena_id=sena.id, actor=RECEPCION, ahora=momento_utc)

    assert [m.fecha for m in h.movimientos_del_dia(date(2026, 11, 13))] == [
        date(2026, 11, 13)
    ]
    assert h.movimientos_del_dia(date(2026, 11, 14)) == []
