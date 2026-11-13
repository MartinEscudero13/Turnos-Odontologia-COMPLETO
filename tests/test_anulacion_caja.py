"""Tasks 3.1–3.14 — anulación, compensación y ajustes post-cierre (TDD rojo primero).

Reglas verificadas (RN-CJ-02/RN-CJ-03, design D2/D3/D14):
- Nunca hay borrado físico: `anulado=true` + motivo + actor + instante, una sola vez.
- Anular en un día abierto saca el movimiento de los totales y **no** compensa.
- Anular con la fecha del original cerrada crea un compensatorio de tipo inverso,
  mismo medio y monto, fechado el día del registro, y un ajuste
  `AJUSTE_ANULACION` contra ese cierre; la fecha cerrada no recibe movimientos.
- Si el día del registro también está cerrado ⇒ `409 CIERRE_CERRADO` sin anular.
- Un alta en un día cerrado ⇒ `409 CIERRE_CERRADO`.
- El cierre nunca se edita ni se recalcula; el ajuste no suma en ningún total.

La carrera de dos anulaciones simultáneas vive en
`tests/test_anulacion_concurrente_pg.py` (dos conexiones reales a PostgreSQL).
"""
from __future__ import annotations

from datetime import date

import pytest
from _caja_helpers import U2, HarnessCaja, d3
from conftest import T1

from app.caja.puertos import Movimiento
from app.caja.servicio import ConflictoCaja
from app.turnos.servicio import Invalido

FECHA = date(2026, 11, 10)
SIGUIENTE = date(2026, 11, 11)


def _acciones(h: HarnessCaja) -> list[str]:
    return [entrada.accion for entrada in h.auditoria.entradas]


def _movimientos(h: HarnessCaja, fecha: date) -> list[Movimiento]:
    return list(h.movimientos.listar_por_fecha(tenant_id=T1, fecha=fecha))


# ---------------------------------------------------------------------------
# 3.1 — día abierto: anular excluye de totales sin compensar
# ---------------------------------------------------------------------------


def test_anular_dia_abierto_excluye_de_totales() -> None:
    h = HarnessCaja()
    mov = h.registrar(monto=150000, medio="EFECTIVO", fecha="2026-11-10")

    anulado = h.anular(mov.id, motivo="cobro duplicado")

    assert anulado.anulado is True
    assert anulado.motivo_anulacion == "cobro duplicado"
    assert anulado.anulado_por == U2
    assert anulado.anulado_en == h.ahora
    # RN-CJ-03: nunca se borra; el anulado sigue listado con sus valores.
    assert h.movimientos.total(T1) == 1
    assert _movimientos(h, FECHA) == [anulado]
    assert h.movimientos.totales_por_medio(tenant_id=T1, fecha=FECHA)["EFECTIVO"] == 0
    # Día abierto: sin compensatorio ni ajuste (D3).
    assert _movimientos(h, SIGUIENTE) == []
    assert h.ajustes.total(T1) == 0
    # D14: se toma el lock del día del original.
    assert h.uow.bloqueos_dia == [(T1, FECHA)]
    assert "MOVIMIENTO_CAJA_ANULADO" in _acciones(h)
    entrada = next(e for e in h.auditoria.entradas if e.accion == "MOVIMIENTO_CAJA_ANULADO")
    assert entrada.antes == {"anulado": False}
    assert entrada.despues is not None
    assert entrada.despues["anulado"] is True
    assert entrada.despues["compensatorio_id"] is None


# ---------------------------------------------------------------------------
# 3.2 — sin motivo: 422 y el movimiento sigue vigente
# ---------------------------------------------------------------------------


def test_anular_sin_motivo_422() -> None:
    h = HarnessCaja()
    mov = h.registrar(monto=150000, medio="EFECTIVO", fecha="2026-11-10")

    for invalido in (None, "", "   "):
        with pytest.raises(Invalido) as excinfo:
            h.anular(mov.id, motivo=invalido)
        assert excinfo.value.codigo == 422

    actual = h.movimientos.obtener(tenant_id=T1, movimiento_id=mov.id)
    assert actual is not None
    assert actual.anulado is False
    assert h.ajustes.total(T1) == 0


# ---------------------------------------------------------------------------
# 3.3 — segunda anulación: 409 ANULADO, sin segundo compensatorio ni ajuste
# ---------------------------------------------------------------------------


def test_segunda_anulacion_409() -> None:
    h = HarnessCaja()
    mov = h.registrar(monto=150000, medio="EFECTIVO", fecha="2026-11-10")
    primera = h.anular(mov.id, motivo="cobro duplicado")

    h.ahora = d3("2026-11-11", 9)
    with pytest.raises(ConflictoCaja) as excinfo:
        h.anular(mov.id, motivo="otro motivo")

    assert excinfo.value.codigo == 409
    assert excinfo.value.codigo_dominio == "ANULADO"
    actual = h.movimientos.obtener(tenant_id=T1, movimiento_id=mov.id)
    assert actual == primera
    assert actual is not None
    assert actual.anulado_en == d3("2026-11-10", 10)
    assert actual.motivo_anulacion == "cobro duplicado"
    assert h.movimientos.total(T1) == 1
    assert h.movimientos.total(T1) == 1 and h.ajustes.total(T1) == 0
    assert _movimientos(h, SIGUIENTE) == []


# ---------------------------------------------------------------------------
# 3.4 — la anulación conserva monto, medio y tipo originales
# ---------------------------------------------------------------------------


def test_anulacion_conserva_monto_y_medio() -> None:
    h = HarnessCaja()
    mov = h.registrar(
        monto=150000, medio="EFECTIVO", tipo="EGRESO", fecha="2026-11-10"
    )

    anulado = h.anular(mov.id, motivo="carga equivocada")

    assert anulado.monto == 150000
    assert anulado.medio == "EFECTIVO"
    assert anulado.tipo == "EGRESO"
    assert anulado.fecha == FECHA
    assert anulado.usuario_id == mov.usuario_id
    assert anulado.motivo_anulacion == "carga equivocada"
    # El único cambio permitido es la anulación (D2).
    assert anulado.id == mov.id
    assert anulado.origen == mov.origen
    assert anulado.creado_en == mov.creado_en


# ---------------------------------------------------------------------------
# 3.5 — un alta en un día cerrado: 409, nada persistido, cierre intacto
# ---------------------------------------------------------------------------


def test_post_movimiento_en_dia_cerrado_409() -> None:
    h = HarnessCaja()
    cierre = h.cerrar(fecha="2026-11-10", efectivo_contado=0)
    h.cierres.llamadas_cerrar = 0

    with pytest.raises(ConflictoCaja) as excinfo:
        h.registrar(monto=150000, medio="EFECTIVO", fecha="2026-11-10")

    assert excinfo.value.codigo == 409
    assert excinfo.value.codigo_dominio == "CIERRE_CERRADO"
    assert h.movimientos.total(T1) == 0
    assert h.cierres.obtener(tenant_id=T1, fecha=FECHA) == cierre
    assert h.cierres.llamadas_cerrar == 0


# ---------------------------------------------------------------------------
# 3.6 — anular post-cierre crea el compensatorio inverso del día del registro
# ---------------------------------------------------------------------------


def test_anular_post_cierre_crea_compensatorio() -> None:
    h = HarnessCaja()
    m1 = h.registrar(monto=150000, medio="EFECTIVO", fecha="2026-11-10")
    h.cerrar(fecha="2026-11-10", efectivo_contado=150000)
    h.ahora = d3("2026-11-11", 9)

    anulado = h.anular(m1.id, motivo="error de carga")

    assert anulado.anulado is True
    del_dia = _movimientos(h, SIGUIENTE)
    assert len(del_dia) == 1
    compensatorio = del_dia[0]
    assert isinstance(compensatorio, type(m1))
    assert compensatorio.tipo == "EGRESO"
    assert compensatorio.medio == "EFECTIVO"
    assert compensatorio.monto == 150000
    assert compensatorio.origen == "COMPENSACION"
    assert compensatorio.compensa_a_id == m1.id
    assert compensatorio.motivo_anulacion == "error de carga"
    assert compensatorio.anulado is False
    assert compensatorio.fecha == SIGUIENTE
    assert compensatorio.usuario_id == U2
    # D14: lock de la fecha del original y del día del registro.
    assert h.uow.bloqueos_dia == [(T1, FECHA), (T1, SIGUIENTE)]
    assert "MOVIMIENTO_COMPENSATORIO_REGISTRADO" in _acciones(h)


# ---------------------------------------------------------------------------
# 3.7 — el ajuste post-cierre queda referenciado al cierre y al original
# ---------------------------------------------------------------------------


def test_anular_post_cierre_asienta_ajuste() -> None:
    h = HarnessCaja()
    m1 = h.registrar(monto=150000, medio="EFECTIVO", fecha="2026-11-10")
    cierre = h.cerrar(fecha="2026-11-10", efectivo_contado=150000)
    h.ahora = d3("2026-11-11", 9)

    h.anular(m1.id, motivo="error de carga")
    compensatorio = _movimientos(h, SIGUIENTE)[0]
    ajustes = h.ajustes.listar_por_cierre(tenant_id=T1, cierre_id=cierre.id)

    assert len(ajustes) == 1
    ajuste = ajustes[0]
    assert ajuste.tipo == "AJUSTE_ANULACION"
    assert ajuste.cierre_id == cierre.id
    assert ajuste.movimiento_original_id == m1.id
    assert ajuste.cobro_pendiente_id is None
    assert ajuste.monto == 150000
    assert ajuste.medio == "EFECTIVO"
    assert ajuste.motivo == "error de carga"
    assert ajuste.actor_id == U2
    assert ajuste.compensatorio_id == compensatorio.id
    assert "AJUSTE_POST_CIERRE_REGISTRADO" in _acciones(h)


# ---------------------------------------------------------------------------
# 3.8 — la anulación post-cierre no inserta ni edita la fecha cerrada
# ---------------------------------------------------------------------------


def test_anulacion_post_cierre_no_inserta_en_la_fecha_cerrada() -> None:
    h = HarnessCaja()
    m1 = h.registrar(monto=150000, medio="EFECTIVO", fecha="2026-11-10")
    h.cerrar(fecha="2026-11-10", efectivo_contado=150000)
    antes = [(m.id, m.monto, m.medio) for m in _movimientos(h, FECHA)]
    h.ahora = d3("2026-11-11", 9)

    h.anular(m1.id, motivo="error de carga")

    despues = _movimientos(h, FECHA)
    assert [(m.id, m.monto, m.medio) for m in despues] == antes
    assert len(despues) == len(antes)
    assert {m.fecha for m in despues} == {FECHA}
    # El compensatorio sólo existe en el día del registro.
    assert [m.fecha for m in _movimientos(h, SIGUIENTE)] == [SIGUIENTE]


# ---------------------------------------------------------------------------
# 3.9 — el compensatorio no edita ni recalcula el cierre
# ---------------------------------------------------------------------------


def test_compensatorio_no_edita_el_cierre() -> None:
    h = HarnessCaja()
    m1 = h.registrar(monto=150000, medio="EFECTIVO", fecha="2026-11-10")
    cierre = h.cerrar(fecha="2026-11-10", efectivo_contado=150000)
    h.cierres.llamadas_cerrar = 0
    h.ahora = d3("2026-11-11", 9)

    h.anular(m1.id, motivo="error de carga")

    assert h.cierres.obtener(tenant_id=T1, fecha=FECHA) == cierre
    assert cierre.total_efectivo == 150000
    assert cierre.efectivo_contado == 150000
    assert cierre.diferencia == 0
    assert cierre.cerrado_at == d3("2026-11-10", 10)
    # Ningún `UPDATE`/recálculo: el repositorio no vuelve a cerrar el día.
    assert h.cierres.llamadas_cerrar == 0


# ---------------------------------------------------------------------------
# 3.10 — el compensatorio de un egreso es un ingreso del mismo medio
# ---------------------------------------------------------------------------


def test_compensatorio_de_egreso_es_ingreso() -> None:
    h = HarnessCaja()
    egreso = h.registrar(
        monto=20000, medio="TRANSFERENCIA", tipo="EGRESO", fecha="2026-11-10"
    )
    h.cerrar(fecha="2026-11-10", efectivo_contado=0)
    h.ahora = d3("2026-11-11", 9)

    h.anular(egreso.id, motivo="error de carga")

    compensatorio = _movimientos(h, SIGUIENTE)[0]
    assert compensatorio.tipo == "INGRESO"
    assert compensatorio.medio == "TRANSFERENCIA"
    assert compensatorio.monto == 20000
    assert h.movimientos.totales_por_medio(tenant_id=T1, fecha=SIGUIENTE)[
        "TRANSFERENCIA"
    ] == 20000
    # El día cerrado conserva el snapshot: el original anulado no suma.
    assert h.movimientos.totales_por_medio(tenant_id=T1, fecha=FECHA)[
        "TRANSFERENCIA"
    ] == 0


# ---------------------------------------------------------------------------
# 3.11 — el compensatorio descuenta en el día del registro, no en el cerrado
# ---------------------------------------------------------------------------


def test_compensatorio_cuenta_en_dia_del_registro() -> None:
    h = HarnessCaja()
    m1 = h.registrar(monto=150000, medio="EFECTIVO", fecha="2026-11-10")
    h.cerrar(fecha="2026-11-10", efectivo_contado=150000)
    h.ahora = d3("2026-11-11", 9)

    h.anular(m1.id, motivo="error de carga")

    assert h.movimientos.totales_por_medio(tenant_id=T1, fecha=SIGUIENTE)[
        "EFECTIVO"
    ] == -150000
    assert h.movimientos.totales_por_medio(tenant_id=T1, fecha=FECHA)["EFECTIVO"] == 0
    assert [m.fecha for m in _movimientos(h, SIGUIENTE)] == [SIGUIENTE]


# ---------------------------------------------------------------------------
# 3.12 — un compensatorio de un día abierto también se puede anular (N7)
# ---------------------------------------------------------------------------


def test_anular_un_compensatorio() -> None:
    h = HarnessCaja()
    m1 = h.registrar(monto=150000, medio="EFECTIVO", fecha="2026-11-10")
    h.cerrar(fecha="2026-11-10", efectivo_contado=150000)
    h.ahora = d3("2026-11-11", 9)
    h.anular(m1.id, motivo="error de carga")
    compensatorio = _movimientos(h, SIGUIENTE)[0]

    anulado = h.anular(compensatorio.id, motivo="correccion del compensatorio")

    assert anulado.anulado is True
    assert anulado.anulado_por == U2
    assert anulado.motivo_anulacion == "correccion del compensatorio"
    # El día 2026-11-11 está abierto: no se crea un segundo compensatorio.
    assert h.movimientos.total(T1) == 2
    assert _movimientos(h, SIGUIENTE) == [anulado]
    assert h.movimientos.totales_por_medio(tenant_id=T1, fecha=SIGUIENTE)[
        "EFECTIVO"
    ] == 0
    # Sólo el ajuste original de la primera anulación.
    assert h.ajustes.total(T1) == 1


# ---------------------------------------------------------------------------
# 3.13 — si el día del registro también está cerrado: 409 y nada cambia
# ---------------------------------------------------------------------------


def test_dia_del_registro_cerrado_409() -> None:
    h = HarnessCaja()
    m1 = h.registrar(monto=150000, medio="EFECTIVO", fecha="2026-11-10")
    h.cerrar(fecha="2026-11-10", efectivo_contado=150000)
    h.cerrar(fecha="2026-11-11", efectivo_contado=0)
    h.ahora = d3("2026-11-11", 9)

    with pytest.raises(ConflictoCaja) as excinfo:
        h.anular(m1.id, motivo="error de carga")

    assert excinfo.value.codigo == 409
    assert excinfo.value.codigo_dominio == "CIERRE_CERRADO"
    actual = h.movimientos.obtener(tenant_id=T1, movimiento_id=m1.id)
    assert actual is not None
    assert actual.anulado is False
    assert h.movimientos.total(T1) == 1
    assert _movimientos(h, SIGUIENTE) == []
    assert h.ajustes.total(T1) == 0


# ---------------------------------------------------------------------------
# 3.14 — el ajuste no suma en los totales de ningún día
# ---------------------------------------------------------------------------


def test_ajuste_no_suma_en_totales() -> None:
    h = HarnessCaja()
    m1 = h.registrar(monto=150000, medio="EFECTIVO", fecha="2026-11-10")
    cierre = h.cerrar(fecha="2026-11-10", efectivo_contado=150000)
    h.ahora = d3("2026-11-11", 9)
    h.anular(m1.id, motivo="error de carga")

    ajuste = h.ajustes.listar_por_cierre(tenant_id=T1, cierre_id=cierre.id)[0]
    ids_movimientos = {
        m.id
        for m in _movimientos(h, FECHA) + _movimientos(h, SIGUIENTE)
    }
    assert ajuste.id not in ids_movimientos
    assert h.ajustes.total(T1) == 1
    # Totales exactos: el ajuste no aparece como movimiento en ninguno de los días.
    assert h.movimientos.totales_por_medio(tenant_id=T1, fecha=FECHA)["EFECTIVO"] == 0
    assert h.movimientos.totales_por_medio(tenant_id=T1, fecha=SIGUIENTE)[
        "EFECTIVO"
    ] == -150000
    # La suma de movimientos vigentes del día del registro es exactamente el compensatorio.
    total = sum(
        (1 if m.tipo == "INGRESO" else -1) * m.monto
        for m in _movimientos(h, SIGUIENTE)
        if not m.anulado
    )
    assert total == -150000
    assert total != -150000 + ajuste.monto
