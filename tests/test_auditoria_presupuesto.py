"""Tasks 9.2–9.5 — auditoría del presupuesto append-only y sin PHI (D12).

Creación, emisión, vencimiento persistido, aceptación e imputación escriben
auditoría con `tenant_id`, actor, entidad y montos; nunca nombre, DNI, teléfono
ni texto clínico.
"""
from __future__ import annotations

import pytest
from _odontograma_helpers import PREST1, d3
from _presupuesto_helpers import (
    HarnessPresupuesto,
    agregar_linea,
    crear_borrador,
    emitir,
    presupuesto_vigente,
    registrar_aceptacion,
)
from conftest import T1

from app.presupuesto.servicio import Conflicto


def test_aceptacion_e_imputacion_auditadas_sin_phi():
    h = HarnessPresupuesto()
    presupuesto_id, lineas = presupuesto_vigente(h, monto=100000)

    registrar_aceptacion(h, presupuesto_id, lineas[0], ahora=d3("2026-11-10", 11))

    acciones = [e.accion for e in h.auditoria.entradas]
    assert "ACEPTACION_REGISTRADA" in acciones
    assert "IMPUTACION_REGISTRADA" in acciones

    aceptacion = next(
        e for e in h.auditoria.entradas if e.accion == "ACEPTACION_REGISTRADA"
    )
    assert aceptacion.tenant_id == T1
    assert aceptacion.actor == "usuario-1"
    assert aceptacion.entidad_id == presupuesto_id
    assert aceptacion.despues is not None
    assert aceptacion.despues["linea_id"] == lineas[0]
    assert aceptacion.despues["acepta"] is True
    assert aceptacion.despues["monto_centavos"] == 100000

    imputacion = next(
        e for e in h.auditoria.entradas if e.accion == "IMPUTACION_REGISTRADA"
    )
    assert imputacion.despues is not None
    assert imputacion.despues["monto_paciente_centavos"] == 100000
    assert imputacion.despues["monto_os_centavos"] == 0

    for entrada in h.auditoria.entradas:
        payload = str(entrada.antes) + str(entrada.despues)
        assert "Paciente Demo" not in payload
        assert "+5491" not in payload
        assert "telefono" not in payload
        assert "nombre" not in payload


def test_presupuesto_creado_y_emitido_auditados():
    h = HarnessPresupuesto()
    borrador = crear_borrador(h)
    agregar_linea(h, borrador.id, monto=100000)
    emitir(h, borrador.id, vence_en=d3("2026-12-31", 23, 59))

    creado = next(e for e in h.auditoria.entradas if e.accion == "PRESUPUESTO_CREADO")
    assert creado.tenant_id == T1
    assert creado.actor == "usuario-1"
    assert creado.entidad_id == borrador.id
    assert creado.despues is not None and creado.despues["estado"] == "BORRADOR"

    emitido = next(e for e in h.auditoria.entradas if e.accion == "PRESUPUESTO_EMITIDO")
    assert emitido.tenant_id == T1
    assert emitido.entidad_id == borrador.id
    assert emitido.despues is not None
    assert emitido.despues["estado"] == "VIGENTE"
    assert emitido.despues["vence_en"] is not None
    payload = str(creado.antes) + str(creado.despues) + str(emitido.antes) + str(emitido.despues)
    assert "Paciente Demo" not in payload
    assert "+5491" not in payload


def test_vencido_persistido_auditado():
    h = HarnessPresupuesto()
    presupuesto_id, lineas = presupuesto_vigente(
        h,
        vence_en=d3("2026-11-05"),
        ahora_emision=d3("2026-11-01"),
    )

    with pytest.raises(Conflicto) as exc:
        registrar_aceptacion(h, presupuesto_id, lineas[0], ahora=d3("2026-11-10"))
    assert exc.value.codigo == 409

    persistido = h.presupuestos.obtener(tenant_id=T1, presupuesto_id=presupuesto_id)
    assert persistido is not None and persistido.estado == "VENCIDO"
    vencido = next(
        e for e in h.auditoria.entradas if e.accion == "PRESUPUESTO_VENCIDO"
    )
    assert vencido.tenant_id == T1
    assert vencido.entidad_id == presupuesto_id
    assert vencido.despues is not None
    assert vencido.despues["estado"] == "VENCIDO"
    assert vencido.despues["vence_en"] is not None
    assert h.aceptaciones.total(T1) == 0
    assert h.imputacion.llamadas_caja == []
    assert h.imputacion.llamadas_agenda == []


def test_auditoria_sin_update_ni_delete():
    h = HarnessPresupuesto()
    # El puerto es append-only: no expone update/delete.
    assert not hasattr(h.auditoria, "borrar")
    assert not hasattr(h.auditoria, "actualizar")
    assert not hasattr(h.auditoria, "eliminar")

    antes = len(h.auditoria.entradas)
    borrador = crear_borrador(h)
    agregar_linea(h, borrador.id, prestacion_id=PREST1, monto=100000)
    assert len(h.auditoria.entradas) > antes
    primera = h.auditoria.entradas[0]
    assert primera.accion == "PRESUPUESTO_CREADO"
