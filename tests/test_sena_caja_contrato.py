"""Task 9.7 — contrato del adaptador con el alta de C-10 (`C10-OQ-6`, F-13).

La seña **no** escribe caja: delega en `ServicioCaja.registrar_movimiento`, que
es la única puerta del hecho de caja. Este test fija la firma real (si el
adaptador inventara argumentos, el `TypeError` sería el rojo), el día operativo
de la aplicación en `-03:00` y la propagación de los errores de C-10 (`404` de
turno ajeno y `409 CIERRE_CERRADO`).

La transacción compartida (`TransaccionSQL(session)` anidable) se verifica en
`tests/test_sena_carreras_pg.py::test_aplicar_vs_cierre` con dos conexiones
reales: ahí el movimiento y la seña commitean o revierten juntos.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from _senas_helpers import T1, TUR1, U1, HarnessSenaAplicacion

from app.caja.servicio import ConflictoCaja, ServicioCaja
from app.senas.adaptadores import AplicacionCajaServicio
from app.turnos.servicio import NoEncontrado


class CajaEspia(ServicioCaja):
    """`ServicioCaja` real que registra la llamada antes de delegar.

    Heredar del servicio real prueba la firma: si el adaptador pasara un
    argumento que C-10 no acepta, el test explotaría en el `super()`.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.llamadas: list[dict[str, Any]] = []

    def registrar_movimiento(self, actor: Any, **kwargs: Any) -> Any:
        self.llamadas.append({"actor": actor, **kwargs})
        return super().registrar_movimiento(actor, **kwargs)


def _espia(h: HarnessSenaAplicacion) -> CajaEspia:
    return CajaEspia(
        h.movimientos,
        h.cierres,
        h.pendientes,
        h.ajustes,
        h.cuentas,
        h.caja_turnos,
        h.auditoria_caja,
        usuarios=h.caja_usuarios,
        uow_factory=h.uow_caja,
        reloj=lambda: h.ahora,
    )


def test_contrato_con_el_alta_de_c10() -> None:
    h = HarnessSenaAplicacion()
    espia = _espia(h)
    adaptador = AplicacionCajaServicio(espia)

    movimiento = adaptador.registrar_ingreso_mp(
        tenant_id=T1,
        turno_id=TUR1,
        monto_centavos=3000,
        fecha=date(2026, 11, 13),
        actor_id=U1,
        concepto="TRATAMIENTO",
    )

    # Firma real: el alta de C-10 se llamó con los argumentos del contrato.
    assert len(espia.llamadas) == 1
    llamada = espia.llamadas[0]
    assert llamada["monto"] == 3000
    assert llamada["medio"] == "MP"
    assert llamada["tipo"] == "INGRESO"
    assert llamada["fecha"] == date(2026, 11, 13)  # día de la aplicación (F-13)
    assert llamada["turno_id"] == TUR1
    assert llamada["actor"].tenant_id == T1
    assert llamada["actor"].user_id == U1

    assert movimiento.medio == "MP"
    assert movimiento.monto_centavos == 3000
    assert movimiento.fecha == date(2026, 11, 13)
    # El movimiento es un alta normal de C-10 (no un origen nuevo de C-11).
    assert movimiento.turno_id == TUR1

    # `404`: el turno no pertenece al tenant.
    with pytest.raises(NoEncontrado):
        adaptador.registrar_ingreso_mp(
            tenant_id=T1,
            turno_id="turno-ajeno",
            monto_centavos=3000,
            fecha=date(2026, 11, 13),
            actor_id=U1,
            concepto="TRATAMIENTO",
        )

    # `409 CIERRE_CERRADO`: lo decide C-10, C-11 sólo lo propaga.
    h.cerrar_dia(date(2026, 11, 13))
    with pytest.raises(ConflictoCaja) as excinfo:
        adaptador.registrar_ingreso_mp(
            tenant_id=T1,
            turno_id=TUR1,
            monto_centavos=3000,
            fecha=date(2026, 11, 13),
            actor_id=U1,
            concepto="TRATAMIENTO",
        )
    assert excinfo.value.codigo == 409
    assert excinfo.value.codigo_dominio == "CIERRE_CERRADO"
