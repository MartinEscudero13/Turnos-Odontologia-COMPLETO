"""Tasks 10.1–10.8 — auditoría de caja (TDD rojo primero).

Criterios (design D11, RN-AU-02, RN-CL-04):

- toda mutación de caja deja una entrada append-only con `tenant_id`, actor,
  acción, `antes`/`después` y timestamp, sin PHI;
- la anulación registra el antes y el después; el compensatorio referencia al
  original; el ajuste post-cierre referencia al cierre y al compensatorio;
- la observación del cierre se registra sólo como presencia (`observacion_cargada`);
- `UPDATE`/`DELETE` de una entrada de auditoría son rechazados en la base.

Datos ficticios: T1, U1 (RECEPCION), U2 (ADMIN), PACI-1, "Paciente Demo".
"""
from __future__ import annotations

import json
import os
import uuid

import pytest
from _caja_helpers import U1, U2, HarnessCaja, actor, d3
from conftest import T1
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from app.caja.puertos import AccionCaja, CobroPendiente, EntradaAuditoria

PG_URL = os.environ.get("C02_DATABASE_URL")
requiere_pg = pytest.mark.skipif(not PG_URL, reason="C02_DATABASE_URL no configurada")

FECHA = "2026-11-10"


def _entrada(h: HarnessCaja, accion: AccionCaja) -> EntradaAuditoria:
    entradas = h.auditoria.de_accion(accion)
    assert len(entradas) == 1, f"se esperaba una entrada {accion}, hay {len(entradas)}"
    return entradas[0]


def test_movimiento_registrado_auditado() -> None:
    # GIVEN T1 con el usuario U1.
    h = HarnessCaja()

    # WHEN U1 registra un movimiento.
    movimiento = h.registrar(monto=150000, medio="EFECTIVO", fecha=FECHA)

    # THEN se escribe MOVIMIENTO_CAJA_REGISTRADO con ids, fecha, medio y monto.
    entrada = _entrada(h, "MOVIMIENTO_CAJA_REGISTRADO")
    assert entrada.tenant_id == T1
    assert entrada.actor == U1
    assert entrada.entidad == "movimiento_caja"
    assert entrada.entidad_id == movimiento.id
    assert entrada.antes is None
    assert entrada.despues is not None
    assert entrada.despues["fecha"] == FECHA
    assert entrada.despues["medio"] == "EFECTIVO"
    assert entrada.despues["tipo"] == "INGRESO"
    assert entrada.despues["monto"] == 150000
    assert "nombre" not in entrada.despues
    assert "dni" not in entrada.despues


def test_anulacion_auditada_con_antes_y_despues() -> None:
    # GIVEN T1 con un movimiento vigente.
    h = HarnessCaja()
    movimiento = h.registrar(monto=150000, medio="EFECTIVO", fecha=FECHA)

    # WHEN ADMIN lo anula con motivo.
    h.anular(movimiento.id, motivo="cobro duplicado", actor_=actor("ADMIN", user_id=U2))

    # THEN MOVIMIENTO_CAJA_ANULADO registra el antes y el después (N8).
    entrada = _entrada(h, "MOVIMIENTO_CAJA_ANULADO")
    assert entrada.entidad_id == movimiento.id
    assert entrada.actor == U2
    assert entrada.antes == {"anulado": False}
    assert entrada.despues is not None
    assert entrada.despues["anulado"] is True
    assert entrada.despues["motivo_anulacion"] == "cobro duplicado"
    assert "Paciente Demo" not in repr(entrada.despues)


def test_compensatorio_auditado_con_referencia() -> None:
    # GIVEN T1 con un movimiento de un día cerrado.
    h = HarnessCaja()
    original = h.registrar(monto=150000, medio="EFECTIVO", fecha=FECHA)
    h.cerrar_dia(fecha=FECHA, efectivo_contado=150000, responsable_id=U2)
    h.ahora = d3("2026-11-11", hora=9)

    # WHEN ADMIN lo anula y se crea el compensatorio.
    h.anular(original.id, motivo="error de carga", actor_=actor("ADMIN", user_id=U2))

    # THEN MOVIMIENTO_COMPENSATORIO_REGISTRADO referencia al original.
    entrada = _entrada(h, "MOVIMIENTO_COMPENSATORIO_REGISTRADO")
    assert "Paciente Demo" not in repr(entrada.despues)
    assert entrada.despues is not None
    assert entrada.despues["compensa_a_id"] == original.id
    assert entrada.despues["tipo"] == "EGRESO"
    assert entrada.despues["medio"] == "EFECTIVO"
    assert entrada.despues["monto"] == 150000
    assert entrada.despues["fecha"] == "2026-11-11"


def test_ajuste_post_cierre_auditado() -> None:
    # GIVEN T1 con un movimiento y un pendiente de un día cerrado.
    h = HarnessCaja()
    original = h.registrar(monto=150000, medio="EFECTIVO", fecha=FECHA)
    h.cerrar_dia(fecha=FECHA, efectivo_contado=150000, responsable_id=U2)
    h.ahora = d3("2026-11-11", hora=9)

    # WHEN ADMIN anula el movimiento (se asienta el ajuste).
    h.anular(original.id, motivo="error de carga", actor_=actor("ADMIN", user_id=U2))

    # THEN AJUSTE_POST_CIERRE_REGISTRADO lleva cierre, tipo, monto y compensatorio.
    cierre = h.cierres.obtener(tenant_id=T1, fecha=d3("2026-11-10").date())
    assert cierre is not None
    [ajuste] = h.ajustes.listar_por_cierre(tenant_id=T1, cierre_id=cierre.id)
    entrada = _entrada(h, "AJUSTE_POST_CIERRE_REGISTRADO")
    assert entrada.entidad_id == ajuste.id
    assert entrada.despues is not None
    assert entrada.despues["cierre_id"] == cierre.id
    assert entrada.despues["tipo"] == "AJUSTE_ANULACION"
    assert entrada.despues["monto"] == 150000
    assert entrada.despues["medio"] == "EFECTIVO"
    assert entrada.despues["compensatorio_id"] == ajuste.compensatorio_id
    assert "Paciente Demo" not in repr(entrada.despues)


def test_pendientes_auditados() -> None:
    # GIVEN T1 con una imputación sin medio.
    h = HarnessCaja()
    pendiente = h.imputar_tramo(monto=60000, medio=None)
    assert isinstance(pendiente, CobroPendiente)

    # WHEN se registra el pendiente y luego se cobra.
    h.cobrar(pendiente.id, medio="TRANSFERENCIA")

    # THEN deja COBRO_PENDIENTE_REGISTRADO y COBRO_PENDIENTE_RESUELTO sin PHI.
    registrado = _entrada(h, "COBRO_PENDIENTE_REGISTRADO")
    assert registrado.entidad_id == pendiente.id
    assert registrado.despues is not None
    assert registrado.despues["monto"] == 60000
    assert "Paciente Demo" not in repr(registrado.despues)

    resuelto = _entrada(h, "COBRO_PENDIENTE_RESUELTO")
    assert resuelto.entidad_id == pendiente.id
    assert resuelto.antes == {"resuelto": False}
    assert resuelto.despues is not None
    assert resuelto.despues["resuelto"] is True
    assert resuelto.despues["medio"] == "TRANSFERENCIA"
    movimiento = resuelto.despues["movimiento_id"]
    assert isinstance(movimiento, str) and movimiento.startswith("movimiento-")


def test_cierre_auditado_y_motivo() -> None:
    # GIVEN T1 con 100000 en efectivo y un faltante de 5000 explicado.
    h = HarnessCaja()
    h.registrar(monto=100000, medio="EFECTIVO", fecha=FECHA)

    # WHEN se cierra el día con diferencia y motivo.
    cierre = h.cerrar_dia(
        fecha=FECHA,
        efectivo_contado=95000,
        responsable_id=U1,
        motivo_diferencia="faltante de caja",
    )

    # THEN CIERRE_DIARIO_REGISTRADO lleva ids, totales, diferencia y motivo.
    entrada = _entrada(h, "CIERRE_DIARIO_REGISTRADO")
    assert entrada.entidad == "cierre_diario"
    assert entrada.entidad_id == cierre.id
    assert entrada.antes is None
    assert entrada.despues is not None
    assert entrada.despues["fecha"] == FECHA
    assert entrada.despues["total_efectivo"] == 100000
    assert entrada.despues["efectivo_contado"] == 95000
    assert entrada.despues["diferencia"] == -5000
    assert entrada.despues["responsable_id"] == U1
    assert entrada.despues["motivo_diferencia"] == "faltante de caja"
    assert entrada.despues["observacion_cargada"] is False


def test_auditoria_no_copia_observacion() -> None:
    # GIVEN T1 con un cierre que tiene una observación operativa.
    h = HarnessCaja()
    observacion = "se revisó el cajón con el responsable"
    h.registrar(monto=100000, medio="EFECTIVO", fecha=FECHA)
    h.cerrar_dia(
        fecha=FECHA,
        efectivo_contado=95000,
        responsable_id=U1,
        motivo_diferencia="faltante de caja",
        observacion=observacion,
    )

    # WHEN se consulta la entrada de auditoría del cierre.
    entrada = _entrada(h, "CIERRE_DIARIO_REGISTRADO")

    # THEN sólo se registra su presencia, no su contenido (D11).
    assert entrada.despues is not None
    assert entrada.despues["observacion_cargada"] is True
    assert observacion not in repr(entrada.despues)
    for valor in h.auditoria.entradas:
        assert observacion not in repr(valor.despues)


def test_auditoria_append_only() -> None:
    # GIVEN una entrada de auditoría de caja.
    h = HarnessCaja()
    h.registrar(monto=100000, medio="EFECTIVO", fecha=FECHA)
    [entrada] = h.auditoria.entradas

    # WHEN se intenta mutar la auditoría desde el puerto.
    # THEN el puerto no expone update/delete y la entrada original sigue igual.
    for metodo in ("actualizar", "borrar", "eliminar", "update", "delete"):
        assert not hasattr(h.auditoria, metodo)
    copia = h.auditoria.de_tenant(T1)
    copia.clear()
    assert h.auditoria.entradas == [entrada]


# ---------------------------------------------------------------------------
# 10.8 (integración) — la base rechaza UPDATE/DELETE de auditoría
# ---------------------------------------------------------------------------


@requiere_pg
def test_auditoria_append_only_en_pg() -> None:
    assert PG_URL is not None
    engine = create_engine(PG_URL, future=True)
    tenant = str(uuid.uuid4())
    try:
        with engine.connect() as owner:
            tx = owner.begin()
            owner.execute(
                text(
                    "INSERT INTO tenants (id, nombre, slug)"
                    " VALUES (:id, 'Auditoría Demo', :slug)"
                ),
                {"id": tenant, "slug": f"audit-c10-{tenant[:8]}"},
            )
            tx.commit()

        with engine.connect() as app:
            app.execute(text("SET ROLE turnos_app"))
            app.execute(
                text("SELECT set_config('app.tenant_id', :tenant, false)"),
                {"tenant": tenant},
            )
            app.execute(
                text(
                    "INSERT INTO auditoria"
                    " (tenant_id, actor_id, accion, entidad, entidad_id, antes, despues)"
                    " VALUES (:tenant, :actor, 'MOVIMIENTO_CAJA_REGISTRADO',"
                    "  'movimiento_caja', :entidad, NULL, :despues)"
                ),
                {
                    "tenant": tenant,
                    "actor": U1,
                    "entidad": str(uuid.uuid4()),
                    "despues": json.dumps({"monto": 100000}),
                },
            )
            app.commit()

        with engine.connect() as app:
            app.execute(text("SET ROLE turnos_app"))
            app.execute(
                text("SELECT set_config('app.tenant_id', :tenant, false)"),
                {"tenant": tenant},
            )
            with pytest.raises(DBAPIError):
                app.execute(
                    text("UPDATE auditoria SET accion = 'ALTERADO' WHERE tenant_id = :t"),
                    {"t": tenant},
                )
            app.rollback()

        with engine.connect() as app:
            app.execute(text("SET ROLE turnos_app"))
            app.execute(
                text("SELECT set_config('app.tenant_id', :tenant, false)"),
                {"tenant": tenant},
            )
            with pytest.raises(DBAPIError):
                app.execute(
                    text("DELETE FROM auditoria WHERE tenant_id = :t"), {"t": tenant}
                )
            app.rollback()

        # La entrada original sigue intacta.
        with engine.connect() as owner:
            accion = owner.execute(
                text("SELECT accion FROM auditoria WHERE tenant_id = :t"),
                {"t": tenant},
            ).scalar_one()
        assert accion == "MOVIMIENTO_CAJA_REGISTRADO"
    finally:
        with engine.connect() as owner:
            tx = owner.begin()
            owner.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant})
            tx.commit()
        engine.dispose()
