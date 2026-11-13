"""Task 4.1 — puertos y adaptadores en memoria del presupuesto (tenant-scoped).

El adaptador en memoria reproduce el contrato de la migración 007: toda lectura y
escritura filtra por `tenant_id`, el lock de línea es explícito (no es una
garantía real de exclusión, ver D4/B1) y la imputación sólo registra la
intención de agenda/caja (M10: no transporta datos de turno).
"""
from __future__ import annotations

import pytest
from _odontograma_helpers import PAC1, PAC9, PREST1, d3
from conftest import T1, T2

from app.presupuesto.puertos import (
    AceptacionMemoria,
    CoberturaConfigurada,
    CoberturaMemoria,
    CoberturaSinDatos,
    ImputacionMemoria,
    LineaMemoria,
    PresupuestoMemoria,
)
from app.turnos.servicio import NoEncontrado


def _linea(repo: LineaMemoria, *, tenant_id: str, presupuesto_id: str, monto: int = 100000):
    return repo.agregar(
        tenant_id=tenant_id,
        presupuesto_id=presupuesto_id,
        prestacion_id=PREST1,
        monto=monto,
        cobertura_os=0,
        a_cargo_paciente=monto,
        origen_cobertura="SIN_COBERTURA",
        validada_en_vivo=False,
        ahora=d3(),
    )


def test_repositorios_y_puertos_scoped_por_tenant():
    presupuestos = PresupuestoMemoria()
    lineas = LineaMemoria()
    aceptaciones = AceptacionMemoria()

    de_t1 = presupuestos.crear(tenant_id=T1, paciente_id=PAC1, ahora=d3())
    de_t2 = presupuestos.crear(tenant_id=T2, paciente_id=PAC9, ahora=d3())
    assert presupuestos.obtener(tenant_id=T1, presupuesto_id=de_t1.id) == de_t1
    assert presupuestos.obtener(tenant_id=T2, presupuesto_id=de_t1.id) is None
    assert presupuestos.obtener(tenant_id=T2, presupuesto_id=de_t2.id) == de_t2

    linea_t1 = _linea(lineas, tenant_id=T1, presupuesto_id=de_t1.id)
    linea_t2 = _linea(lineas, tenant_id=T2, presupuesto_id=de_t2.id)
    assert lineas.listar(tenant_id=T1, presupuesto_id=de_t1.id) == [linea_t1]
    # Un presupuesto de T2 no expone líneas de T1 aunque se pase su id.
    assert lineas.listar(tenant_id=T2, presupuesto_id=de_t1.id) == []
    assert lineas.listar(tenant_id=T2, presupuesto_id=de_t2.id) == [linea_t2]

    # El lock de fila también está scoped: T2 no puede bloquear una línea de T1.
    assert lineas.bloquear(tenant_id=T1, linea_id=linea_t1.id) == linea_t1
    with pytest.raises(NoEncontrado):
        lineas.bloquear(tenant_id=T2, linea_id=linea_t1.id)

    # Aceptaciones: ledger append-only y última decisión por línea.
    primera = aceptaciones.registrar(
        tenant_id=T1,
        linea_id=linea_t1.id,
        acepta=True,
        fecha=d3(),
        canal="CONSULTORIO",
        ahora=d3(),
    )
    assert primera.medio is None
    assert aceptaciones.ultima_por_linea(tenant_id=T2, linea_id=linea_t1.id) is None
    assert aceptaciones.ultima_por_linea(tenant_id=T1, linea_id=linea_t1.id) == primera
    segunda = aceptaciones.registrar(
        tenant_id=T1,
        linea_id=linea_t1.id,
        acepta=False,
        fecha=d3(hora=11),
        canal="CONSULTORIO",
        ahora=d3(hora=11),
    )
    assert aceptaciones.ultima_por_linea(tenant_id=T1, linea_id=linea_t1.id) == segunda
    assert [a.acepta for a in aceptaciones.listar_por_linea(tenant_id=T1, linea_id=linea_t1.id)] == [
        True,
        False,
    ]
    assert aceptaciones.listar_por_linea(tenant_id=T2, linea_id=linea_t1.id) == []

    # Transiciones de estado scoped: T2 no puede emitir ni cambiar el estado de T1.
    with pytest.raises(NoEncontrado):
        presupuestos.actualizar_estado(tenant_id=T2, presupuesto_id=de_t1.id, estado="VIGENTE")
    with pytest.raises(NoEncontrado):
        presupuestos.emitir(
            tenant_id=T2,
            presupuesto_id=de_t1.id,
            vence_en=d3("2026-12-31", hora=23, minuto=59),
            ahora=d3(),
        )
    vigente = presupuestos.emitir(
        tenant_id=T1,
        presupuesto_id=de_t1.id,
        vence_en=d3("2026-12-31", hora=23, minuto=59),
        ahora=d3(),
    )
    assert vigente.estado == "VIGENTE"
    assert vigente.vence_en == d3("2026-12-31", hora=23, minuto=59)
    assert presupuestos.obtener(tenant_id=T1, presupuesto_id=de_t1.id) == vigente
    assert presupuestos.obtener(tenant_id=T2, presupuesto_id=de_t2.id).estado == "BORRADOR"


def test_puertos_de_cobertura_e_imputacion_no_cruzan_tenant():
    coberturas = CoberturaMemoria()
    config = CoberturaConfigurada(modo="PORCENTAJE", valor=50)
    coberturas.agregar(T1, "OS-1", PREST1, config)
    assert (
        coberturas.cobertura(tenant_id=T1, obra_social_id="OS-1", prestacion_id=PREST1) == config
    )
    assert coberturas.cobertura(tenant_id=T2, obra_social_id="OS-1", prestacion_id=PREST1) is None
    assert coberturas.cobertura(tenant_id=T1, obra_social_id="OS-2", prestacion_id=PREST1) is None
    # El adaptador deja rastro de lo consultado: sirve para probar que el
    # servicio no consulta una cobertura que no corresponde (M1).
    assert coberturas.consultas == [
        (T1, "OS-1", PREST1),
        (T2, "OS-1", PREST1),
        (T1, "OS-2", PREST1),
    ]

    sin_datos = CoberturaSinDatos()
    assert sin_datos.cobertura(tenant_id=T1, obra_social_id="OS-1", prestacion_id=PREST1) is None
    assert sin_datos.consultas == [(T1, "OS-1", PREST1)]

    imputacion = ImputacionMemoria()
    imputacion.imputar_agenda(
        tenant_id=T1,
        presupuesto_id="presupuesto-1",
        linea_id="linea-1",
        paciente_id=PAC1,
        prestacion_id=PREST1,
        monto_centavos=100000,
    )
    imputacion.imputar_caja(
        tenant_id=T1,
        presupuesto_id="presupuesto-1",
        linea_id="linea-1",
        paciente_id=PAC1,
        prestacion_id=PREST1,
        monto_paciente_centavos=60000,
        monto_os_centavos=40000,
        actor_id="usuario-1",
        turno_id=None,
        medio="EFECTIVO",
    )
    assert len(imputacion.llamadas_agenda) == 1
    assert len(imputacion.llamadas_caja) == 1
    agenda = imputacion.llamadas_agenda[0]
    caja = imputacion.llamadas_caja[0]
    assert agenda.tenant_id == T1 and agenda.monto_centavos == 100000
    assert caja.monto_paciente_centavos == 60000
    assert caja.monto_os_centavos == 40000
    assert caja.medio == "EFECTIVO" and caja.turno_id is None
    # M10: el puerto de agenda registra la intención y no recibe datos con los
    # que pudiera crear un turno (profesional/sillón/inicio/duración).
    for campo in ("profesional_id", "sillon_id", "inicio", "fin", "duracion_min"):
        assert not hasattr(agenda, campo)
