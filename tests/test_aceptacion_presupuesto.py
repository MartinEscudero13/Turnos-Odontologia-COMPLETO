"""Tasks 5.1–5.11 y 5.13–5.16 — aceptación parcial e imputación.

Dominio puro con adaptadores en memoria, salvo 5.11 (`test_imputar_agenda_no_crea_turno`),
que es integración con PostgreSQL y se salta sin `C02_DATABASE_URL`. La garantía
de exclusión real (5.12) vive en `test_aceptacion_concurrente_pg.py`: un
adaptador en memoria simula el lock con un método explícito y no prueba nada
sobre concurrencia (D4/B1).
"""
from __future__ import annotations

from types import TracebackType

import pytest
from _odontograma_helpers import PAC1, PREST1, actor, d3
from _presupuesto_helpers import (
    OS1,
    HarnessPresupuesto,
    presupuesto_vigente,
    registrar_aceptacion,
)
from _presupuesto_pg import CONSULTA_TURNOS, limpiar, motor, requiere_pg, sembrar_base
from conftest import T1

from app.presupuesto.puertos import (
    Aceptacion,
    AceptacionMemoria,
    ImputacionMemoria,
    Linea,
    LlamadaAgenda,
    LlamadaCaja,
    UnidadDeTrabajoMemoria,
)
from app.presupuesto.servicio import Conflicto, ServicioNoDisponible
from app.turnos.servicio import Invalido


def _caja_de(h: HarnessPresupuesto, linea_id: str) -> list[LlamadaCaja]:
    return [llamada for llamada in h.imputacion.llamadas_caja if llamada.linea_id == linea_id]


def _agenda_de(h: HarnessPresupuesto, linea_id: str) -> list[LlamadaAgenda]:
    return [llamada for llamada in h.imputacion.llamadas_agenda if llamada.linea_id == linea_id]


# ---------------------------------------------------------------------------
# 5.1 → 5.5 — estados de la aceptación
# ---------------------------------------------------------------------------


def test_aceptacion_parcial_imputa_solo_la_aceptada():
    h = HarnessPresupuesto()
    presupuesto_id, lineas = presupuesto_vigente(h, cantidad_lineas=2)
    resultado = registrar_aceptacion(h, presupuesto_id, lineas[0])
    assert resultado.presupuesto.estado == "PARCIAL"
    assert resultado.aceptacion.acepta is True
    assert len(_caja_de(h, lineas[0])) == 1
    assert len(_agenda_de(h, lineas[0])) == 1
    assert _caja_de(h, lineas[1]) == []
    assert _agenda_de(h, lineas[1]) == []


def test_aceptacion_total_pasa_a_aceptado():
    h = HarnessPresupuesto()
    presupuesto_id, lineas = presupuesto_vigente(h, cantidad_lineas=2)
    parcial = registrar_aceptacion(h, presupuesto_id, lineas[0])
    assert parcial.presupuesto.estado == "PARCIAL"
    total = registrar_aceptacion(h, presupuesto_id, lineas[1])
    assert total.presupuesto.estado == "ACEPTADO"
    assert len(_caja_de(h, lineas[0])) == 1
    assert len(_caja_de(h, lineas[1])) == 1
    assert len(h.imputacion.llamadas_caja) == 2
    # Cada línea se imputa exactamente una vez (D4).
    assert sorted(llamada.linea_id for llamada in h.imputacion.llamadas_caja) == sorted(lineas)


def test_rechazo_no_imputa():
    h = HarnessPresupuesto()
    presupuesto_id, lineas = presupuesto_vigente(h, cantidad_lineas=2)
    resultado = registrar_aceptacion(h, presupuesto_id, lineas[1], acepta=False)
    assert resultado.aceptacion.acepta is False
    assert resultado.presupuesto.estado == "VIGENTE"
    assert h.imputacion.llamadas_caja == []
    assert h.imputacion.llamadas_agenda == []
    assert _caja_de(h, lineas[1]) == []


def test_aceptadas_y_rechazadas_quedan_parcial():
    h = HarnessPresupuesto()
    presupuesto_id, lineas = presupuesto_vigente(h, cantidad_lineas=2)
    registrar_aceptacion(h, presupuesto_id, lineas[0])
    resultado = registrar_aceptacion(h, presupuesto_id, lineas[1], acepta=False)
    assert resultado.presupuesto.estado == "PARCIAL"
    assert resultado.presupuesto.estado != "ACEPTADO"
    assert len(_caja_de(h, lineas[0])) == 1
    assert _caja_de(h, lineas[1]) == []
    assert _agenda_de(h, lineas[1]) == []


def test_todas_rechazadas_conserva_estado_anterior():
    h = HarnessPresupuesto()
    presupuesto_id, lineas = presupuesto_vigente(h)
    resultado = registrar_aceptacion(h, presupuesto_id, lineas[0], acepta=False)
    assert resultado.presupuesto.estado == "VIGENTE"
    assert resultado.presupuesto.estado != "ACEPTADO"
    assert len(h.aceptaciones.listar_por_linea(tenant_id=T1, linea_id=lineas[0])) == 1
    assert h.imputacion.llamadas_caja == []
    assert h.imputacion.llamadas_agenda == []


# ---------------------------------------------------------------------------
# 5.6 → 5.9 — decisiones ya tomadas y fallo de imputación
# ---------------------------------------------------------------------------


def test_aceptar_linea_ya_aceptada_409_sin_duplicar():
    h = HarnessPresupuesto()
    presupuesto_id, lineas = presupuesto_vigente(h)
    registrar_aceptacion(h, presupuesto_id, lineas[0], ahora=d3("2026-11-10", hora=10))
    with pytest.raises(Conflicto) as exc:
        registrar_aceptacion(h, presupuesto_id, lineas[0], ahora=d3("2026-11-10", hora=11))
    assert exc.value.codigo == 409
    aceptaciones = h.aceptaciones.listar_por_linea(tenant_id=T1, linea_id=lineas[0])
    assert len(aceptaciones) == 1
    assert len(h.imputacion.llamadas_caja) == 1
    assert len(h.imputacion.llamadas_agenda) == 1


def test_aceptar_linea_ya_rechazada_409():
    h = HarnessPresupuesto()
    presupuesto_id, lineas = presupuesto_vigente(h)
    registrar_aceptacion(h, presupuesto_id, lineas[0], acepta=False)
    with pytest.raises(Conflicto) as exc:
        registrar_aceptacion(h, presupuesto_id, lineas[0])
    assert exc.value.codigo == 409
    [aceptacion] = h.aceptaciones.listar_por_linea(tenant_id=T1, linea_id=lineas[0])
    assert aceptacion.acepta is False
    assert h.imputacion.llamadas_caja == []


def test_rechazar_linea_ya_aceptada_409():
    h = HarnessPresupuesto()
    presupuesto_id, lineas = presupuesto_vigente(h)
    aceptada = registrar_aceptacion(h, presupuesto_id, lineas[0])
    with pytest.raises(Conflicto) as exc:
        registrar_aceptacion(h, presupuesto_id, lineas[0], acepta=False)
    assert exc.value.codigo == 409
    aceptaciones = h.aceptaciones.listar_por_linea(tenant_id=T1, linea_id=lineas[0])
    assert len(aceptaciones) == 1
    assert aceptaciones[0] == aceptada.aceptacion
    assert aceptaciones[0].acepta is True
    # La imputación ya registrada no se revierte (v1 no revierte decisiones).
    assert len(h.imputacion.llamadas_caja) == 1


def test_imputacion_fallida_no_deja_aceptacion():
    h = HarnessPresupuesto(imputacion=ImputacionMemoria(fallar_caja=True))
    presupuesto_id, lineas = presupuesto_vigente(h)
    with pytest.raises(ServicioNoDisponible) as exc:
        registrar_aceptacion(h, presupuesto_id, lineas[0])
    assert exc.value.codigo == 503
    assert h.aceptaciones.total(T1) == 0
    assert h.presupuestos.obtener(tenant_id=T1, presupuesto_id=presupuesto_id).estado == "VIGENTE"
    assert h.imputacion.llamadas_agenda == []
    assert h.imputacion.llamadas_caja == []
    assert h.auditoria.de_accion("ACEPTACION_REGISTRADA") == []


# ---------------------------------------------------------------------------
# 5.10 — contrato de caja (D6/B3)
# ---------------------------------------------------------------------------


def test_imputacion_caja_recibe_tramos_actor_y_medio():
    h = HarnessPresupuesto()
    h.seed_cobertura(modo="MONTO", valor=40000, obra_social_id=OS1)
    presupuesto_id, lineas = presupuesto_vigente(h, monto=100000)
    resultado = registrar_aceptacion(
        h,
        presupuesto_id,
        lineas[0],
        medio="EFECTIVO",
        actor_=actor("RECEPCION", user_id="U1"),
    )
    linea = resultado.aceptacion
    assert linea.medio == "EFECTIVO"
    [caja] = h.imputacion.llamadas_caja
    assert caja.tenant_id == T1
    assert caja.presupuesto_id == presupuesto_id
    assert caja.linea_id == lineas[0]
    assert caja.paciente_id == PAC1
    assert caja.prestacion_id == PREST1
    assert caja.monto_paciente_centavos == 60000
    assert caja.monto_os_centavos == 40000
    assert caja.actor_id == "U1"
    assert caja.turno_id is None
    assert caja.medio == "EFECTIVO"


# ---------------------------------------------------------------------------
# 5.12 → 5.16 — recupero, fecha del servidor y validaciones del payload
# ---------------------------------------------------------------------------


def test_lineas_no_aceptadas_consultables_para_recupero():
    h = HarnessPresupuesto()
    presupuesto_id, lineas = presupuesto_vigente(h, cantidad_lineas=3)
    registrar_aceptacion(h, presupuesto_id, lineas[0])
    registrar_aceptacion(h, presupuesto_id, lineas[1], acepta=False)
    leido = h.svc.obtener(
        actor("RECEPCION"), presupuesto_id=presupuesto_id, ahora=d3()
    )
    decisiones = {item.linea.id: item.aceptacion for item in leido.lineas}
    assert decisiones[lineas[0]] is not None and decisiones[lineas[0]].acepta is True
    assert decisiones[lineas[1]] is not None and decisiones[lineas[1]].acepta is False
    assert decisiones[lineas[2]] is None
    # Ninguna de las no aceptadas se imputó.
    assert _caja_de(h, lineas[1]) == [] and _agenda_de(h, lineas[1]) == []
    assert _caja_de(h, lineas[2]) == [] and _agenda_de(h, lineas[2]) == []
    assert len(h.imputacion.llamadas_caja) == 1


def test_fecha_aceptacion_la_fija_el_servidor():
    h = HarnessPresupuesto()
    presupuesto_id, lineas = presupuesto_vigente(h)
    momento = d3("2026-11-10", hora=10)
    resultado = registrar_aceptacion(h, presupuesto_id, lineas[0], ahora=momento)
    assert resultado.aceptacion.fecha == momento
    persistida = h.aceptaciones.ultima_por_linea(tenant_id=T1, linea_id=lineas[0])
    assert persistida is not None and persistida.fecha == momento


def test_canal_vacio_o_body_vacio_422():
    h = HarnessPresupuesto()
    presupuesto_id, lineas = presupuesto_vigente(h)
    for canal in ("", "   ", None):
        with pytest.raises(Invalido) as exc:
            registrar_aceptacion(h, presupuesto_id, lineas[0], canal=canal)
        assert exc.value.codigo == 422
        assert exc.value.codigo != 500
    assert h.aceptaciones.total(T1) == 0
    assert h.imputacion.llamadas_caja == []
    assert h.imputacion.llamadas_agenda == []


def test_medio_opcional_en_aceptacion_null_por_defecto():
    h = HarnessPresupuesto()
    presupuesto_id, lineas = presupuesto_vigente(h)
    resultado = registrar_aceptacion(h, presupuesto_id, lineas[0])
    assert resultado.aceptacion.medio is None
    [caja] = h.imputacion.llamadas_caja
    assert caja.medio is None
    # C-10 completa el medio al cobrar; la aceptación ya quedó registrada.
    [aceptacion] = h.aceptaciones.listar_por_linea(tenant_id=T1, linea_id=lineas[0])
    assert aceptacion.medio is None


def test_rechazar_no_exige_medio_y_no_imputa():
    h = HarnessPresupuesto()
    presupuesto_id, lineas = presupuesto_vigente(h)
    resultado = registrar_aceptacion(
        h, presupuesto_id, lineas[0], acepta=False, medio=None
    )
    assert resultado.aceptacion.medio is None
    assert h.imputacion.llamadas_caja == []


@requiere_pg
def test_imputar_agenda_no_crea_turno():
    """Aceptar una línea no cambia `turnos`: la agenda sólo registra la intención.

    Integración con PostgreSQL real (se salta sin `C02_DATABASE_URL`). Alcance
    honesto: el wiring SQLAlchemy es un follow-up declarado; esta prueba fija
    que la tabla `turnos` queda idéntica y que el contrato de agenda no recibe
    datos con los que pudiera crear un turno (M10).
    """
    engine = motor()
    ids: dict[str, str] = {}
    try:
        with engine.connect() as owner:
            tx = owner.begin()
            ids = sembrar_base(owner)
            tx.commit()

        with engine.connect() as owner:
            antes = [
                tuple(fila) for fila in owner.execute(CONSULTA_TURNOS, {"t": ids["tenant"]})
            ]

        h = HarnessPresupuesto()
        presupuesto_id, lineas = presupuesto_vigente(h)
        registrar_aceptacion(h, presupuesto_id, lineas[0])
        [intencion] = h.imputacion.llamadas_agenda
        assert intencion.monto_centavos > 0
        for campo in ("profesional_id", "sillon_id", "inicio", "fin"):
            assert not hasattr(intencion, campo)
        assert h.imputacion.llamadas_caja[0].turno_id is None
        assert h.imputacion.llamadas_caja[0].tenant_id == T1

        with engine.connect() as owner:
            despues = [
                tuple(fila) for fila in owner.execute(CONSULTA_TURNOS, {"t": ids["tenant"]})
            ]
        assert despues == antes
        assert len(despues) == 1
    finally:
        limpiar(engine, ids)


class _UowConDecisionDeOtraTransaccion:
    """Simula la transacción que gana el lock antes que la nuestra.

    El lock en memoria es **explícito, no real** (D4/B1): al tomarlo, la "otra"
    transacción ya registró y confirmó su decisión, exactamente lo que ve la
    segunda transacción en PostgreSQL después de esperar el `SELECT ... FOR
    UPDATE`. Su commit es durable: si nuestra unidad de trabajo revierte, la
    decisión de la otra transacción se repone y no desaparece.
    """

    def __init__(
        self,
        base: UnidadDeTrabajoMemoria,
        aceptaciones: AceptacionMemoria,
        *,
        tenant_id: str,
        linea_id: str,
    ) -> None:
        self._base = base
        self._aceptaciones = aceptaciones
        self._tenant_id = tenant_id
        self._linea_id = linea_id
        self._otra: Aceptacion | None = None

    def __enter__(self) -> _UowConDecisionDeOtraTransaccion:
        self._base.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._base.__exit__(exc_type, exc, tb)
        if self._otra is not None and (
            self._aceptaciones.ultima_por_linea(
                tenant_id=self._tenant_id, linea_id=self._linea_id
            )
            is None
        ):
            self._aceptaciones.registrar(
                tenant_id=self._otra.tenant_id,
                linea_id=self._otra.linea_id,
                acepta=self._otra.acepta,
                fecha=self._otra.fecha,
                canal=self._otra.canal,
                medio=self._otra.medio,
                ahora=self._otra.creado_en,
            )

    def bloquear_linea(self, *, tenant_id: str, linea_id: str) -> Linea:
        if self._otra is None:
            self._otra = self._aceptaciones.registrar(
                tenant_id=tenant_id,
                linea_id=linea_id,
                acepta=True,
                fecha=d3("2026-11-10", hora=9),
                canal="CONSULTORIO",
                ahora=d3("2026-11-10", hora=9),
            )
        return self._base.bloquear_linea(tenant_id=tenant_id, linea_id=linea_id)


def test_decision_de_otra_transaccion_se_ve_despues_del_lock():
    h = HarnessPresupuesto()
    presupuesto_id, lineas = presupuesto_vigente(h)

    def factory() -> _UowConDecisionDeOtraTransaccion:
        return _UowConDecisionDeOtraTransaccion(
            h.nueva_uow(), h.aceptaciones, tenant_id=T1, linea_id=lineas[0]
        )

    h.cablear_uow(factory)  # type: ignore[arg-type]  # protocolo estructural
    with pytest.raises(Conflicto) as exc:
        registrar_aceptacion(h, presupuesto_id, lineas[0])
    assert exc.value.codigo == 409
    # Sólo la aceptación de la otra transacción: no hay una segunda decisión
    # ni una segunda imputación (exclusión real, no TOCTOU).
    assert len(h.aceptaciones.listar_por_linea(tenant_id=T1, linea_id=lineas[0])) == 1
    assert h.imputacion.llamadas_caja == []
    assert h.imputacion.llamadas_agenda == []

