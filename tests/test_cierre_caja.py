"""Tasks 6.1–6.30 — cierre diario de caja (TDD rojo primero).

Criterios (spec `cierre-caja`, design D4/D8/D14, RN-CJ-02, Flujo 5):

- El cierre es un **snapshot inmutable** por `(tenant, fecha)`: totales netos por
  medio (excluyen anulados), `total_os` devengado informativo separado de
  `total_os_cobrado` (caja real del medio OS) y `diferencia = efectivo_contado −
  total_efectivo` (sólo efectivo, C10-OQ-2).
- `diferencia ≠ 0` exige `motivo_diferencia` no vacío; la `observacion` es
  opcional y auditable (D3/M2). Motivo vacío o en blanco ⇒ `422` sin persistir.
- El responsable es obligatorio y debe ser un usuario **del tenant**: ausente ⇒
  `422` (el día sigue abierto); de otro tenant ⇒ `404`.
- Un día futuro no se cierra (`422`); uno atrasado sí (C10-OQ-3/M3); un día sin
  movimientos se cierra en cero (C10-OQ-4).
- Segundo cierre del mismo día ⇒ `409 CIERRE_EXISTENTE`; no hay `PATCH`/`DELETE`
  del cierre ni reapertura.
- El estado del día (`abierto`/`cerrado`) es consultable; el cierre de otro
  tenant responde `404`.

Estos `201`/`200` son del borde HTTP (§9): acá se verifica el resultado de
dominio que ese borde traduce.
"""
from __future__ import annotations

import json
from datetime import date

import pytest
from _caja_helpers import U1, U2, U9, HarnessCaja, actor, d3
from conftest import T1, T2
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.caja.puertos import Cierre
from app.caja.servicio import ConflictoCaja
from app.routers.caja import crear_app
from app.turnos.servicio import Invalido, NoEncontrado

FECHA = date(2026, 11, 10)
SIGUIENTE = date(2026, 11, 11)
ANTERIOR = date(2026, 11, 9)
RECEP = {"X-Tenant-Id": T1, "X-User-Id": U1, "X-Rol": "RECEPCION"}


def _ingreso(
    h: HarnessCaja,
    monto: int = 150000,
    *,
    medio: str = "EFECTIVO",
    fecha: date = FECHA,
) -> None:
    h.registrar(monto=monto, medio=medio, fecha=fecha)


def _cerrar(
    h: HarnessCaja,
    *,
    efectivo_contado: int = 0,
    fecha: date = FECHA,
    responsable_id: str = U2,
    motivo_diferencia: str | None = None,
    observacion: str | None = None,
    actor_: object = None,
) -> Cierre:
    return h.cerrar_dia(
        fecha=fecha,
        efectivo_contado=efectivo_contado,
        responsable_id=responsable_id,
        motivo_diferencia=motivo_diferencia,
        observacion=observacion,
        actor_=actor_,  # type: ignore[arg-type]
    )


def _acciones(h: HarnessCaja) -> list[str]:
    return [entrada.accion for entrada in h.auditoria.entradas]


def _entrada_cierre(h: HarnessCaja) -> dict[str, object]:
    entradas = [
        entrada
        for entrada in h.auditoria.entradas
        if entrada.accion == "CIERRE_DIARIO_REGISTRADO"
    ]
    assert len(entradas) == 1
    despues = entradas[0].despues
    assert despues is not None
    return despues


def _rutas(app: FastAPI) -> set[tuple[str, str]]:
    return {
        (metodo, ruta.path)
        for ruta in app.routes
        if hasattr(ruta, "methods")
        for metodo in ruta.methods  # type: ignore[attr-defined]
    }


# ---------------------------------------------------------------------------
# 6.1 — cierre con diferencia cero
# ---------------------------------------------------------------------------


def test_cierre_diferencia_cero() -> None:
    # GIVEN un ingreso de 100000 en efectivo del 2026-11-10.
    h = HarnessCaja()
    _ingreso(h, 100000)

    # WHEN recepción cierra el día contando 100000 en efectivo.
    cierre = _cerrar(h, efectivo_contado=100000, actor_=actor("RECEPCION", user_id=U1))

    # THEN diferencia cero y cierre sellado con su instante.
    assert cierre.fecha == FECHA
    assert cierre.total_efectivo == 100000
    assert cierre.total_transferencia == 0
    assert cierre.total_mp == 0
    assert cierre.total_os_cobrado == 0
    assert cierre.total_os == 0
    assert cierre.efectivo_contado == 100000
    assert cierre.diferencia == 0
    assert cierre.responsable_id == U2
    assert cierre.cerrado_at == h.ahora
    assert h.cierres.obtener(tenant_id=T1, fecha=FECHA) == cierre


# ---------------------------------------------------------------------------
# 6.2 — totales por medio netos
# ---------------------------------------------------------------------------


def test_totales_por_medio_netos() -> None:
    # GIVEN ingresos por los cuatro medios y un egreso de efectivo.
    h = HarnessCaja()
    _ingreso(h, 150000, medio="EFECTIVO")
    _ingreso(h, 30000, medio="TRANSFERENCIA")
    _ingreso(h, 20000, medio="MP")
    _ingreso(h, 40000, medio="OS")
    h.registrar(monto=50000, medio="EFECTIVO", tipo="EGRESO", fecha=FECHA)

    # WHEN se cierra con 100000 contados (150000 − 50000 en efectivo).
    cierre = _cerrar(h, efectivo_contado=100000)

    # THEN los cuatro totales de caja son netos y la diferencia es cero.
    assert cierre.total_efectivo == 100000
    assert cierre.total_transferencia == 30000
    assert cierre.total_mp == 20000
    assert cierre.total_os_cobrado == 40000
    assert cierre.diferencia == 0


# ---------------------------------------------------------------------------
# 6.3 / 6.4 — devengado OS informativo vs caja real del medio OS
# ---------------------------------------------------------------------------


def test_total_os_es_devengado_informativo() -> None:
    # GIVEN L1 aceptada con cobertura_os=40000 y a_cargo_paciente=60000 en efectivo.
    h = HarnessCaja()
    h.imputar(monto_paciente=60000, monto_os=40000, medio="EFECTIVO")

    # WHEN se cierra el día contando 60000 en efectivo.
    cierre = _cerrar(h, efectivo_contado=60000)

    # THEN el devengado queda informado y no altera la caja ni la diferencia.
    assert cierre.total_efectivo == 60000
    assert cierre.total_os_cobrado == 0
    assert cierre.total_os == 40000
    assert cierre.diferencia == 0
    assert (
        cierre.total_efectivo
        + cierre.total_transferencia
        + cierre.total_mp
        + cierre.total_os_cobrado
    ) == 60000


def test_total_os_cobrado_es_caja() -> None:
    # GIVEN un ingreso manual de 40000 con medio OS (cobro efectivo de la obra social).
    h = HarnessCaja()
    _ingreso(h, 40000, medio="OS")

    # WHEN se cierra el día sin efectivo contado.
    cierre = _cerrar(h, efectivo_contado=0)

    # THEN el medio OS es caja real y el devengado informativo no cambia.
    assert cierre.total_os_cobrado == 40000
    assert cierre.total_os == 0


# ---------------------------------------------------------------------------
# 6.5 / 6.6 / 6.7 — diferencia contra efectivo
# ---------------------------------------------------------------------------


def test_diferencia_faltante() -> None:
    # GIVEN total de efectivo de 100000.
    h = HarnessCaja()
    _ingreso(h, 100000)

    # WHEN se cuenta 95000 y se explica el motivo.
    cierre = _cerrar(h, efectivo_contado=95000, motivo_diferencia="faltante de caja")

    # THEN la diferencia negativa es el faltante y el motivo queda persistido.
    assert cierre.diferencia == -5000
    assert cierre.motivo_diferencia == "faltante de caja"


def test_diferencia_sobrante() -> None:
    # GIVEN total de efectivo de 100000.
    h = HarnessCaja()
    _ingreso(h, 100000)

    # WHEN se cuenta 102000 y se explica el motivo.
    cierre = _cerrar(h, efectivo_contado=102000, motivo_diferencia="sobrante de caja")

    # THEN la diferencia positiva es el sobrante.
    assert cierre.diferencia == 2000
    assert cierre.motivo_diferencia == "sobrante de caja"


def test_diferencia_solo_contra_efectivo() -> None:
    # GIVEN efectivo 100000, transferencia 30000 y MP 20000 (sólo el efectivo se cuenta).
    h = HarnessCaja()
    _ingreso(h, 100000, medio="EFECTIVO")
    _ingreso(h, 30000, medio="TRANSFERENCIA")
    _ingreso(h, 20000, medio="MP")

    # WHEN se cierra contando 100000 en efectivo.
    cierre = _cerrar(h, efectivo_contado=100000)

    # THEN la diferencia es cero aunque no se hayan contado los otros medios (C10-OQ-2).
    assert cierre.total_transferencia == 30000
    assert cierre.total_mp == 20000
    assert cierre.diferencia == 0


# ---------------------------------------------------------------------------
# 6.8 — día sin movimientos cierra en cero
# ---------------------------------------------------------------------------


def test_dia_sin_movimientos_cierra_en_cero() -> None:
    # GIVEN un día sin movimientos.
    h = HarnessCaja()
    dia = date(2026, 11, 8)

    # WHEN se cierra con 0 contado y responsable.
    cierre = _cerrar(h, fecha=dia, efectivo_contado=0, responsable_id=U2)

    # THEN el cierre existe con los cuatro totales en cero (C10-OQ-4).
    assert cierre.fecha == dia
    assert (
        cierre.total_efectivo,
        cierre.total_transferencia,
        cierre.total_mp,
        cierre.total_os_cobrado,
        cierre.total_os,
        cierre.efectivo_contado,
        cierre.diferencia,
    ) == (0, 0, 0, 0, 0, 0, 0)
    assert cierre.responsable_id == U2
    assert h.svc.estado_dia(actor(), fecha=dia).estado == "cerrado"


# ---------------------------------------------------------------------------
# 6.9 — segundo cierre del mismo día
# ---------------------------------------------------------------------------


def test_segundo_cierre_409() -> None:
    # GIVEN el 2026-11-10 ya cerrado.
    h = HarnessCaja()
    _ingreso(h, 100000)
    original = _cerrar(h, efectivo_contado=100000)

    # WHEN recepción intenta cerrarlo otra vez.
    with pytest.raises(ConflictoCaja) as excinfo:
        _cerrar(h, efectivo_contado=100000, motivo_diferencia="otro arqueo")

    # THEN 409 CIERRE_EXISTENTE, una sola fila y el cierre original intacto.
    assert excinfo.value.codigo == 409
    assert excinfo.value.codigo_dominio == "CIERRE_EXISTENTE"
    assert h.cierres.total(T1) == 1
    assert h.cierres.obtener(tenant_id=T1, fecha=FECHA) == original
    assert _acciones(h).count("CIERRE_DIARIO_REGISTRADO") == 1


# ---------------------------------------------------------------------------
# 6.10 / 6.11 — diferencia con motivo y observación opcional
# ---------------------------------------------------------------------------


def test_cierre_con_diferencia_y_motivo() -> None:
    # GIVEN total de efectivo de 100000.
    h = HarnessCaja()
    _ingreso(h, 100000)

    # WHEN se cierra con faltante, motivo y observación operativa.
    cierre = _cerrar(
        h,
        efectivo_contado=95000,
        motivo_diferencia="faltante de caja",
        observacion="se revisó el cajón con el responsable",
    )

    # THEN ambos textos se persisten y la auditoría los registra sin copiar la observación.
    assert cierre.diferencia == -5000
    assert cierre.motivo_diferencia == "faltante de caja"
    assert cierre.observacion == "se revisó el cajón con el responsable"
    despues = _entrada_cierre(h)
    assert despues["motivo_diferencia"] == "faltante de caja"
    assert despues["observacion_cargada"] is True
    assert despues["diferencia"] == -5000
    assert "se revisó el cajón con el responsable" not in json.dumps(despues, ensure_ascii=False)


def test_cierre_con_diferencia_y_motivo_sin_observacion_201() -> None:
    # GIVEN total de efectivo de 100000.
    h = HarnessCaja()
    _ingreso(h, 100000)

    # WHEN se cierra con faltante y motivo, sin observación.
    cierre = _cerrar(h, efectivo_contado=95000, motivo_diferencia="faltante de caja")

    # THEN la observación queda NULL: es opcional (D3/M2).
    assert cierre.diferencia == -5000
    assert cierre.observacion is None
    despues = _entrada_cierre(h)
    assert despues["observacion_cargada"] is False


# ---------------------------------------------------------------------------
# 6.12 / 6.13 / 6.14 — motivo obligatorio con diferencia ≠ 0
# ---------------------------------------------------------------------------


def test_cierre_con_diferencia_sin_motivo_422() -> None:
    # GIVEN total de efectivo de 100000 y un faltante sin motivo.
    h = HarnessCaja()
    _ingreso(h, 100000)

    # WHEN se intenta cerrar con 95000 y sin motivo.
    with pytest.raises(Invalido) as excinfo:
        _cerrar(h, efectivo_contado=95000)

    # THEN 422 y ningún cierre persistido.
    assert excinfo.value.codigo == 422
    assert h.cierres.total(T1) == 0
    assert h.svc.estado_dia(actor(), fecha=FECHA).estado == "abierto"


def test_motivo_vacio_422() -> None:
    # GIVEN total de efectivo de 100000.
    h = HarnessCaja()
    _ingreso(h, 100000)

    # WHEN se cierra con motivo vacío aunque haya observación.
    with pytest.raises(Invalido) as excinfo:
        _cerrar(
            h,
            efectivo_contado=95000,
            motivo_diferencia="",
            observacion="se revisó el cajón",
        )

    # THEN 422: una observación no reemplaza al motivo.
    assert excinfo.value.codigo == 422
    assert h.cierres.total(T1) == 0


def test_sobrante_sin_motivo_422() -> None:
    # GIVEN total de efectivo de 100000 y un sobrante sin motivo.
    h = HarnessCaja()
    _ingreso(h, 100000)

    # WHEN se intenta cerrar con 102000 y sin motivo.
    with pytest.raises(Invalido) as excinfo:
        _cerrar(h, efectivo_contado=102000)

    # THEN 422 y ningún cierre.
    assert excinfo.value.codigo == 422
    assert h.cierres.total(T1) == 0


def test_diferencia_cero_sin_motivo_201() -> None:
    # GIVEN total de efectivo de 100000.
    h = HarnessCaja()
    _ingreso(h, 100000)

    # WHEN se cierra con 100000 y sin motivo.
    cierre = _cerrar(h, efectivo_contado=100000)

    # THEN el cierre existe con diferencia cero.
    assert cierre.diferencia == 0
    assert cierre.motivo_diferencia is None
    assert h.cierres.total(T1) == 1


# ---------------------------------------------------------------------------
# 6.16 / 6.17 / 6.18 / 6.19 — responsable del tenant
# ---------------------------------------------------------------------------


def test_dia_con_movimientos_sin_responsable_422() -> None:
    # GIVEN movimientos del 2026-11-10.
    h = HarnessCaja()
    _ingreso(h, 100000)

    # WHEN se cierra sin `responsable_id`.
    with pytest.raises(Invalido) as excinfo:
        _cerrar(h, efectivo_contado=100000, responsable_id=None)  # type: ignore[arg-type]

    # THEN 422, sin cierre y el día sigue abierto.
    assert excinfo.value.codigo == 422
    assert h.cierres.total(T1) == 0
    assert h.svc.estado_dia(actor(), fecha=FECHA).estado == "abierto"


def test_dia_sin_movimientos_sin_responsable_422() -> None:
    # GIVEN un día sin movimientos.
    h = HarnessCaja()
    dia = date(2026, 11, 8)

    # WHEN se cierra sin responsable.
    with pytest.raises(Invalido) as excinfo:
        _cerrar(h, fecha=dia, efectivo_contado=0, responsable_id="")

    # THEN 422 y ningún cierre: el responsable es obligatorio siempre.
    assert excinfo.value.codigo == 422
    assert h.cierres.total(T1) == 0


def test_responsable_otro_tenant_404() -> None:
    # GIVEN un usuario U9 del tenant T2.
    h = HarnessCaja()
    _ingreso(h, 100000)

    # WHEN T1 intenta cerrar con `responsable_id=U9`.
    with pytest.raises(NoEncontrado) as excinfo:
        _cerrar(h, efectivo_contado=100000, responsable_id=U9)

    # THEN 404 y ningún cierre en T1.
    assert excinfo.value.codigo == 404
    assert h.cierres.total(T1) == 0
    # El mismo usuario sí es válido para el día de su propio tenant.
    cierre_t2 = _cerrar(
        h,
        efectivo_contado=0,
        responsable_id=U9,
        actor_=actor("RECEPCION", tenant=T2, user_id=U9),
    )
    assert cierre_t2.tenant_id == T2


def test_responsable_queda_en_el_cierre() -> None:
    # GIVEN el usuario U1 de recepción.
    h = HarnessCaja()
    _ingreso(h, 100000)

    # WHEN U1 cierra el día declarándose responsable.
    cierre = _cerrar(
        h,
        efectivo_contado=100000,
        responsable_id=U1,
        actor_=actor("RECEPCION", user_id=U1),
    )

    # THEN el cierre y la auditoría registran a U1 como responsable y actor.
    assert cierre.responsable_id == U1
    entradas = [
        entrada
        for entrada in h.auditoria.entradas
        if entrada.accion == "CIERRE_DIARIO_REGISTRADO"
    ]
    assert len(entradas) == 1
    assert entradas[0].actor == U1
    assert entradas[0].despues is not None
    assert entradas[0].despues["responsable_id"] == U1


# ---------------------------------------------------------------------------
# 6.20 — efectivo contado negativo
# ---------------------------------------------------------------------------


def test_efectivo_contado_negativo_422() -> None:
    # GIVEN un día abierto.
    h = HarnessCaja()

    # WHEN se intenta cerrar con un efectivo contado negativo (o no entero).
    for invalido in (-1, -100, 1000.5, "0", True):
        with pytest.raises(Invalido) as excinfo:
            _cerrar(h, efectivo_contado=invalido)  # type: ignore[arg-type]
        assert excinfo.value.codigo == 422

    # THEN ningún cierre persistido (N9).
    assert h.cierres.total(T1) == 0


# ---------------------------------------------------------------------------
# 6.21 / 6.22 / 6.23 / 6.24 — día futuro y cierre atrasado
# ---------------------------------------------------------------------------


def test_dia_futuro_no_se_cierra() -> None:
    # GIVEN el reloj en 2026-11-10T10:00:00-03:00.
    h = HarnessCaja()
    h.ahora = d3("2026-11-10")

    # WHEN se intenta cerrar el 2026-11-12.
    with pytest.raises(Invalido) as excinfo:
        _cerrar(h, fecha=date(2026, 11, 12), efectivo_contado=0)

    # THEN 422 y ningún cierre: el día todavía no ocurrió.
    assert excinfo.value.codigo == 422
    assert h.cierres.total(T1) == 0


def test_dia_anterior_sin_cerrar_no_bloquea() -> None:
    # GIVEN el 2026-11-09 sin cierre y el reloj en 2026-11-10.
    h = HarnessCaja()
    h.ahora = d3("2026-11-10")
    assert h.cierres.obtener(tenant_id=T1, fecha=ANTERIOR) is None

    # WHEN U1 registra un ingreso con fecha del 2026-11-10.
    movimiento = h.registrar(fecha="2026-11-10")

    # THEN la operación del día no se bloquea y el 2026-11-09 sigue abierto.
    assert movimiento.fecha == FECHA
    assert h.svc.estado_dia(actor(), fecha=ANTERIOR).estado == "abierto"


def test_cierre_atrasado_se_permite() -> None:
    # GIVEN el 2026-11-09 sin cierre y el reloj en 2026-11-10.
    h = HarnessCaja()
    h.ahora = d3("2026-11-10")
    _ingreso(h, 150000, fecha=ANTERIOR)

    # WHEN U1 cierra el 2026-11-09 con un responsable del tenant.
    cierre = _cerrar(h, fecha=ANTERIOR, efectivo_contado=150000, responsable_id=U1)

    # THEN el cierre atrasado existe y el día queda cerrado (M3/C10-OQ-3).
    assert cierre.fecha == ANTERIOR
    assert cierre.total_efectivo == 150000
    assert h.svc.estado_dia(actor(), fecha=ANTERIOR).estado == "cerrado"


def test_dia_atrasado_cerrado_queda_inmutable() -> None:
    # GIVEN el 2026-11-09 recién cerrado de forma atrasada.
    h = HarnessCaja()
    h.ahora = d3("2026-11-10")
    _ingreso(h, 150000, fecha=ANTERIOR)
    _cerrar(h, fecha=ANTERIOR, efectivo_contado=150000, responsable_id=U1)

    # WHEN U1 intenta registrar un movimiento con fecha del 2026-11-09.
    with pytest.raises(ConflictoCaja) as excinfo:
        h.registrar(monto=1000, medio="EFECTIVO", fecha=ANTERIOR)

    # THEN 409 CIERRE_CERRADO y no se inserta nada.
    assert excinfo.value.codigo_dominio == "CIERRE_CERRADO"
    assert len(h.movimientos.listar_por_fecha(tenant_id=T1, fecha=ANTERIOR)) == 1


# ---------------------------------------------------------------------------
# 6.25 / 6.26 / 6.27 — el cierre no se edita ni se reabre
# ---------------------------------------------------------------------------


def test_cierre_no_se_edita_por_api() -> None:
    # GIVEN el cierre del 2026-11-10.
    h = HarnessCaja()
    _ingreso(h, 100000)
    cierre = _cerrar(h, efectivo_contado=100000)
    app = crear_app(h.svc)
    client = TestClient(app)

    # WHEN se intenta PATCH/DELETE del cierre por colección y por id.
    respuestas = [
        client.patch("/api/caja/cierre", json={"efectivo_contado": 1}, headers=RECEP),
        client.delete("/api/caja/cierre", headers=RECEP),
        client.patch(f"/api/caja/cierre/{cierre.id}", json={"efectivo_contado": 1}, headers=RECEP),
        client.delete(f"/api/caja/cierre/{cierre.id}", headers=RECEP),
    ]

    # THEN nunca 200, y el cierre sigue intacto.
    for respuesta in respuestas:
        assert respuesta.status_code in (404, 405)
    assert not {
        (metodo, ruta)
        for metodo, ruta in _rutas(app)
        if metodo in {"PATCH", "DELETE"} and ruta.startswith("/api/caja/cierre")
    }
    assert h.cierres.obtener(tenant_id=T1, fecha=FECHA) == cierre


def test_reapertura_no_existe() -> None:
    # GIVEN el cierre del 2026-11-10.
    h = HarnessCaja()
    _ingreso(h, 100000)
    cierre = _cerrar(h, efectivo_contado=100000)
    app = crear_app(h.svc)
    client = TestClient(app)

    # WHEN se intenta reabrir por las dos formas del contrato.
    respuestas = [
        client.post("/api/caja/cierre/reabrir", json={}, headers=RECEP),
        client.post(f"/api/caja/cierre/{cierre.id}/reabrir", json={}, headers=RECEP),
    ]

    # THEN 404/405, nunca 200, y no hay ruta de reapertura (C10-OQ-1).
    for respuesta in respuestas:
        assert respuesta.status_code in (404, 405)
    assert not {ruta for _, ruta in _rutas(app) if "reabrir" in ruta}
    assert h.svc.estado_dia(actor(), fecha=FECHA).estado == "cerrado"


def test_dia_cerrado_sigue_bloqueado_tras_intento_de_reapertura() -> None:
    # GIVEN el cierre del 2026-11-10 y un intento de reapertura fallido.
    h = HarnessCaja()
    _ingreso(h, 100000)
    _cerrar(h, efectivo_contado=100000)
    client = TestClient(crear_app(h.svc))
    assert client.post("/api/caja/cierre/reabrir", json={}, headers=RECEP).status_code in (
        404,
        405,
    )

    # WHEN recepción intenta cargar un movimiento con fecha del día cerrado.
    with pytest.raises(ConflictoCaja) as excinfo:
        h.registrar(monto=1000, medio="EFECTIVO", fecha=FECHA)

    # THEN sigue respondiendo 409 CIERRE_CERRADO.
    assert excinfo.value.codigo_dominio == "CIERRE_CERRADO"
    assert len(h.movimientos.listar_por_fecha(tenant_id=T1, fecha=FECHA)) == 1


# ---------------------------------------------------------------------------
# 6.28 / 6.29 / 6.30 — estado del día y aislamiento
# ---------------------------------------------------------------------------


def test_estado_dia_abierto() -> None:
    # GIVEN el 2026-11-11 sin cierre y un ingreso de 30000 por transferencia.
    h = HarnessCaja()
    _ingreso(h, 30000, medio="TRANSFERENCIA", fecha=SIGUIENTE)

    # WHEN se consulta el estado del día.
    estado = h.svc.estado_dia(actor(), fecha=SIGUIENTE)

    # THEN está abierto, sin totales de cierre, con el total del sistema por medio.
    assert estado.fecha == SIGUIENTE
    assert estado.estado == "abierto"
    assert estado.cierre is None
    assert estado.totales == {
        "EFECTIVO": 0,
        "TRANSFERENCIA": 30000,
        "MP": 0,
        "OS": 0,
    }


def test_estado_dia_cerrado() -> None:
    # GIVEN el 2026-11-10 cerrado con sus totales.
    h = HarnessCaja()
    _ingreso(h, 150000)
    cierre = _cerrar(h, efectivo_contado=150000, responsable_id=U2, actor_=actor("ADMIN", user_id=U2))

    # WHEN se consulta el estado del día.
    estado = h.svc.estado_dia(actor(), fecha=FECHA)

    # THEN devuelve el cierre con totales, contado, diferencia, responsable e instante.
    assert estado.estado == "cerrado"
    assert estado.cierre is not None
    assert estado.cierre == cierre
    assert estado.cierre.total_efectivo == 150000
    assert estado.cierre.efectivo_contado == 150000
    assert estado.cierre.diferencia == 0
    assert estado.cierre.responsable_id == U2
    assert estado.cierre.cerrado_at == h.ahora

    # AND una anulación post-cierre no recalcula el snapshot: el cierre conserva
    # sus cifras y los totales vigentes del día bajan a cero (H6).
    movimiento = h.movimientos.listar_por_fecha(tenant_id=T1, fecha=FECHA)[0]
    h.ahora = d3("2026-11-11", hora=9)
    h.anular(movimiento.id)
    posterior = h.svc.estado_dia(actor(), fecha=FECHA)
    assert posterior.totales["EFECTIVO"] == 0
    assert posterior.cierre is not None
    assert posterior.cierre.total_efectivo == 150000
    assert posterior.cierre.efectivo_contado == 150000
    assert posterior.cierre.diferencia == 0
    assert posterior.cierre.cerrado_at == cierre.cerrado_at


def test_cierre_otro_tenant_404() -> None:
    # GIVEN el cierre del 2026-11-10 del tenant T2.
    h = HarnessCaja()
    cierre_t2 = h.cerrar(
        tenant_id=T2, fecha="2026-11-10", efectivo_contado=0, responsable_id=U9
    )

    # WHEN un actor de T1 consulta el cierre del 2026-11-10.
    with pytest.raises(NoEncontrado) as excinfo:
        h.svc.obtener_cierre(actor(), fecha=FECHA)

    # THEN 404 y no expone datos de T2.
    assert excinfo.value.codigo == 404
    # El mismo cierre sí se lee desde su tenant.
    assert h.svc.obtener_cierre(
        actor("RECEPCION", tenant=T2, user_id=U9), fecha=FECHA
    ) == cierre_t2
