"""Tasks 4.1–4.8 — cobros pendientes (`medio=NULL` de C-09) y su cobro.

Reglas verificadas (design D5/D14, RN-CJ-01/RN-CJ-02, spec "Cobros pendientes"):
- Una imputación sin medio crea **un** cobro pendiente por línea, sin movimiento y
  sin sumar a los totales; un tramo en 0 no crea nada.
- Cobrarlo crea el `INGRESO` con la trazabilidad de la línea (`tramo=PACIENTE`),
  resuelve el pendiente (`resuelto_en` + `movimiento_id`) y audita ambos hechos.
- Un pendiente resuelto no se cobra dos veces (`409 COBRO_YA_RESUELTO`).
- El replay sin medio nunca crea un segundo pendiente (UNIQUE pleno, H1) y el
  replay con otro medio es `409 IMPUTACION_DUPLICADA` (el medio no integra la
  clave de idempotencia).
- Si la fecha del pendiente tiene cierre, el cobro se fecha el día del registro
  y asienta un ajuste `COBRO_PENDIENTE` contra ese cierre, que no se recalcula.
- Una imputación sin medio en un día cerrado ⇒ `409 CIERRE_CERRADO` sin escribir.
- D14: el lock del día se toma dentro de la unidad de trabajo antes de escribir.

El `201` del escenario es del borde HTTP (§9); esta capa verifica el resultado de
dominio (`ResultadoCobro`) que ese borde traduce a `201`.
"""
from __future__ import annotations

from datetime import date

import pytest
from _caja_helpers import (
    LINEA1,
    PAC1,
    PRESU1,
    U1,
    HarnessCaja,
    d3,
)
from conftest import T1, T2

from app.caja.puertos import CobroPendiente, Movimiento
from app.caja.servicio import ConflictoCaja

FECHA = date(2026, 11, 10)
SIGUIENTE = date(2026, 11, 11)


def _acciones(h: HarnessCaja) -> list[str]:
    return [entrada.accion for entrada in h.auditoria.entradas]


def _movimientos(h: HarnessCaja, fecha: date, tenant_id: str = T1) -> list[Movimiento]:
    return list(h.movimientos.listar_por_fecha(tenant_id=tenant_id, fecha=fecha))


def _pendiente(h: HarnessCaja, *, monto: int = 60000) -> CobroPendiente:
    creado = h.imputar_tramo(monto=monto, medio=None, fecha=FECHA.isoformat())
    assert isinstance(creado, CobroPendiente)
    return creado


# ---------------------------------------------------------------------------
# 4.1 — imputación sin medio: un pendiente, ningún movimiento
# ---------------------------------------------------------------------------


def test_imputacion_sin_medio_crea_pendiente_sin_movimiento() -> None:
    # GIVEN L1 de a_cargo_paciente=60000 y cobertura_os=0 (sin devengado OS).
    h = HarnessCaja()

    # WHEN el puerto imputa L1 con medio=NULL y fecha operativa 2026-11-10.
    creado = h.imputar_tramo(monto=60000, medio=None, fecha="2026-11-10")

    # THEN un pendiente de 60000 para L1 fechado 2026-11-10.
    assert isinstance(creado, CobroPendiente)
    pendientes = h.pendientes.listar(tenant_id=T1)
    assert pendientes == [creado]
    assert creado.monto_centavos == 60000
    assert creado.fecha == FECHA
    assert creado.linea_id == LINEA1
    assert creado.presupuesto_id == PRESU1
    assert creado.paciente_id == PAC1
    assert creado.actor_id == U1
    assert creado.resuelto_en is None
    assert creado.movimiento_id is None
    # Sin movimiento y sin total: el pendiente no es un hecho de caja.
    assert h.movimientos.total(T1) == 0
    assert h.movimientos.totales_por_medio(tenant_id=T1, fecha=FECHA) == {
        "EFECTIVO": 0,
        "TRANSFERENCIA": 0,
        "MP": 0,
        "OS": 0,
    }
    assert _movimientos(h, FECHA) == []
    # D14: el lock del día operativo se toma antes de escribir.
    assert h.uow.bloqueos_dia == [(T1, FECHA)]
    # Auditoría con ids y montos, sin PHI.
    registros = h.auditoria.de_accion("COBRO_PENDIENTE_REGISTRADO")
    assert len(registros) == 1
    assert registros[0].entidad_id == creado.id
    assert registros[0].despues is not None
    assert registros[0].despues["linea_id"] == LINEA1
    assert registros[0].despues["monto"] == 60000
    assert registros[0].despues["fecha"] == FECHA.isoformat()


# ---------------------------------------------------------------------------
# 4.2 — cobrar el pendiente crea el movimiento y audita ambos hechos
# ---------------------------------------------------------------------------


def test_cobrar_pendiente_crea_movimiento_y_audita() -> None:
    h = HarnessCaja()
    pendiente = _pendiente(h)

    resultado = h.cobrar(pendiente.id, medio="TRANSFERENCIA")

    # THEN un INGRESO de 60000 con la trazabilidad de L1 y el medio elegido.
    movimiento = resultado.movimiento
    assert movimiento.tipo == "INGRESO"
    assert movimiento.monto == 60000
    assert movimiento.medio == "TRANSFERENCIA"
    assert movimiento.fecha == FECHA
    assert movimiento.origen == "IMPUTACION"
    assert movimiento.tramo == "PACIENTE"
    assert movimiento.presupuesto_id == PRESU1
    assert movimiento.linea_id == LINEA1
    assert movimiento.paciente_id == PAC1
    assert movimiento.usuario_id == U1
    assert movimiento.anulado is False
    # El pendiente queda resuelto con instante y movimiento.
    assert resultado.pendiente.id == pendiente.id
    assert resultado.pendiente.resuelto_en == h.ahora
    assert resultado.pendiente.movimiento_id == movimiento.id
    assert resultado.pendiente.monto_centavos == 60000
    # Día abierto: sin ajuste post-cierre.
    assert resultado.ajuste is None
    assert h.ajustes.total(T1) == 0
    assert _movimientos(h, FECHA) == [movimiento]
    assert h.movimientos.totales_por_medio(tenant_id=T1, fecha=FECHA)[
        "TRANSFERENCIA"
    ] == 60000
    # Ambos hechos auditados: alta del pendiente y resolución.
    assert _acciones(h) == [
        "COBRO_PENDIENTE_REGISTRADO",
        "MOVIMIENTO_CAJA_REGISTRADO",
        "COBRO_PENDIENTE_RESUELTO",
    ]
    resolucion = h.auditoria.de_accion("COBRO_PENDIENTE_RESUELTO")[0]
    assert resolucion.entidad_id == pendiente.id
    assert resolucion.despues is not None
    assert resolucion.despues["movimiento_id"] == movimiento.id
    assert resolucion.despues["medio"] == "TRANSFERENCIA"


# ---------------------------------------------------------------------------
# 4.3 — un pendiente resuelto no se cobra dos veces
# ---------------------------------------------------------------------------


def test_pendiente_resuelto_no_se_cobra_dos_veces() -> None:
    h = HarnessCaja()
    pendiente = _pendiente(h)
    primero = h.cobrar(pendiente.id, medio="TRANSFERENCIA")

    with pytest.raises(ConflictoCaja) as excinfo:
        h.cobrar(pendiente.id, medio="EFECTIVO")

    assert excinfo.value.codigo == 409
    assert excinfo.value.codigo_dominio == "COBRO_YA_RESUELTO"
    # Sigue habiendo un solo movimiento y el pendiente conserva su resolución.
    assert h.movimientos.total(T1) == 1
    assert _movimientos(h, FECHA) == [primero.movimiento]
    actual = h.pendientes.obtener(tenant_id=T1, pendiente_id=pendiente.id)
    assert actual is not None
    assert actual.resuelto_en == primero.pendiente.resuelto_en
    assert actual.movimiento_id == primero.movimiento.id
    assert h.movimientos.totales_por_medio(tenant_id=T1, fecha=FECHA)[
        "TRANSFERENCIA"
    ] == 60000
    assert h.movimientos.totales_por_medio(tenant_id=T1, fecha=FECHA)["EFECTIVO"] == 0
    # La resolución se auditó una sola vez.
    assert len(h.auditoria.de_accion("COBRO_PENDIENTE_RESUELTO")) == 1


# ---------------------------------------------------------------------------
# 4.4 — el replay sin medio no crea un segundo pendiente (H1)
# ---------------------------------------------------------------------------


def test_replay_sin_medio_no_crea_segundo_pendiente() -> None:
    h = HarnessCaja()
    pendiente = _pendiente(h)

    # Replay con el pendiente abierto: devuelve el mismo, no crea otro.
    abierto = h.imputar_tramo(monto=60000, medio=None, fecha="2026-11-10")
    assert isinstance(abierto, CobroPendiente)
    assert abierto.id == pendiente.id
    assert h.pendientes.total(T1) == 1
    assert h.movimientos.total(T1) == 0

    # Cobrado el pendiente, otro replay tampoco crea pendiente ni movimiento.
    cobro = h.cobrar(pendiente.id, medio="TRANSFERENCIA")
    despues_del_cobro = h.imputar_tramo(monto=60000, medio=None, fecha="2026-11-10")
    assert isinstance(despues_del_cobro, Movimiento)
    assert despues_del_cobro.id == cobro.movimiento.id
    assert h.pendientes.total(T1) == 1
    assert h.movimientos.total(T1) == 1
    assert len(h.pendientes.listar(tenant_id=T1)) == 1

    # La misma línea en T2 sí puede tener su propio pendiente (aislamiento).
    otro_tenant = h.imputar_tramo(medio=None, fecha="2026-11-10", tenant_id=T2)
    assert isinstance(otro_tenant, CobroPendiente)
    assert otro_tenant.id != pendiente.id
    assert otro_tenant.tenant_id == T2
    assert h.pendientes.total(T2) == 1
    assert h.pendientes.total(T1) == 1
    assert h.movimientos.total(T2) == 0


# ---------------------------------------------------------------------------
# 4.5 — el replay con otro medio es 409 y no duplica
# ---------------------------------------------------------------------------


def test_replay_con_otro_medio_409() -> None:
    h = HarnessCaja()
    original = h.imputar_tramo(monto=60000, medio="EFECTIVO", fecha="2026-11-10")
    assert isinstance(original, Movimiento)

    with pytest.raises(ConflictoCaja) as excinfo:
        h.imputar_tramo(monto=60000, medio="TRANSFERENCIA", fecha="2026-11-10")

    assert excinfo.value.codigo == 409
    assert excinfo.value.codigo_dominio == "IMPUTACION_DUPLICADA"
    # El medio no integra la clave: sigue existiendo un solo movimiento.
    assert h.movimientos.total(T1) == 1
    assert _movimientos(h, FECHA) == [original]
    intacto = h.movimientos.obtener(tenant_id=T1, movimiento_id=original.id)
    assert intacto == original
    assert intacto is not None
    assert intacto.medio == "EFECTIVO"
    assert intacto.monto == 60000
    assert h.movimientos.totales_por_medio(tenant_id=T1, fecha=FECHA) == {
        "EFECTIVO": 60000,
        "TRANSFERENCIA": 0,
        "MP": 0,
        "OS": 0,
    }


# ---------------------------------------------------------------------------
# 4.6 — cobro con la fecha del pendiente cerrada: ajuste y cierre intacto (H4)
# ---------------------------------------------------------------------------


def test_cobro_con_fecha_cerrada_asienta_ajuste_201() -> None:
    h = HarnessCaja()
    pendiente = _pendiente(h)
    # El día del pendiente ya tiene un ingreso y su cierre.
    ingreso = h.registrar(monto=150000, medio="EFECTIVO", fecha="2026-11-10")
    cierre = h.cerrar(fecha="2026-11-10", efectivo_contado=150000)
    assert cierre.total_efectivo == 150000
    h.cierres.llamadas_cerrar = 0
    h.ahora = d3("2026-11-11", 9)

    resultado = h.cobrar(pendiente.id, medio="TRANSFERENCIA")

    # THEN el movimiento se fecha el día del registro, nunca el día cerrado.
    movimiento = resultado.movimiento
    assert movimiento.fecha == SIGUIENTE
    assert movimiento.tipo == "INGRESO"
    assert movimiento.monto == 60000
    assert movimiento.medio == "TRANSFERENCIA"
    assert movimiento.tramo == "PACIENTE"
    assert movimiento.linea_id == LINEA1
    assert resultado.pendiente.resuelto_en == d3("2026-11-11", 9)
    assert resultado.pendiente.movimiento_id == movimiento.id
    # El ajuste `COBRO_PENDIENTE` apunta al cierre del día del pendiente.
    assert resultado.ajuste is not None
    ajustes = h.ajustes.listar_por_cierre(tenant_id=T1, cierre_id=cierre.id)
    assert ajustes == [resultado.ajuste]
    ajuste = resultado.ajuste
    assert ajuste.tipo == "COBRO_PENDIENTE"
    assert ajuste.cierre_id == cierre.id
    assert ajuste.cobro_pendiente_id == pendiente.id
    assert ajuste.movimiento_original_id is None
    assert ajuste.monto == 60000
    assert ajuste.medio == "TRANSFERENCIA"
    assert ajuste.motivo is None
    assert ajuste.actor_id == U1
    assert ajuste.compensatorio_id == movimiento.id
    # D14: lock del día del pendiente y del día del registro.
    assert h.uow.bloqueos_dia == [(T1, FECHA), (T1, SIGUIENTE)]
    # El cierre no se recalcula ni se edita y el día cerrado no recibe movimientos.
    assert h.cierres.obtener(tenant_id=T1, fecha=FECHA) == cierre
    assert h.cierres.llamadas_cerrar == 0
    assert cierre.total_efectivo == 150000
    assert cierre.total_transferencia == 0
    assert cierre.efectivo_contado == 150000
    assert cierre.diferencia == 0
    assert cierre.cerrado_at == d3("2026-11-10", 10)
    assert _movimientos(h, FECHA) == [ingreso]
    assert [m.id for m in _movimientos(h, SIGUIENTE)] == [movimiento.id]
    assert h.movimientos.totales_por_medio(tenant_id=T1, fecha=SIGUIENTE)[
        "TRANSFERENCIA"
    ] == 60000
    # El ajuste no suma en los totales de ningún día.
    assert h.movimientos.totales_por_medio(tenant_id=T1, fecha=FECHA)[
        "TRANSFERENCIA"
    ] == 0
    assert "AJUSTE_POST_CIERRE_REGISTRADO" in _acciones(h)
    assert "COBRO_PENDIENTE_RESUELTO" in _acciones(h)


# ---------------------------------------------------------------------------
# 4.7 — imputación sin medio en un día cerrado: 409 sin escribir nada
# ---------------------------------------------------------------------------


def test_imputacion_sin_medio_en_dia_cerrado_409() -> None:
    h = HarnessCaja()
    cierre = h.cerrar(fecha="2026-11-10", efectivo_contado=0)
    h.cierres.llamadas_cerrar = 0

    with pytest.raises(ConflictoCaja) as excinfo:
        h.imputar_tramo(monto=60000, medio=None, fecha="2026-11-10")

    assert excinfo.value.codigo == 409
    assert excinfo.value.codigo_dominio == "CIERRE_CERRADO"
    assert h.pendientes.total(T1) == 0
    assert h.movimientos.total(T1) == 0
    assert h.cierres.obtener(tenant_id=T1, fecha=FECHA) == cierre
    assert h.cierres.llamadas_cerrar == 0
    assert h.auditoria.entradas == []


# ---------------------------------------------------------------------------
# 4.8 — un tramo en cero no crea pendiente ni movimiento
# ---------------------------------------------------------------------------


def test_tramo_cero_no_crea_pendiente() -> None:
    h = HarnessCaja()

    resultado = h.imputar_tramo(monto=0, medio=None, fecha="2026-11-10")

    assert resultado is None
    assert h.pendientes.total(T1) == 0
    assert h.movimientos.total(T1) == 0
    assert _movimientos(h, FECHA) == []
    assert h.auditoria.entradas == []
    # Sin hecho de caja no se abre unidad de trabajo ni se toma el lock.
    assert h.uow.bloqueos_dia == []
