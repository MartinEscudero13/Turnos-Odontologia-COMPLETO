"""Tasks 2.1–2.11 — dominio del odontograma (hallazgos, historial e inmutabilidad).

Datos ficticios ("Paciente Demo"/"Otro Paciente Demo", P1/P2, "Conducto Demo") y
reloj inyectado en `-03:00`. Los escenarios de la spec son estos tests.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from _odontograma_helpers import (
    PAC1,
    PAC9,
    HarnessOdontograma,
    actor,
    d3,
)
from conftest import P1, T1, T2

from app.ficha_clinica.servicio import Conflicto, ConsentimientoRequerido
from app.turnos.servicio import Invalido, NoEncontrado

FDI_GRID = [
    *range(11, 19),
    *range(21, 29),
    *range(31, 39),
    *range(41, 49),
]


# ---------------------------------------------------------------------------
# 2.2 — hallazgo válido
# ---------------------------------------------------------------------------


def test_registrar_hallazgo_valido_fdi():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    hallazgo = h.svc.registrar_hallazgo(
        actor("ODONTOLOGO", profesional_id=P1),
        paciente_id=PAC1,
        pieza_fdi=36,
        superficie="O",
        hallazgo="caries oclusal",
        fecha=d3(),
        profesional_id=P1,
    )
    assert hallazgo.tenant_id == T1
    assert hallazgo.paciente_id == PAC1
    assert hallazgo.pieza_fdi == 36
    assert hallazgo.superficie == "O"
    assert hallazgo.profesional_id == P1
    assert hallazgo.resuelto is False
    assert h.hallazgos.listar_por_pieza(
        tenant_id=T1, paciente_id=PAC1, pieza_fdi=36
    ) == [hallazgo]


# ---------------------------------------------------------------------------
# 2.3 — grilla FDI
# ---------------------------------------------------------------------------


def test_fdi_grilla_valida_32_posiciones():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    registrados = [
        h.svc.registrar_hallazgo(
            actor("ADMIN"),
            paciente_id=PAC1,
            pieza_fdi=pieza,
            hallazgo="hallazgo demo",
            fecha=d3(),
            profesional_id=P1,
        )
        for pieza in FDI_GRID
    ]
    assert len(registrados) == 32
    assert {r.pieza_fdi for r in registrados} == set(FDI_GRID)
    assert h.hallazgos.total(T1) == 32


def test_fdi_diente_inexistente_x9_422():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    for pieza in (19, 29, 39):
        with pytest.raises(Invalido) as exc:
            h.svc.registrar_hallazgo(
                actor("ADMIN"),
                paciente_id=PAC1,
                pieza_fdi=pieza,
                hallazgo="hallazgo demo",
                fecha=d3(),
                profesional_id=P1,
            )
        assert exc.value.codigo == 422
        assert "cuadrante 1–4 y diente 1–8" in exc.value.mensaje
    assert h.hallazgos.total(T1) == 0


def test_fdi_fuera_de_grilla_422():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    for pieza in (10, 20, 30, 40, 49, 0, 99):
        with pytest.raises(Invalido) as exc:
            h.svc.registrar_hallazgo(
                actor("ADMIN"),
                paciente_id=PAC1,
                pieza_fdi=pieza,
                hallazgo="hallazgo demo",
                fecha=d3(),
                profesional_id=P1,
            )
        assert exc.value.codigo == 422
        assert "cuadrante 1–4 y diente 1–8" in exc.value.mensaje
    assert h.hallazgos.total(T1) == 0


def test_fdi_no_numerica_422():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    for pieza in ("36a", 36.5, None, True):
        with pytest.raises(Invalido) as exc:
            h.svc.registrar_hallazgo(
                actor("ADMIN"),
                paciente_id=PAC1,
                pieza_fdi=pieza,
                hallazgo="hallazgo demo",
                fecha=d3(),
                profesional_id=P1,
            )
        assert exc.value.codigo == 422
    assert h.hallazgos.total(T1) == 0


# ---------------------------------------------------------------------------
# 2.4 / 2.5 — texto y superficie
# ---------------------------------------------------------------------------


def test_payload_vacio_o_hallazgo_vacio_422():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    for texto in ("", "   "):
        with pytest.raises(Invalido) as exc:
            h.svc.registrar_hallazgo(
                actor("ADMIN"),
                paciente_id=PAC1,
                pieza_fdi=36,
                hallazgo=texto,
                fecha=d3(),
                profesional_id=P1,
            )
        assert exc.value.codigo == 422
    assert h.hallazgos.total(T1) == 0


def test_superficie_vacia_422_y_ausente_null():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    sin_superficie = h.svc.registrar_hallazgo(
        actor("ADMIN"),
        paciente_id=PAC1,
        pieza_fdi=11,
        hallazgo="hallazgo demo",
        fecha=d3(),
        profesional_id=P1,
    )
    assert sin_superficie.superficie is None
    with pytest.raises(Invalido) as exc:
        h.svc.registrar_hallazgo(
            actor("ADMIN"),
            paciente_id=PAC1,
            pieza_fdi=12,
            superficie="",
            hallazgo="hallazgo demo",
            fecha=d3(),
            profesional_id=P1,
        )
    assert exc.value.codigo == 422
    assert h.hallazgos.total(T1) == 1


# ---------------------------------------------------------------------------
# 2.6 — historial por pieza
# ---------------------------------------------------------------------------


def test_historial_por_pieza_ordenado():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    primero = h.svc.registrar_hallazgo(
        actor("ADMIN"),
        paciente_id=PAC1,
        pieza_fdi=36,
        hallazgo="caries oclusal",
        fecha=d3("2026-11-01"),
        profesional_id=P1,
    )
    segundo = h.svc.registrar_hallazgo(
        actor("ADMIN"),
        paciente_id=PAC1,
        pieza_fdi=36,
        hallazgo="caries oclusal (control)",
        fecha=d3("2026-11-10"),
        profesional_id=P1,
    )
    otra_pieza = h.svc.registrar_hallazgo(
        actor("ADMIN"),
        paciente_id=PAC1,
        pieza_fdi=37,
        hallazgo="hallazgo en otra pieza",
        fecha=d3("2026-11-05"),
        profesional_id=P1,
    )
    historial = h.svc.listar_historial(
        actor("RECEPCION"), paciente_id=PAC1, pieza_fdi=36
    )
    assert [x.id for x in historial] == [primero.id, segundo.id]
    assert all(x.pieza_fdi == 36 for x in historial)
    assert otra_pieza.id not in {x.id for x in historial}
    # El historial completo del paciente sí incluye las dos piezas.
    completo = h.svc.listar_historial(actor("RECEPCION"), paciente_id=PAC1)
    assert {x.pieza_fdi for x in completo} == {36, 37}
    assert len(completo) == 3


def test_pieza_sin_hallazgos_lista_vacia():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    h.svc.registrar_hallazgo(
        actor("ADMIN"),
        paciente_id=PAC1,
        pieza_fdi=36,
        hallazgo="hallazgo demo",
        fecha=d3(),
        profesional_id=P1,
    )
    assert h.svc.listar_historial(
        actor("RECEPCION"), paciente_id=PAC1, pieza_fdi=11
    ) == []


# ---------------------------------------------------------------------------
# 2.7 — inmutabilidad del contenido clínico
# ---------------------------------------------------------------------------


def test_contenido_clinico_inmutable_405_y_revoke():
    """Corrección = hallazgo nuevo; la DB sólo permite UPDATE de `resuelto`.

    La verificación HTTP de `PATCH`/`DELETE` ⇒ 405/403/404 vive en la tarea 7.2
    (borde API, fuera de esta tanda). Acá se prueba lo que el dominio y la
    migración pueden garantizar: no hay operación de edición/borrado y el
    `GRANT` de la base no permite tocar el contenido clínico.
    """
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    original = h.svc.registrar_hallazgo(
        actor("ADMIN"),
        paciente_id=PAC1,
        pieza_fdi=36,
        hallazgo="caries oclusal (texto erróneo)",
        fecha=d3(),
        profesional_id=P1,
    )
    corregido = h.svc.registrar_hallazgo(
        actor("ADMIN"),
        paciente_id=PAC1,
        pieza_fdi=36,
        hallazgo="caries oclusal",
        fecha=d3(),
        profesional_id=P1,
    )
    assert corregido.id != original.id
    assert h.hallazgos.obtener(tenant_id=T1, hallazgo_id=original.id) == original
    assert [x.id for x in h.svc.listar_historial(
        actor("RECEPCION"), paciente_id=PAC1, pieza_fdi=36
    )] == [original.id, corregido.id]
    # No existe operación de edición ni de borrado en el servicio.
    assert not hasattr(h.svc, "editar_hallazgo")
    assert not hasattr(h.svc, "eliminar_hallazgo")

    migracion = (
        __file__.rsplit("tests", 1)[0]
        + "backend/alembic/versions/007_odontograma_presupuesto.py"
    )
    with open(migracion, encoding="utf-8") as archivo:
        sql = archivo.read()
    assert "GRANT UPDATE (resuelto) ON odontograma_hallazgos TO turnos_app" in sql
    assert "REVOKE DELETE ON odontograma_hallazgos FROM turnos_app" in sql
    assert "GRANT UPDATE ON odontograma_hallazgos" not in sql


# ---------------------------------------------------------------------------
# 2.8 — resolución única
# ---------------------------------------------------------------------------


def test_resolver_una_sola_vez():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    hallazgo = h.svc.registrar_hallazgo(
        actor("ADMIN"),
        paciente_id=PAC1,
        pieza_fdi=36,
        hallazgo="caries oclusal",
        fecha=d3(),
        profesional_id=P1,
    )
    resuelto = h.svc.resolver(actor("ADMIN"), hallazgo_id=hallazgo.id)
    assert resuelto.resuelto is True
    with pytest.raises(Conflicto) as exc:
        h.svc.resolver(actor("ADMIN"), hallazgo_id=hallazgo.id)
    assert exc.value.codigo == 409
    persistido = h.hallazgos.obtener(tenant_id=T1, hallazgo_id=hallazgo.id)
    assert persistido is not None and persistido.resuelto is True
    # No existe operación que vuelva `resuelto` a false (PATCH/PUT ⇒ 405 en 7.2).
    assert not hasattr(h.svc, "desresolver")


# ---------------------------------------------------------------------------
# 2.9 — gate de consentimiento al resolver
# ---------------------------------------------------------------------------


def test_sin_consentimiento_no_resuelve_hallazgo():
    h = HarnessOdontograma()
    # El hallazgo se siembra directo en el repo: el paciente nunca dio consentimiento.
    hallazgo = h.hallazgos.registrar(
        tenant_id=T1,
        paciente_id=PAC1,
        pieza_fdi=36,
        superficie=None,
        hallazgo="caries oclusal",
        fecha=d3(),
        profesional_id=P1,
    )
    with pytest.raises(ConsentimientoRequerido) as exc:
        h.svc.resolver(actor("ADMIN"), hallazgo_id=hallazgo.id)
    assert exc.value.codigo == 409
    assert "CONSENTIMIENTO_REQUERIDO" in exc.value.mensaje
    sin_consentimiento = h.hallazgos.obtener(tenant_id=T1, hallazgo_id=hallazgo.id)
    assert sin_consentimiento is not None and sin_consentimiento.resuelto is False
    # Con consentimiento sí resuelve.
    h.dar_consentimiento(PAC1)
    assert h.svc.resolver(actor("ADMIN"), hallazgo_id=hallazgo.id).resuelto is True


# ---------------------------------------------------------------------------
# 2.10 — aislamiento multi-tenant
# ---------------------------------------------------------------------------


def test_hallazgo_paciente_otro_tenant_404():
    h = HarnessOdontograma()
    h.seed_paciente(PAC9, tenant=T2)
    h.dar_consentimiento(PAC9, tenant=T2)
    with pytest.raises(NoEncontrado) as exc:
        h.svc.registrar_hallazgo(
            actor("ADMIN", tenant=T1),
            paciente_id=PAC9,
            pieza_fdi=36,
            hallazgo="hallazgo demo",
            fecha=d3(),
            profesional_id=P1,
        )
    assert exc.value.codigo == 404
    assert h.hallazgos.total(T1) == 0
    assert h.hallazgos.total(T2) == 0
    # T2 tampoco puede leer el historial del paciente de T1.
    h.seed_paciente(PAC1, tenant=T1)
    with pytest.raises(NoEncontrado):
        h.svc.listar_historial(
            actor("RECEPCION", tenant=T2), paciente_id=PAC1, pieza_fdi=36
        )


# ---------------------------------------------------------------------------
# 2.11 — fecha naive
# ---------------------------------------------------------------------------


def test_fecha_naive_422():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    with pytest.raises(Invalido) as exc:
        h.svc.registrar_hallazgo(
            actor("ADMIN"),
            paciente_id=PAC1,
            pieza_fdi=36,
            hallazgo="hallazgo demo",
            fecha=datetime(2026, 11, 10, 10, 0),  # sin offset
            profesional_id=P1,
        )
    assert exc.value.codigo == 422
    assert h.hallazgos.total(T1) == 0
    # Con offset -03:00 sí se persiste.
    h.svc.registrar_hallazgo(
        actor("ADMIN"),
        paciente_id=PAC1,
        pieza_fdi=36,
        hallazgo="hallazgo demo",
        fecha=d3(),
        profesional_id=P1,
    )
    assert h.hallazgos.total(T1) == 1
