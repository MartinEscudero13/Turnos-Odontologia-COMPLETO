"""Tasks 2.2–2.11 — dominio de caja: alta de movimientos (TDD rojo primero).

Reglas verificadas:
- `medio` ∈ {EFECTIVO, TRANSFERENCIA, MP, OS} y `tipo` ∈ {INGRESO, EGRESO}.
- `monto` entero positivo en centavos: 0, negativo, float y string son `422`.
- `fecha` es día operativo `YYYY-MM-DD`; sin fecha se usa el reloj en `-03:00`
  (C10-OQ-8), por eso `2026-11-11T01:30:00Z` es `2026-11-10`.
- Un `turno_id` de otro tenant responde `404` y no persiste.
- El alta toma el advisory lock del día antes de insertar (D14).
- No existe `PATCH` ni `DELETE` de movimientos.
"""
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from _caja_helpers import TUR1, TUR9, U1, HarnessCaja, actor, d3
from conftest import T1, T2
from fastapi.testclient import TestClient

from app.caja.puertos import UnidadDeTrabajoMemoria
from app.routers.caja import crear_app
from app.turnos.servicio import Invalido, NoEncontrado

RECEP = {"X-Tenant-Id": T1, "X-User-Id": U1, "X-Rol": "RECEPCION"}


def test_registrar_ingreso_efectivo() -> None:
    h = HarnessCaja()
    mov = h.registrar(monto=150000, medio="EFECTIVO", fecha="2026-11-10", turno_id=TUR1)

    assert mov.tenant_id == T1
    assert mov.fecha == date(2026, 11, 10)
    assert mov.medio == "EFECTIVO"
    assert mov.monto == 150000
    assert mov.tipo == "INGRESO"
    assert mov.usuario_id == U1
    assert mov.turno_id == TUR1
    assert mov.anulado is False
    assert mov.origen == "MANUAL"
    assert mov.tramo is None
    assert h.movimientos.listar_por_fecha(tenant_id=T1, fecha=date(2026, 11, 10)) == [mov]
    # D14: el lock del día se toma antes de insertar.
    assert h.uow.bloqueos_dia == [(T1, date(2026, 11, 10))]
    # Auditoría append-only con ids y montos, sin PHI.
    assert [e.accion for e in h.auditoria.entradas] == ["MOVIMIENTO_CAJA_REGISTRADO"]
    entrada = h.auditoria.entradas[0]
    assert entrada.entidad_id == mov.id
    assert entrada.despues is not None
    assert entrada.despues["monto"] == 150000
    assert "nombre" not in entrada.despues


def test_registrar_egreso() -> None:
    h = HarnessCaja()
    egreso = h.registrar(monto=20000, medio="TRANSFERENCIA", tipo="EGRESO", fecha="2026-11-10")

    assert egreso.tipo == "EGRESO"
    assert egreso.medio == "TRANSFERENCIA"
    assert h.movimientos.totales_por_medio(tenant_id=T1, fecha=date(2026, 11, 10))[
        "TRANSFERENCIA"
    ] == -20000
    # Un ingreso del mismo medio compensa parcialmente el neto.
    h.registrar(monto=5000, medio="TRANSFERENCIA", fecha="2026-11-10")
    assert h.movimientos.totales_por_medio(tenant_id=T1, fecha=date(2026, 11, 10))[
        "TRANSFERENCIA"
    ] == -15000


def test_cuatro_medios_validos() -> None:
    h = HarnessCaja()
    montos = {"EFECTIVO": 150000, "TRANSFERENCIA": 30000, "MP": 20000, "OS": 40000}
    for medio, monto in montos.items():
        h.registrar(monto=monto, medio=medio, fecha="2026-11-10")

    movimientos = h.movimientos.listar_por_fecha(tenant_id=T1, fecha=date(2026, 11, 10))
    assert {(m.medio, m.monto) for m in movimientos} == set(montos.items())
    totales = h.movimientos.totales_por_medio(tenant_id=T1, fecha=date(2026, 11, 10))
    assert totales == montos
    assert set(totales) == {"EFECTIVO", "TRANSFERENCIA", "MP", "OS"}


def test_monto_invalido_422() -> None:
    h = HarnessCaja()
    for invalido in (0, -100, 1000.5, "1000", True):
        with pytest.raises(Invalido) as excinfo:
            h.registrar(monto=invalido, medio="EFECTIVO", fecha="2026-11-10")
        assert excinfo.value.codigo == 422
    assert h.movimientos.total(T1) == 0
    # El mínimo válido es 1 centavo.
    assert h.registrar(monto=1, medio="EFECTIVO", fecha="2026-11-10").monto == 1


def test_medio_o_tipo_invalido_422() -> None:
    h = HarnessCaja()
    for campo, valor in (("medio", "CHEQUE"), ("medio", ""), ("tipo", "AJUSTE"), ("tipo", None)):
        kwargs: dict[str, object] = {"monto": 1000, "medio": "EFECTIVO", "fecha": "2026-11-10"}
        kwargs[campo] = valor
        with pytest.raises(Invalido) as excinfo:
            h.registrar(**kwargs)  # type: ignore[arg-type]
        assert excinfo.value.codigo == 422
    assert h.movimientos.total(T1) == 0


def test_fecha_mal_formada_422() -> None:
    h = HarnessCaja()
    for invalida in ("10/11/2026", "2026-11-10T10:00:00-03:00", "2026-13-01", "", 20261110):
        with pytest.raises(Invalido) as excinfo:
            h.registrar(monto=1000, medio="EFECTIVO", fecha=invalida)
        assert excinfo.value.codigo == 422
    assert h.movimientos.total(T1) == 0
    # El borde HTTP también rechaza el instante: la fecha es un día operativo.
    client = TestClient(crear_app(h.svc))
    for invalida_http in ("10/11/2026", "2026-11-10T10:00:00-03:00"):
        respuesta = client.post(
            "/api/caja/movimientos",
            json={"monto": 1000, "medio": "EFECTIVO", "fecha": invalida_http},
            headers=RECEP,
        )
        assert respuesta.status_code == 422
    assert h.movimientos.total(T1) == 0


def test_sin_fecha_usa_reloj_servidor() -> None:
    h = HarnessCaja()
    h.ahora = d3("2026-11-10", hora=22)
    mov = h.registrar(monto=1000, medio="EFECTIVO", fecha=None)
    assert mov.fecha == date(2026, 11, 10)
    # A las 00:30 del -03:00 ya es otro día operativo.
    h.ahora = d3("2026-11-11", hora=0, minuto=30)
    assert h.registrar(monto=1000, medio="EFECTIVO", fecha=None).fecha == date(2026, 11, 11)


def test_lock_del_dia_antes_de_insertar() -> None:
    """D14: el advisory lock se toma antes de insertar el movimiento."""
    h = HarnessCaja()

    class UowConOrden(UnidadDeTrabajoMemoria):
        def __init__(self) -> None:
            super().__init__(
                [
                    h.movimientos,
                    h.cierres,
                    h.pendientes,
                    h.ajustes,
                    h.cuentas,
                    h.auditoria,
                ],
                h.movimientos,
            )
            self.movimientos_al_bloquear = -1

        def bloquear_dia(self, *, tenant_id: str, fecha: date) -> None:
            self.movimientos_al_bloquear = h.movimientos.total(tenant_id)
            super().bloquear_dia(tenant_id=tenant_id, fecha=fecha)

    h.cablear_uow(UowConOrden)
    h.registrar(monto=1000, medio="EFECTIVO", fecha="2026-11-10")
    assert getattr(h.uow, "movimientos_al_bloquear", None) == 0
    assert h.movimientos.total(T1) == 1


def test_dia_operativo_offset_menos_03() -> None:
    h = HarnessCaja()
    # 2026-11-11T01:30:00Z = 2026-11-10T22:30 en -03:00 (C10-OQ-8).
    h.ahora = datetime(2026, 11, 11, 1, 30, tzinfo=UTC)
    assert h.registrar(monto=1000, medio="EFECTIVO", fecha=None).fecha == date(2026, 11, 10)
    # 03:00:00Z ya es el 2026-11-11 en -03:00.
    h.ahora = datetime(2026, 11, 11, 3, 0, tzinfo=UTC)
    assert h.registrar(monto=1000, medio="EFECTIVO", fecha=None).fecha == date(2026, 11, 11)


def test_turno_otro_tenant_404() -> None:
    h = HarnessCaja()
    with pytest.raises(NoEncontrado) as excinfo:
        h.registrar(monto=150000, medio="EFECTIVO", fecha="2026-11-10", turno_id=TUR9)
    assert excinfo.value.codigo == 404
    assert h.movimientos.total(T1) == 0
    # El turno de T2 sí se puede asociar desde el actor de T2.
    mov = h.registrar(
        monto=150000,
        medio="EFECTIVO",
        fecha="2026-11-10",
        turno_id=TUR9,
        actor_=actor(tenant=T2),
    )
    assert mov.turno_id == TUR9
    assert h.movimientos.total(T2) == 1


def test_movimiento_sin_patch_ni_delete() -> None:
    h = HarnessCaja()
    client = TestClient(crear_app(h.svc))

    alta = client.post(
        "/api/caja/movimientos",
        json={"monto": 150000, "medio": "EFECTIVO", "fecha": "2026-11-10"},
        headers=RECEP,
    )
    assert alta.status_code == 201
    mov_id = alta.json()["id"]

    patch = client.patch(
        f"/api/caja/movimientos/{mov_id}", json={"monto": 1}, headers=RECEP
    )
    delete = client.delete(f"/api/caja/movimientos/{mov_id}", headers=RECEP)
    patch_coleccion = client.patch(
        "/api/caja/movimientos", json={"monto": 1}, headers=RECEP
    )
    for respuesta in (patch, delete, patch_coleccion):
        assert respuesta.status_code in (405, 403, 404)
        assert respuesta.status_code != 200

    intacto = client.get(f"/api/caja/movimientos/{mov_id}", headers=RECEP)
    assert intacto.status_code == 200
    assert intacto.json()["monto"] == 150000
    assert intacto.json()["anulado"] is False
