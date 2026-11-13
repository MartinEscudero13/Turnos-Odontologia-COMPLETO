"""Task 2.1 — puertos y adaptadores en memoria del odontograma (RLS lógico)."""
from __future__ import annotations

import pytest
from _odontograma_helpers import KEY, PAC1, PAC9, d3
from conftest import P1, T1, T2

from app.odontograma.puertos import HallazgoMemoria, UnidadDeTrabajoMemoria
from app.presupuesto.puertos import LineaMemoria, PresupuestoMemoria
from app.turnos.servicio import NoEncontrado


def test_repositorio_scoped_por_tenant():
    repo = HallazgoMemoria()
    h1 = repo.registrar(
        tenant_id=T1,
        paciente_id=PAC1,
        pieza_fdi=36,
        superficie="O",
        hallazgo="caries oclusal",
        fecha=d3(),
        profesional_id=P1,
    )
    h2 = repo.registrar(
        tenant_id=T2,
        paciente_id=PAC9,
        pieza_fdi=36,
        superficie=None,
        hallazgo="hallazgo de otro tenant",
        fecha=d3(),
        profesional_id=P1,
    )
    # Cada tenant sólo ve lo suyo.
    assert repo.listar_por_paciente(tenant_id=T1, paciente_id=PAC1) == [h1]
    assert repo.listar_por_paciente(tenant_id=T2, paciente_id=PAC9) == [h2]
    assert repo.listar_por_pieza(tenant_id=T1, paciente_id=PAC1, pieza_fdi=36) == [h1]
    assert repo.listar_por_pieza(tenant_id=T2, paciente_id=PAC1, pieza_fdi=36) == []
    assert repo.obtener(tenant_id=T2, hallazgo_id=h1.id) is None
    assert repo.obtener(tenant_id=T1, hallazgo_id=h1.id) == h1
    # Resolver desde el tenant equivocado no toca la fila.
    with pytest.raises(NoEncontrado):
        repo.marcar_resuelto(tenant_id=T2, hallazgo_id=h1.id)
    assert repo.obtener(tenant_id=T1, hallazgo_id=h1.id).resuelto is False
    assert repo.marcar_resuelto(tenant_id=T1, hallazgo_id=h1.id).resuelto is True
    assert repo.total(T1) == 1 and repo.total(T2) == 1


def test_historial_del_repositorio_ordena_por_fecha_y_no_mezcla_piezas():
    repo = HallazgoMemoria()
    tarde = repo.registrar(
        tenant_id=T1,
        paciente_id=PAC1,
        pieza_fdi=36,
        superficie=None,
        hallazgo="tarde",
        fecha=d3("2026-11-10"),
        profesional_id=P1,
    )
    temprano = repo.registrar(
        tenant_id=T1,
        paciente_id=PAC1,
        pieza_fdi=36,
        superficie=None,
        hallazgo="temprano",
        fecha=d3("2026-11-01"),
        profesional_id=P1,
    )
    otra = repo.registrar(
        tenant_id=T1,
        paciente_id=PAC1,
        pieza_fdi=37,
        superficie=None,
        hallazgo="otra pieza",
        fecha=d3("2026-11-05"),
        profesional_id=P1,
    )
    assert [h.id for h in repo.listar_por_pieza(
        tenant_id=T1, paciente_id=PAC1, pieza_fdi=36
    )] == [temprano.id, tarde.id]
    assert repo.listar_por_pieza(tenant_id=T1, paciente_id=PAC1, pieza_fdi=37) == [otra]


def test_unidad_de_trabajo_revierte_hallazgo_y_linea_ante_excepcion():
    hallazgos = HallazgoMemoria()
    presupuestos = PresupuestoMemoria()
    lineas = LineaMemoria()
    uow = UnidadDeTrabajoMemoria([hallazgos, presupuestos, lineas])
    with pytest.raises(RuntimeError):  # noqa: SIM117 - la excepción debe verla el uow
        with uow:
            hallazgo = hallazgos.registrar(
                tenant_id=T1,
                paciente_id=PAC1,
                pieza_fdi=36,
                superficie=None,
                hallazgo="caries oclusal",
                fecha=d3(),
                profesional_id=P1,
            )
            presupuesto = presupuestos.crear(tenant_id=T1, paciente_id=PAC1, ahora=d3())
            lineas.agregar(
                tenant_id=T1,
                presupuesto_id=presupuesto.id,
                prestacion_id="prestacion-1",
                monto=150000,
                cobertura_os=0,
                a_cargo_paciente=150000,
                origen_cobertura="SIN_COBERTURA",
                validada_en_vivo=False,
                pieza_fdi=36,
                hallazgo_id=hallazgo.id,
                idempotency_key=KEY,
                ahora=d3(),
            )
            raise RuntimeError("falla la unidad de trabajo")
    assert hallazgos.total(T1) == 0
    assert presupuestos.total(T1) == 0
    assert lineas.total(T1) == 0
    # Éxito: la unidad de trabajo confirma lo escrito.
    with uow:
        hallazgos.registrar(
            tenant_id=T1,
            paciente_id=PAC1,
            pieza_fdi=11,
            superficie=None,
            hallazgo="caries oclusal",
            fecha=d3(),
            profesional_id=P1,
        )
    assert hallazgos.total(T1) == 1
