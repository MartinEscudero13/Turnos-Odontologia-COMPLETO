"""Tasks 5.3–5.14 y 5.17 — adaptador real del puerto de imputación de C-09.

Reglas verificadas (design D4/D6/D14, spec "Imputación desde presupuesto con dos
tramos" y "Punto de observación de los errores del adaptador"):

- El tramo del paciente es **caja**: un `INGRESO` con `tramo=PACIENTE` y el medio
  recibido; el tramo OS es **devengado informativo** en `cuentas_por_cobrar_os` y
  nunca suma a los totales de caja (D4/M12).
- `medio='OS'` en el tramo del paciente ⇒ `422 MEDIO_OS_RESERVADO` sin escribir
  nada (C10-OQ-5); `medio=None` ⇒ cobro pendiente (D5/§4).
- Idempotencia por `(línea, tramo)` sin el medio (H1): replay idéntico es no-op,
  otro medio u otro monto es `409 IMPUTACION_DUPLICADA`.
- Día cerrado ⇒ `409 CIERRE_CERRADO` sin escrituras; línea de otro tenant ⇒ `404`.
- `imputar_agenda` no crea turnos (M10).
- A través de `POST /api/presupuestos/{id}/aceptar` el mismo fallo es `503` y C-09
  no persiste la aceptación (H5/D2).
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from _caja_helpers import (
    LINEA1,
    PAC1,
    PRESU1,
    U1,
    HarnessCaja,
    actor,
)
from _caja_sql import (
    cablear_caja,
    limpiar,
    motor,
    requiere_pg,
    sembrar_caja,
)
from _presupuesto_helpers import HarnessPresupuesto, presupuesto_vigente
from conftest import T1, T2
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.caja.puertos import (
    CuentaPorCobrarOS,
    ImputacionDuplicada,
    MedioPago,
    Movimiento,
)
from app.caja.servicio import ConflictoCaja, InvalidoCaja
from app.models.turno import Turno
from app.routers.presupuesto import crear_app
from app.turnos.servicio import NoEncontrado

FECHA = date(2026, 11, 10)
MEDIOS_CERO: dict[MedioPago, int] = {
    "EFECTIVO": 0,
    "TRANSFERENCIA": 0,
    "MP": 0,
    "OS": 0,
}


def _del_dia(h: HarnessCaja, fecha: date = FECHA, tenant_id: str = T1) -> list[Movimiento]:
    return list(h.movimientos.listar_por_fecha(tenant_id=tenant_id, fecha=fecha))


def _cuenta(h: HarnessCaja, linea_id: str = LINEA1, tenant_id: str = T1) -> CuentaPorCobrarOS:
    cuenta = h.cuentas.buscar_por_linea(tenant_id=tenant_id, linea_id=linea_id)
    assert cuenta is not None
    return cuenta


def _cerrar_dia(h: HarnessCaja, fecha: date = FECHA) -> None:
    h.cerrar(fecha=fecha.isoformat(), efectivo_contado=0)


# ---------------------------------------------------------------------------
# 5.3 — sólo el tramo del paciente genera un movimiento
# ---------------------------------------------------------------------------


def test_solo_tramo_paciente_crea_un_movimiento() -> None:
    h = HarnessCaja()

    h.imputar(monto_paciente=100000, monto_os=0, medio="EFECTIVO")

    movimientos = _del_dia(h)
    assert len(movimientos) == 1
    movimiento = movimientos[0]
    assert movimiento.tipo == "INGRESO"
    assert movimiento.tramo == "PACIENTE"
    assert movimiento.monto == 100000
    assert movimiento.medio == "EFECTIVO"
    assert movimiento.usuario_id == U1
    assert movimiento.presupuesto_id == PRESU1
    assert movimiento.linea_id == LINEA1
    assert movimiento.paciente_id == PAC1
    assert movimiento.origen == "IMPUTACION"
    assert h.cuentas.total(T1) == 0
    assert h.pendientes.listar(tenant_id=T1) == []


# ---------------------------------------------------------------------------
# 5.4 — el tramo OS es una cuenta por cobrar, no caja (D4)
# ---------------------------------------------------------------------------


def test_tramo_os_crea_cuenta_por_cobrar() -> None:
    h = HarnessCaja()

    h.imputar(monto_paciente=0, monto_os=40000, medio="EFECTIVO")

    assert _del_dia(h) == []
    cuenta = _cuenta(h)
    assert cuenta.monto_centavos == 40000
    assert cuenta.fecha == FECHA
    assert cuenta.presupuesto_id == PRESU1
    assert cuenta.paciente_id == PAC1
    # El devengado no toca ningún total de caja: suma aparte, informativo.
    assert h.svc.totales_del_dia(actor("RECEPCION"), fecha=FECHA) == MEDIOS_CERO
    assert h.movimientos.totales_por_medio(tenant_id=T1, fecha=FECHA) == MEDIOS_CERO
    assert h.cuentas.total_devengado(tenant_id=T1, fecha=FECHA) == 40000


# ---------------------------------------------------------------------------
# 5.5 — dos tramos, dos hechos distintos
# ---------------------------------------------------------------------------


def test_dos_tramos_crean_movimiento_y_cuenta_por_cobrar() -> None:
    h = HarnessCaja()

    h.imputar(monto_paciente=60000, monto_os=40000, medio="EFECTIVO")

    movimientos = _del_dia(h)
    assert len(movimientos) == 1
    assert (movimientos[0].tramo, movimientos[0].monto, movimientos[0].medio) == (
        "PACIENTE",
        60000,
        "EFECTIVO",
    )
    assert [m.medio for m in movimientos] == ["EFECTIVO"]
    assert _cuenta(h).monto_centavos == 40000
    assert sum(m.monto for m in movimientos) == 60000
    assert h.svc.totales_del_dia(actor("RECEPCION"), fecha=FECHA) == {
        **MEDIOS_CERO,
        "EFECTIVO": 60000,
    }


# ---------------------------------------------------------------------------
# 5.6 — el tramo OS nunca genera dos ingresos por el mismo monto (D4)
# ---------------------------------------------------------------------------


def test_os_no_genera_dos_ingresos_por_la_misma_linea() -> None:
    h = HarnessCaja()
    h.imputar(monto_paciente=60000, monto_os=40000, medio="EFECTIVO")

    # Replay exacto: no duplica ni el movimiento ni el devengado.
    h.imputar(monto_paciente=60000, monto_os=40000, medio="EFECTIVO")

    assert len(_del_dia(h)) == 1
    assert h.cuentas.total(T1) == 1
    assert _cuenta(h).monto_centavos == 40000
    assert [m.medio for m in _del_dia(h)] == ["EFECTIVO"]

    # La acreditación de C-12 usará `tramo=OS` y el mismo UNIQUE: un segundo
    # ingreso de OS por la misma línea es imposible.
    h.movimientos.registrar(
        tenant_id=T1,
        fecha=FECHA,
        medio="OS",
        monto=40000,
        tipo="INGRESO",
        usuario_id=U1,
        tramo="OS",
        presupuesto_id=PRESU1,
        linea_id=LINEA1,
        paciente_id=PAC1,
        origen="IMPUTACION",
    )
    with pytest.raises(ImputacionDuplicada):
        h.movimientos.registrar(
            tenant_id=T1,
            fecha=FECHA,
            medio="OS",
            monto=40000,
            tipo="INGRESO",
            usuario_id=U1,
            tramo="OS",
            presupuesto_id=PRESU1,
            linea_id=LINEA1,
            paciente_id=PAC1,
            origen="IMPUTACION",
        )
    assert [m.tramo for m in _del_dia(h)] == ["PACIENTE", "OS"]


# ---------------------------------------------------------------------------
# 5.7 — el medio OS no se acepta en el tramo del paciente (C10-OQ-5)
# ---------------------------------------------------------------------------


def test_medio_os_en_tramo_paciente_422() -> None:
    h = HarnessCaja()

    with pytest.raises(InvalidoCaja) as excinfo:
        h.imputar(monto_paciente=60000, monto_os=40000, medio="OS")

    assert excinfo.value.codigo == 422
    assert excinfo.value.codigo_dominio == "MEDIO_OS_RESERVADO"
    assert str(excinfo.value) == "el medio OS no se acepta en el tramo del paciente"
    assert _del_dia(h) == []
    assert h.cuentas.total(T1) == 0
    assert h.pendientes.listar(tenant_id=T1) == []
    assert h.auditoria.de_tenant(T1) == []


# ---------------------------------------------------------------------------
# 5.8 — el turno asociado se persiste
# ---------------------------------------------------------------------------


def test_turno_se_persiste() -> None:
    h = HarnessCaja()

    h.imputar(monto_paciente=60000, monto_os=0, medio="MP", turno_id="turno-1")

    movimiento = _del_dia(h)[0]
    assert movimiento.turno_id == "turno-1"
    assert movimiento.medio == "MP"


# ---------------------------------------------------------------------------
# 5.9–5.11 — idempotencia por (línea, tramo): el medio no integra la clave (H1)
# ---------------------------------------------------------------------------


def test_replay_identico_no_duplica() -> None:
    h = HarnessCaja()
    h.imputar(monto_paciente=60000, monto_os=0, medio="EFECTIVO")

    h.imputar(monto_paciente=60000, monto_os=0, medio="EFECTIVO")

    assert len(_del_dia(h)) == 1
    assert _del_dia(h)[0].monto == 60000


def test_replay_con_otro_medio_409() -> None:
    h = HarnessCaja()
    h.imputar(monto_paciente=60000, monto_os=0, medio="EFECTIVO")

    with pytest.raises(ConflictoCaja) as excinfo:
        h.imputar(monto_paciente=60000, monto_os=0, medio="TRANSFERENCIA")

    assert excinfo.value.codigo == 409
    assert excinfo.value.codigo_dominio == "IMPUTACION_DUPLICADA"
    movimientos = _del_dia(h)
    assert len(movimientos) == 1
    # El movimiento existente no se modifica: sigue en efectivo.
    assert movimientos[0].medio == "EFECTIVO"
    assert movimientos[0].monto == 60000


def test_replay_con_monto_distinto_409() -> None:
    h = HarnessCaja()
    h.imputar(monto_paciente=60000, monto_os=0, medio="EFECTIVO")

    with pytest.raises(ConflictoCaja) as excinfo:
        h.imputar(monto_paciente=70000, monto_os=0, medio="EFECTIVO")

    assert excinfo.value.codigo == 409
    assert excinfo.value.codigo_dominio == "IMPUTACION_DUPLICADA"
    movimientos = _del_dia(h)
    assert len(movimientos) == 1
    assert movimientos[0].monto == 60000


# ---------------------------------------------------------------------------
# 5.13 — día cerrado: 409 y cero escrituras
# ---------------------------------------------------------------------------


def test_imputacion_en_dia_cerrado_409() -> None:
    h = HarnessCaja()
    _cerrar_dia(h)

    with pytest.raises(ConflictoCaja) as excinfo:
        # Con devengado OS incluido: el rollback también revierte la cuenta.
        h.imputar(monto_paciente=60000, monto_os=40000, medio="EFECTIVO")

    assert excinfo.value.codigo == 409
    assert excinfo.value.codigo_dominio == "CIERRE_CERRADO"
    assert _del_dia(h) == []
    assert h.cuentas.total(T1) == 0
    assert h.pendientes.listar(tenant_id=T1) == []
    assert h.auditoria.de_tenant(T1) == []


# ---------------------------------------------------------------------------
# 5.14 — una línea de otro tenant no se imputa (404)
# ---------------------------------------------------------------------------


def test_imputacion_de_otra_linea_tenant_404() -> None:
    h = HarnessCaja()
    linea_ajena = "linea-9"
    # La línea existe, pero pertenece a T2: imputarla como T1 no resuelve.
    h.lineas_presupuesto.agregar(T2, PRESU1, linea_ajena)

    with pytest.raises(NoEncontrado) as excinfo:
        h.imputar(linea_id=linea_ajena, monto_paciente=60000, monto_os=40000)

    assert excinfo.value.codigo == 404
    assert _del_dia(h) == []
    assert h.pendientes.listar(tenant_id=T1) == []
    assert h.cuentas.total(T1) == 0
    assert h.cuentas.total(T2) == 0
    # Y la línea real de T1 sigue imputable (el 404 no dejó estado raro).
    h.imputar(monto_paciente=60000, monto_os=0, medio="EFECTIVO")
    assert len(_del_dia(h)) == 1


# ---------------------------------------------------------------------------
# 5.12 — imputar no crea turnos (integración con PostgreSQL real)
# ---------------------------------------------------------------------------


@requiere_pg
def test_imputacion_no_crea_turno() -> None:
    engine = motor()
    ids: dict[str, str] = {}
    try:
        with engine.connect() as owner:
            tx = owner.begin()
            ids = sembrar_caja(owner)
            tx.commit()

        with Session(engine) as session:
            caja = cablear_caja(session)
            tenant = uuid.UUID(ids["tenant"])
            antes = session.scalar(
                select(func.count()).select_from(Turno).where(Turno.tenant_id == tenant)
            )
            # Imputar con un turno existente del mismo tenant: el movimiento lo
            # referencia, pero C-10 nunca crea ni modifica un turno (M10).
            caja.adaptador.imputar_caja(
                tenant_id=ids["tenant"],
                presupuesto_id=ids["presupuesto"],
                linea_id=ids["linea"],
                paciente_id=ids["paciente"],
                prestacion_id=ids["prestacion"],
                monto_paciente_centavos=60000,
                monto_os_centavos=40000,
                actor_id=ids["usuario"],
                turno_id=ids["turno"],
                medio="EFECTIVO",
            )
            caja.adaptador.imputar_agenda(
                tenant_id=ids["tenant"],
                presupuesto_id=ids["presupuesto"],
                linea_id=ids["linea"],
                paciente_id=ids["paciente"],
                prestacion_id=ids["prestacion"],
                monto_centavos=100000,
            )
            despues = session.scalar(
                select(func.count()).select_from(Turno).where(Turno.tenant_id == tenant)
            )
            movimiento = caja.movimientos.buscar_imputacion(
                tenant_id=ids["tenant"], linea_id=ids["linea"], tramo="PACIENTE"
            )

        assert antes == 1
        assert despues == 1
        # La imputación sí escribió caja: el conteo de turnos no es un no-op vacío.
        assert movimiento is not None
        assert movimiento.turno_id == ids["turno"]
        assert movimiento.monto == 60000
    finally:
        limpiar(engine, ids)


# ---------------------------------------------------------------------------
# 5.17 — a través de C-09 el mismo fallo es 503 y no persiste la aceptación
# ---------------------------------------------------------------------------


def test_aceptacion_con_dia_cerrado_responde_503() -> None:
    # GIVEN la caja de T1 con el día operativo 2026-11-10 cerrado.
    caja = HarnessCaja()
    _cerrar_dia(caja)

    # Y un presupuesto VIGENTE de una línea, con C-09 apuntando al adaptador real.
    hp = HarnessPresupuesto(imputacion=caja.adaptador)
    presupuesto_id, (linea_id,) = presupuesto_vigente(hp)
    caja.lineas_presupuesto.agregar(T1, presupuesto_id, linea_id)
    client = TestClient(crear_app(hp.svc))
    headers = {"X-Tenant-Id": T1, "X-User-Id": U1, "X-Rol": "RECEPCION"}

    # WHEN recepción acepta la línea con medio válido.
    respuesta = client.post(
        f"/api/presupuestos/{presupuesto_id}/aceptar",
        json={
            "linea_id": linea_id,
            "acepta": True,
            "canal": "CONSULTORIO",
            "medio": "EFECTIVO",
        },
        headers=headers,
    )

    # THEN C-09 traduce el fallo de caja a 503 (H5/D2) y no persiste nada.
    assert respuesta.status_code == 503
    assert hp.aceptaciones.total(T1) == 0
    assert hp.presupuestos.obtener(tenant_id=T1, presupuesto_id=presupuesto_id).estado == "VIGENTE"
    assert _del_dia(caja) == []
    assert caja.pendientes.listar(tenant_id=T1) == []
    assert caja.cuentas.total(T1) == 0
    # Y el motivo real sólo se observa invocando el adaptador directo (H5).
    with pytest.raises(ConflictoCaja) as excinfo:
        caja.imputar(linea_id=linea_id, presupuesto_id=presupuesto_id, monto_paciente=60000)
    assert excinfo.value.codigo_dominio == "CIERRE_CERRADO"
