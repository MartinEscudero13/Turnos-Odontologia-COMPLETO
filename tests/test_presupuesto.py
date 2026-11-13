"""Tasks 4.2–4.28 — dominio del presupuesto (líneas, cobertura y estados).

Dominio puro con adaptadores en memoria, datos ficticios ("Paciente Demo",
"Conducto Demo" con `precio_base=150000` centavos, obras sociales `OS-1`/`OS-2`)
y reloj inyectado en `-03:00`. La concurrencia real de aceptación (5.12) vive en
`test_aceptacion_concurrente_pg.py`.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from _odontograma_helpers import PAC1, PAC9, PREST1, PREST9, TZ, actor, d3
from _presupuesto_helpers import (
    OS1,
    OS2,
    PAC2,
    HarnessPresupuesto,
    agregar_linea,
    crear_borrador,
    emitir,
    presupuesto_vigente,
    registrar_aceptacion,
)
from conftest import T1, T2

from app.presupuesto.servicio import Conflicto, TramoCobertura
from app.turnos.servicio import Invalido, NoEncontrado

VENCE_DIC = datetime(2026, 12, 31, 23, 59, 59, tzinfo=TZ)
VENCE_PASADO = d3("2026-11-01", hora=0)


# ---------------------------------------------------------------------------
# 4.2 → 4.4 — creación del presupuesto
# ---------------------------------------------------------------------------


def test_crear_presupuesto_borrador_sin_lineas():
    h = HarnessPresupuesto()
    creado = crear_borrador(h)
    assert creado.tenant_id == T1
    assert creado.paciente_id == PAC1
    assert creado.estado == "BORRADOR"
    assert creado.vence_en is None
    assert h.lineas.listar(tenant_id=T1, presupuesto_id=creado.id) == []
    assert h.imputacion.llamadas_agenda == []
    assert h.imputacion.llamadas_caja == []
    assert [e.accion for e in h.auditoria.de_tenant(T1)] == ["PRESUPUESTO_CREADO"]


def test_crear_presupuesto_paciente_otro_tenant_404():
    h = HarnessPresupuesto()
    with pytest.raises(NoEncontrado) as exc:
        crear_borrador(h, paciente_id=PAC9)
    assert exc.value.codigo == 404
    assert h.presupuestos.total(T1) == 0
    assert h.presupuestos.total(T2) == 0


def test_crear_con_vence_en_422():
    h = HarnessPresupuesto()
    with pytest.raises(Invalido) as exc:
        h.svc.crear(
            actor("RECEPCION"),
            paciente_id=PAC1,
            vence_en=VENCE_DIC,
            ahora=d3(),
        )
    assert exc.value.codigo == 422
    assert h.presupuestos.total(T1) == 0


# ---------------------------------------------------------------------------
# 4.5 → 4.10 — cobertura de la línea
# ---------------------------------------------------------------------------


def test_linea_con_cobertura_50_por_ciento():
    h = HarnessPresupuesto()
    h.seed_cobertura(modo="PORCENTAJE", valor=50, obra_social_id=OS1)
    borrador = crear_borrador(h)
    linea = agregar_linea(h, borrador.id, monto=100000)
    assert linea.monto == 100000
    assert linea.cobertura_os == 50000
    assert linea.a_cargo_paciente == 50000
    assert linea.origen_cobertura == "CONFIGURADA"
    assert linea.validada_en_vivo is False
    assert h.coberturas.consultas == [(T1, OS1, PREST1)]


def test_cobertura_de_otra_obra_social_no_aplica():
    h = HarnessPresupuesto()
    h.seed_cobertura(modo="PORCENTAJE", valor=50, obra_social_id=OS2)
    borrador = crear_borrador(h)
    linea = agregar_linea(h, borrador.id, monto=100000)
    assert linea.cobertura_os == 0
    assert linea.a_cargo_paciente == 100000
    assert linea.origen_cobertura == "SIN_COBERTURA"
    # M1: sólo se consulta la obra social del paciente, nunca la de OS-2.
    assert h.coberturas.consultas == [(T1, OS1, PREST1)]
    assert all(consulta[1] != OS2 for consulta in h.coberturas.consultas)


def test_sin_obra_social_100_por_ciento_particular():
    h = HarnessPresupuesto()
    h.seed_cobertura(modo="PORCENTAJE", valor=50, obra_social_id=OS1)
    borrador = crear_borrador(h, paciente_id=PAC2)
    linea = agregar_linea(h, borrador.id, monto=100000)
    assert linea.cobertura_os == 0
    assert linea.a_cargo_paciente == 100000
    assert linea.origen_cobertura == "SIN_COBERTURA"
    assert linea.validada_en_vivo is False
    # Sin `obra_social_id` no se consulta ninguna cobertura.
    assert h.coberturas.consultas == []


def test_cobertura_inexistente_cae_a_particular():
    h = HarnessPresupuesto()
    borrador = crear_borrador(h)
    linea = agregar_linea(h, borrador.id, monto=150000)
    assert linea.cobertura_os == 0
    assert linea.a_cargo_paciente == 150000
    assert linea.origen_cobertura == "SIN_COBERTURA"
    assert h.coberturas.consultas == [(T1, OS1, PREST1)]


def test_cobertura_por_monto_fijo():
    h = HarnessPresupuesto()
    h.seed_cobertura(modo="MONTO", valor=40000)
    borrador = crear_borrador(h)
    linea = agregar_linea(h, borrador.id, monto=100000)
    assert linea.cobertura_os == 40000
    assert linea.a_cargo_paciente == 60000
    assert linea.origen_cobertura == "CONFIGURADA"


def test_tope_recorta_cobertura():
    h = HarnessPresupuesto()
    h.seed_cobertura(modo="PORCENTAJE", valor=80, tope=50000)
    borrador = crear_borrador(h)
    con_tope = agregar_linea(h, borrador.id, monto=100000)
    assert con_tope.cobertura_os == 50000
    assert con_tope.a_cargo_paciente == 50000

    h.seed_cobertura(modo="PORCENTAJE", valor=40, tope=50000)
    borrador2 = crear_borrador(h)
    debajo_del_tope = agregar_linea(h, borrador2.id, monto=100000)
    assert debajo_del_tope.cobertura_os == 40000
    assert debajo_del_tope.a_cargo_paciente == 60000


def test_cobertura_mayor_al_monto_se_recorta():
    h = HarnessPresupuesto()
    h.seed_cobertura(modo="MONTO", valor=200000)
    borrador = crear_borrador(h)
    linea = agregar_linea(h, borrador.id, monto=100000)
    assert linea.cobertura_os == 100000
    assert linea.a_cargo_paciente == 0


def test_monto_cero_valido():
    h = HarnessPresupuesto()
    borrador = crear_borrador(h)
    linea = agregar_linea(h, borrador.id, monto=0)
    assert linea.monto == 0
    assert linea.cobertura_os == 0
    assert linea.a_cargo_paciente == 0
    assert h.lineas.total(T1) == 1


# ---------------------------------------------------------------------------
# 4.11 → 4.13 — rechazos de la línea sin persistir
# ---------------------------------------------------------------------------


def test_monto_negativo_422_sin_persistir():
    h = HarnessPresupuesto()
    borrador = crear_borrador(h)
    with pytest.raises(Invalido) as exc:
        agregar_linea(h, borrador.id, monto=-1)
    assert exc.value.codigo == 422
    assert h.lineas.listar(tenant_id=T1, presupuesto_id=borrador.id) == []


def test_monto_no_entero_422():
    h = HarnessPresupuesto()
    borrador = crear_borrador(h)
    for monto in (1000.5, "100000"):
        with pytest.raises(Invalido) as exc:
            agregar_linea(h, borrador.id, monto=monto)
        assert exc.value.codigo == 422
    assert h.lineas.listar(tenant_id=T1, presupuesto_id=borrador.id) == []


def test_linea_con_prestacion_de_otro_tenant_404():
    h = HarnessPresupuesto()
    borrador = crear_borrador(h)
    with pytest.raises(NoEncontrado) as exc:
        agregar_linea(h, borrador.id, prestacion_id=PREST9)
    assert exc.value.codigo == 404
    assert h.lineas.listar(tenant_id=T1, presupuesto_id=borrador.id) == []


def test_linea_con_pieza_fdi_invalida_422():
    h = HarnessPresupuesto()
    borrador = crear_borrador(h)
    for pieza in (19, 29, 49, 20, 30, 40):
        with pytest.raises(Invalido) as exc:
            agregar_linea(h, borrador.id, pieza_fdi=pieza)
        assert exc.value.codigo == 422
    assert h.lineas.listar(tenant_id=T1, presupuesto_id=borrador.id) == []


# ---------------------------------------------------------------------------
# 4.14 → 4.17 — emisión y vencimiento
# ---------------------------------------------------------------------------


def test_emitir_exige_al_menos_una_linea():
    h = HarnessPresupuesto()
    vacio = crear_borrador(h)
    with pytest.raises(Conflicto) as exc:
        emitir(h, vacio.id)
    assert exc.value.codigo == 409
    assert h.presupuestos.obtener(tenant_id=T1, presupuesto_id=vacio.id).estado == "BORRADOR"

    con_linea = crear_borrador(h)
    agregar_linea(h, con_linea.id)
    vigente = emitir(h, con_linea.id)
    assert vigente.estado == "VIGENTE"
    assert vigente.vence_en is None


def test_emitir_fija_el_vence_en():
    h = HarnessPresupuesto()
    borrador = crear_borrador(h)
    agregar_linea(h, borrador.id)
    vigente = emitir(h, borrador.id, vence_en=VENCE_DIC)
    assert vigente.estado == "VIGENTE"
    assert vigente.vence_en == VENCE_DIC
    assert h.presupuestos.obtener(tenant_id=T1, presupuesto_id=borrador.id).vence_en == VENCE_DIC
    auditoria = [e.accion for e in h.auditoria.de_tenant(T1)]
    assert auditoria == ["PRESUPUESTO_CREADO", "LINEA_PRESUPESTADA", "PRESUPUESTO_EMITIDO"]


def test_emitir_con_vence_en_pasado_422():
    h = HarnessPresupuesto()
    borrador = crear_borrador(h)
    agregar_linea(h, borrador.id)
    with pytest.raises(Invalido) as exc:
        emitir(h, borrador.id, vence_en=VENCE_PASADO, ahora=d3())
    assert exc.value.codigo == 422
    persistido = h.presupuestos.obtener(tenant_id=T1, presupuesto_id=borrador.id)
    assert persistido.estado == "BORRADOR"
    assert persistido.vence_en is None


def test_vence_en_naive_422():
    h = HarnessPresupuesto()
    borrador = crear_borrador(h)
    agregar_linea(h, borrador.id)
    for naive in (datetime(2026, 11, 30, 23, 59, 59), "2026-11-30T23:59:59"):
        with pytest.raises(Invalido) as exc:
            emitir(h, borrador.id, vence_en=naive)
        assert exc.value.codigo == 422
    persistido = h.presupuestos.obtener(tenant_id=T1, presupuesto_id=borrador.id)
    assert persistido.estado == "BORRADOR"
    assert persistido.vence_en is None


# ---------------------------------------------------------------------------
# 4.18 — la línea no se edita ni se borra
# ---------------------------------------------------------------------------


def test_editar_lineas_solo_en_borrador():
    h = HarnessPresupuesto()
    presupuesto_id, lineas = presupuesto_vigente(h)
    antes = h.lineas.listar(tenant_id=T1, presupuesto_id=presupuesto_id)
    assert len(antes) == 1
    with pytest.raises(Conflicto) as exc:
        agregar_linea(h, presupuesto_id, monto=50000)
    assert exc.value.codigo == 409
    despues = h.lineas.listar(tenant_id=T1, presupuesto_id=presupuesto_id)
    assert despues == antes
    assert [linea.id for linea in despues] == lineas


def test_linea_sin_patch_ni_delete():
    h = HarnessPresupuesto()
    presupuesto_id, lineas = presupuesto_vigente(h)
    # El dominio no expone mutadores de línea (v1: corregir es rehacer el
    # presupuesto en BORRADOR); el borde responde 405/404 y la base no tiene
    # UPDATE ni DELETE sobre `presupuesto_lineas` (D8.1).
    for nombre in ("editar_linea", "actualizar_linea", "eliminar_linea", "borrar_linea"):
        assert not hasattr(h.svc, nombre)
    for nombre in ("actualizar", "editar", "eliminar", "borrar"):
        assert not hasattr(h.lineas, nombre)
    assert [linea.id for linea in h.lineas.listar(tenant_id=T1, presupuesto_id=presupuesto_id)] == (
        lineas
    )


# ---------------------------------------------------------------------------
# 4.19 → 4.23 — estados y vencimiento al leer/aceptar
# ---------------------------------------------------------------------------


def test_presupuesto_vencido_no_acepta():
    h = HarnessPresupuesto()
    presupuesto_id, lineas = presupuesto_vigente(
        h, vence_en=VENCE_PASADO, ahora_emision=d3("2026-10-01")
    )
    with pytest.raises(Conflicto) as exc:
        registrar_aceptacion(h, presupuesto_id, lineas[0], ahora=d3())
    assert exc.value.codigo == 409
    persistido = h.presupuestos.obtener(tenant_id=T1, presupuesto_id=presupuesto_id)
    assert persistido.estado == "VENCIDO"
    assert h.aceptaciones.total(T1) == 0
    assert h.imputacion.llamadas_agenda == []
    assert h.imputacion.llamadas_caja == []
    vencimientos = h.auditoria.de_accion("PRESUPUESTO_VENCIDO")
    assert len(vencimientos) == 1
    assert vencimientos[0].antes == {"estado": "VIGENTE"}
    assert vencimientos[0].despues is not None
    assert vencimientos[0].despues["estado"] == "VENCIDO"
    assert vencimientos[0].despues["vence_en"] == VENCE_PASADO.isoformat()


def test_vencido_ya_persistido_no_se_reaudita():
    h = HarnessPresupuesto()
    presupuesto_id, lineas = presupuesto_vigente(
        h, vence_en=VENCE_PASADO, ahora_emision=d3("2026-10-01")
    )
    for _ in range(2):
        with pytest.raises(Conflicto) as exc:
            registrar_aceptacion(h, presupuesto_id, lineas[0], ahora=d3())
        assert exc.value.codigo == 409
    # Una sola entrada VENCIDO y ninguna aceptación: el 409 persistido no se
    # repite ni duplica auditoría (D5).
    assert len(h.auditoria.de_accion("PRESUPUESTO_VENCIDO")) == 1
    assert h.aceptaciones.total(T1) == 0
    assert h.presupuestos.obtener(tenant_id=T1, presupuesto_id=presupuesto_id).estado == "VENCIDO"


def test_lectura_de_vencido_no_persiste():
    h = HarnessPresupuesto()
    presupuesto_id, _ = presupuesto_vigente(
        h, vence_en=VENCE_PASADO, ahora_emision=d3("2026-10-01")
    )
    auditoria_antes = len(h.auditoria.entradas)
    for _ in range(2):
        leido = h.svc.obtener(
            actor("RECEPCION"),
            presupuesto_id=presupuesto_id,
            ahora=d3(),
        )
        assert leido.estado_reportado == "VENCIDO"
    persistido = h.presupuestos.obtener(tenant_id=T1, presupuesto_id=presupuesto_id)
    assert persistido.estado == "VIGENTE"
    assert len(h.auditoria.entradas) == auditoria_antes


def test_parcial_no_vence_por_reloj():
    h = HarnessPresupuesto()
    presupuesto_id, lineas = presupuesto_vigente(
        h, cantidad_lineas=2, vence_en=VENCE_PASADO, ahora_emision=d3("2026-10-01")
    )
    parcial = registrar_aceptacion(h, presupuesto_id, lineas[0], ahora=d3("2026-10-02"))
    assert parcial.presupuesto.estado == "PARCIAL"

    leido = h.svc.obtener(
        actor("RECEPCION"),
        presupuesto_id=presupuesto_id,
        ahora=d3(),
    )
    assert leido.estado_reportado == "PARCIAL"
    assert leido.presupuesto.estado == "PARCIAL"

    # Aceptar la línea pendiente sigue funcionando aunque el reloj pasó el vence_en.
    resto = registrar_aceptacion(h, presupuesto_id, lineas[1], ahora=d3())
    assert resto.presupuesto.estado == "ACEPTADO"
    assert h.aceptaciones.total(T1) == 2


def test_sin_vence_en_no_vence_solo():
    h = HarnessPresupuesto()
    presupuesto_id, _ = presupuesto_vigente(h)
    leido = h.svc.obtener(
        actor("RECEPCION"),
        presupuesto_id=presupuesto_id,
        ahora=d3("2026-12-31"),
    )
    assert leido.estado_reportado == "VIGENTE"
    assert h.presupuestos.obtener(tenant_id=T1, presupuesto_id=presupuesto_id).estado == "VIGENTE"


def test_no_se_acepta_en_borrador():
    h = HarnessPresupuesto()
    borrador = crear_borrador(h)
    linea = agregar_linea(h, borrador.id)
    with pytest.raises(Conflicto) as exc:
        registrar_aceptacion(h, borrador.id, linea.id)
    assert exc.value.codigo == 409
    assert h.aceptaciones.total(T1) == 0
    assert h.imputacion.llamadas_caja == []
    assert h.imputacion.llamadas_agenda == []


# ---------------------------------------------------------------------------
# 4.24 → 4.27 — configuración inválida y guard del resultado
# ---------------------------------------------------------------------------


def test_cobertura_porcentaje_invalido_cae_a_particular():
    h = HarnessPresupuesto()
    for valor in (150, -10):
        h.seed_cobertura(modo="PORCENTAJE", valor=valor)
        borrador = crear_borrador(h)
        linea = agregar_linea(h, borrador.id, monto=100000)
        assert linea.cobertura_os == 0
        assert linea.a_cargo_paciente == 100000
        assert linea.origen_cobertura == "SIN_COBERTURA"
        assert linea.validada_en_vivo is False


def test_cobertura_monto_o_tope_negativo_cae_a_particular():
    h = HarnessPresupuesto()
    h.seed_cobertura(modo="MONTO", valor=-50000)
    negativo = agregar_linea(h, crear_borrador(h).id, monto=100000)
    assert negativo.cobertura_os == 0 and negativo.a_cargo_paciente == 100000

    h.seed_cobertura(modo="PORCENTAJE", valor=50, tope=-1)
    tope_negativo = agregar_linea(h, crear_borrador(h).id, monto=100000)
    assert tope_negativo.cobertura_os == 0
    assert tope_negativo.a_cargo_paciente == 100000


def test_totales_inconsistentes_caen_a_fallback():
    def calculadora_inconsistente(_monto: int, _config: object) -> TramoCobertura:
        return TramoCobertura(
            cobertura_os=60000,
            a_cargo_paciente=30000,
            origen_cobertura="CONFIGURADA",
        )

    h = HarnessPresupuesto(calculadora=calculadora_inconsistente)
    h.seed_cobertura(modo="PORCENTAJE", valor=50)
    linea = agregar_linea(h, crear_borrador(h).id, monto=100000)
    # Nunca se persiste la combinación inconsistente: 60000 + 30000 != 100000.
    assert linea.cobertura_os == 0
    assert linea.a_cargo_paciente == 100000
    assert linea.origen_cobertura == "SIN_COBERTURA"
    assert linea.validada_en_vivo is False
    assert linea.cobertura_os + linea.a_cargo_paciente == linea.monto
    assert len(h.auditoria.de_accion("COBERTURA_INVALIDA_DESCARTADA")) == 1


def test_cobertura_invalida_auditada_sin_phi():
    h = HarnessPresupuesto()
    h.seed_cobertura(modo="PORCENTAJE", valor=150)
    agregar_linea(h, crear_borrador(h).id, monto=100000)
    entradas = h.auditoria.de_accion("COBERTURA_INVALIDA_DESCARTADA")
    assert len(entradas) == 1
    entrada = entradas[0]
    assert entrada.tenant_id == T1
    assert entrada.entidad == "presupuesto"
    assert entrada.despues is not None
    assert entrada.despues["prestacion_id"] == PREST1
    assert entrada.despues["obra_social_id"] == OS1
    assert isinstance(entrada.despues["motivo"], str) and entrada.despues["motivo"]
    assert "paciente_id" not in entrada.despues
    assert "Paciente Demo" not in str(entrada)


# ---------------------------------------------------------------------------
# 4.28 — el origen de cobertura no se recalcula al leer
# ---------------------------------------------------------------------------


def test_origen_cobertura_no_se_recalcula_al_leer():
    h = HarnessPresupuesto()
    borrador = crear_borrador(h)
    linea = agregar_linea(h, borrador.id, monto=100000)
    assert linea.origen_cobertura == "SIN_COBERTURA"
    consultas_al_crear = list(h.coberturas.consultas)

    # C-12 carga la cobertura después de emitido el presupuesto.
    h.seed_cobertura(modo="PORCENTAJE", valor=50)
    leido = h.svc.obtener(
        actor("RECEPCION"),
        presupuesto_id=borrador.id,
        ahora=d3(),
    )
    [linea_leida] = leido.lineas
    assert linea_leida.linea.cobertura_os == 0
    assert linea_leida.linea.a_cargo_paciente == 100000
    assert linea_leida.linea.origen_cobertura == "SIN_COBERTURA"
    assert linea_leida.linea.validada_en_vivo is False
    # La lectura no vuelve a consultar el puerto de cobertura (M2).
    assert h.coberturas.consultas == consultas_al_crear
