"""Task 3.15 — dos anulaciones simultáneas del mismo movimiento contra PostgreSQL.

Esta prueba **no se simula con adaptadores en memoria**: la garantía de "una sola
transición `vigente → anulado`" (D2/D14) depende del advisory lock real por
`(tenant, fecha)` y de la transacción, no de un chequeo previo en el mismo
proceso. Se salta sin `C02_DATABASE_URL`.

Alcance honesto: el wiring SQLAlchemy de los repositorios de caja es un
follow-up declarado (igual que C-06…C-09), así que acá se ejercita la garantía de
base que sostiene el `200`/`409`: dos conexiones independientes toman el lock del
día, la primera anula y escribe compensatorio + ajuste dentro de su transacción,
y la segunda —bloqueada en el lock— revalida después del commit, ve el
movimiento ya anulado, responde `409` y no escribe nada. El mapeo de esa
revalidación a `200`/`409` está cubierto en el dominio por
`tests/test_anulacion_caja.py` (3.3) y el cierre intacto por 3.9.
"""
from __future__ import annotations

import threading
import time
from datetime import timedelta

from _caja_pg import (
    AHORA,
    BLOQUEAR_DIA,
    FECHA_CERRADA,
    FECHA_REGISTRO,
    MONTO,
    anular_y_compensar,
    limpiar,
    motor,
    requiere_pg,
    sembrar_anulacion,
)
from sqlalchemy import text

pytestmark = requiere_pg

MOTIVO = "error de carga"
ESPERA_MAXIMA = 20


def test_dos_anulaciones_dejan_un_compensatorio() -> None:
    engine = motor()
    ids: dict[str, str] = {}
    try:
        with engine.connect() as owner:
            tx = owner.begin()
            ids = sembrar_anulacion(owner)
            tx.commit()

        listo = threading.Event()
        commit_hecho = threading.Event()
        resultados: dict[str, str] = {}

        def primera_anulacion() -> None:
            with engine.connect() as conn:
                tx = conn.begin()
                resultados["primera"] = anular_y_compensar(
                    conn, ids, motivo=MOTIVO, actor=ids["usuario"]
                )
                # La transacción queda abierta con el lock del día tomado.
                listo.set()
                time.sleep(0.3)
                # Se marca antes del commit: la otra conexión sólo puede salir
                # del lock cuando este commit libere la transacción.
                commit_hecho.set()
                tx.commit()

        def segunda_anulacion() -> None:
            assert listo.wait(timeout=ESPERA_MAXIMA)
            with engine.connect() as conn:
                tx = conn.begin()
                conn.execute(text("SET LOCAL statement_timeout = '5000'"))
                try:
                    # Bloquea hasta que la primera transacción libere el lock.
                    conn.execute(
                        BLOQUEAR_DIA, {"t": ids["tenant"], "f": FECHA_CERRADA}
                    )
                    resultados["segunda_tras_commit"] = (
                        "si" if commit_hecho.is_set() else "no"
                    )
                    resultados["segunda"] = anular_y_compensar(
                        conn, ids, motivo="otro motivo", actor=ids["usuario"]
                    )
                except Exception:  # el escenario prohíbe un 500
                    resultados["segunda"] = "500"
                finally:
                    tx.rollback()

        hilos = [
            threading.Thread(target=primera_anulacion, daemon=True),
            threading.Thread(target=segunda_anulacion, daemon=True),
        ]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=ESPERA_MAXIMA)
            assert not hilo.is_alive()

        # Una `200`, una `409`, ninguna `500` y la segunda esperó al commit real.
        assert resultados == {
            "primera": "200",
            "segunda": "409",
            "segunda_tras_commit": "si",
        }

        with engine.connect() as owner:
            compensatorios = owner.execute(
                text(
                    "SELECT fecha, tipo, monto, medio, origen, compensa_a_id"
                    " FROM movimientos_caja"
                    " WHERE tenant_id = :t AND origen = 'COMPENSACION'"
                ),
                {"t": ids["tenant"]},
            ).all()
            assert len(compensatorios) == 1
            fecha, tipo, monto, medio, origen, compensa = compensatorios[0]
            assert fecha == FECHA_REGISTRO
            assert tipo == "EGRESO"
            assert monto == MONTO
            assert medio == "EFECTIVO"
            assert origen == "COMPENSACION"
            assert str(compensa) == ids["movimiento"]

            ajustes = owner.execute(
                text(
                    "SELECT tipo, cierre_id, monto, motivo"
                    " FROM ajustes_post_cierre"
                    " WHERE tenant_id = :t AND movimiento_original_id = :mov"
                ),
                {"t": ids["tenant"], "mov": ids["movimiento"]},
            ).all()
            assert len(ajustes) == 1
            tipo_ajuste, cierre_id, monto_ajuste, motivo = ajustes[0]
            assert tipo_ajuste == "AJUSTE_ANULACION"
            assert str(cierre_id) == ids["cierre"]
            assert monto_ajuste == MONTO
            assert motivo == MOTIVO

            # El original quedó anulado una sola vez (con el motivo del ganador)
            # y el día cerrado no recibió movimientos nuevos.
            original = owner.execute(
                text(
                    "SELECT anulado, motivo_anulacion, anulado_por, anulado_en"
                    " FROM movimientos_caja WHERE tenant_id = :t AND id = :mov"
                ),
                {"t": ids["tenant"], "mov": ids["movimiento"]},
            ).one()
            assert original[0] is True
            assert original[1] == MOTIVO
            assert str(original[2]) == ids["usuario"]
            assert original[3] == AHORA
            del_dia_cerrado = owner.execute(
                text(
                    "SELECT count(*) FROM movimientos_caja"
                    " WHERE tenant_id = :t AND fecha = :f"
                ),
                {"t": ids["tenant"], "f": FECHA_CERRADA},
            ).scalar_one()
            assert del_dia_cerrado == 1

            # El cierre conserva exactamente sus totales: nadie lo recalculó.
            cierre = owner.execute(
                text(
                    "SELECT total_efectivo, total_transferencia, total_mp,"
                    " total_os_cobrado, total_os, efectivo_contado, diferencia, cerrado_at"
                    " FROM cierres_diarios WHERE tenant_id = :t AND id = :c"
                ),
                {"t": ids["tenant"], "c": ids["cierre"]},
            ).one()
            assert cierre[:7] == (MONTO, 0, 0, 0, 0, MONTO, 0)
            assert cierre[7] == AHORA - timedelta(days=1)
    finally:
        limpiar(engine, ids)
