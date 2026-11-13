"""Tasks 7.1–7.10 — expiración de la seña y auto-oferta (RN-SE-01 / RN-RE-04).

Reloj `2026-11-14T09:00:00-03:00` igual a `expira_at`: la seña se libera, el
turno se cancela con motivo `SENA_NO_ACREDITADA` y se emite **el mismo** evento de
hueco liberado que usa C-06 (C-07 hace la oferta; C-11 no la reimplementa).

La atomicidad del release se prueba con la unidad de trabajo en memoria: si el
puerto de hueco falla, no queda ninguna escritura parcial y el próximo barrido
toma la seña (F-14). La versión con locks reales vive en `test_sena_carreras_pg`.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from _senas_helpers import AHORA, TUR1, TUR2, HarnessSenaCiclo, d3
from conftest import T1, T2

from app.senas.puertos import UnidadDeTrabajoMemoria
from app.senas.runner import JOB_EXPIRACIONES
from app.senas.worker import ServicioSenasExpulsion

VENCIMIENTO = d3("2026-11-14", 9)


class HuecoEspia:
    """Espía del `HuecoLiberadoPort` de C-06/C-07: registra y puede fallar."""

    def __init__(self, *, falla: bool = False) -> None:
        self.llamadas: list[tuple[str, str]] = []
        self._falla = falla

    def emitir(self, *, tenant_id: str, turno_id: str) -> None:
        if self._falla:
            raise RuntimeError("el puerto de hueco liberado falló")
        self.llamadas.append((tenant_id, turno_id))


class VencidasObservadas:
    """Delegador del repositorio que registra el tenant de cada barrido."""

    def __init__(self, real: object) -> None:
        self._real = real
        self.tenants: list[str] = []

    def vencidas(self, *, tenant_id: str, ahora: object) -> list[object]:
        self.tenants.append(tenant_id)
        return self._real.vencidas(tenant_id=tenant_id, ahora=ahora)  # type: ignore[attr-defined]

    def bloquear(self, **kwargs: object) -> object:
        return self._real.bloquear(**kwargs)  # type: ignore[attr-defined]

    def transicionar(self, **kwargs: object) -> object:
        return self._real.transicionar(**kwargs)  # type: ignore[attr-defined]


def _worker(h: HarnessSenaCiclo, huecos: object) -> ServicioSenasExpulsion:
    return ServicioSenasExpulsion(
        h.senas,
        h.turnos,
        huecos,  # type: ignore[arg-type]
        h.auditoria,
        reloj=lambda: h.ahora,
        uow_factory=lambda: UnidadDeTrabajoMemoria(h.senas, h.turnos, h.auditoria),
    )


def test_expira_libera_y_emite_auto_oferta() -> None:
    """7.1 — seña vencida: LIBERADA + turno CANCELADO + evento de hueco."""
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena(expira_at=VENCIMIENTO)
    h.ahora = VENCIMIENTO

    liberadas = h.worker.procesar_expiraciones(tenant_id=T1, ahora=h.ahora)

    assert [s.id for s in liberadas] == [sena.id]
    actual = h.sena(sena)
    assert actual.estado == "LIBERADA"
    assert actual.motivo_liberacion == "EXPIRACION"
    assert actual.liberada_en == VENCIMIENTO
    turno = h.turnos.turno_de(tenant_id=T1, turno_id=TUR1)
    assert turno is not None and turno.estado == "CANCELADO"
    assert h.eventos_hueco() == [(T1, TUR1)]
    entradas = h.auditoria.de_accion("SENA_LIBERADA")
    assert len(entradas) == 1
    assert entradas[0].despues is not None
    assert entradas[0].despues["motivo_liberacion"] == "EXPIRACION"
    assert entradas[0].despues["auto_oferta_emitida"] is True


def test_no_expira_antes() -> None:
    """7.2 — una seña vigente no se libera ni toca el turno."""
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena(expira_at=VENCIMIENTO)

    liberadas = h.worker.procesar_expiraciones(tenant_id=T1, ahora=AHORA)

    assert liberadas == []
    assert h.sena(sena).estado == "PENDIENTE"
    turno = h.turnos.turno_de(tenant_id=T1, turno_id=TUR1)
    assert turno is not None and turno.estado == "PENDIENTE"
    assert h.eventos_hueco() == []


def test_segunda_corrida_no_duplica() -> None:
    """7.3 — el segundo barrido no transiciona, no emite y no rompe."""
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena(expira_at=VENCIMIENTO)
    h.ahora = VENCIMIENTO
    h.worker.procesar_expiraciones(tenant_id=T1, ahora=h.ahora)

    segunda = h.worker.procesar_expiraciones(tenant_id=T1, ahora=h.ahora)

    assert segunda == []
    assert h.sena(sena).estado == "LIBERADA"
    assert len(h.eventos_hueco()) == 1
    assert len(h.auditoria.de_accion("SENA_LIBERADA")) == 1


def test_turno_ya_cancelado_libera_igual() -> None:
    """7.4 — turno cancelado por otro canal: la seña se libera sin segundo evento."""
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena(expira_at=VENCIMIENTO, turno_estado="CANCELADO")
    # C-06 ya emitió el hueco al cancelar el turno.
    h.huecos.emitir(tenant_id=T1, turno_id=TUR1)
    h.ahora = VENCIMIENTO

    liberadas = h.worker.procesar_expiraciones(tenant_id=T1, ahora=h.ahora)

    assert [s.id for s in liberadas] == [sena.id]
    assert h.sena(sena).estado == "LIBERADA"
    turno = h.turnos.turno_de(tenant_id=T1, turno_id=TUR1)
    assert turno is not None and turno.estado == "CANCELADO"
    assert h.eventos_hueco() == [(T1, TUR1)]  # uno solo: el de C-06


def test_pago_tardio_no_reabre() -> None:
    """7.5 — pago aprobado después de liberar: DEVUELTA y el hueco sigue retenido."""
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena(expira_at=VENCIMIENTO)
    h.ahora = VENCIMIENTO
    h.worker.procesar_expiraciones(tenant_id=T1, ahora=h.ahora)
    assert h.eventos_hueco() == [(T1, TUR1)]

    respuesta = h.notificar(sena=sena, mp_payment_id="PAG-TARDE")

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["resultado"] == "FUERA_DE_TIEMPO"
    actual = h.sena(sena)
    assert actual.estado == "DEVUELTA"
    assert actual.motivo_devolucion == "PAGO_FUERA_DE_TIEMPO"
    # El turno sigue cancelado y el hueco no se reabre ni se reemite (C11-OQ-07).
    turno = h.turnos.turno_de(tenant_id=T1, turno_id=TUR1)
    assert turno is not None and turno.estado == "CANCELADO"
    assert h.eventos_hueco() == [(T1, TUR1)]


def test_reloj_inyectado() -> None:
    """7.6 — dos relojes distintos, dos resultados; sin dormir."""
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena(expira_at=VENCIMIENTO)

    antes = h.worker.procesar_expiraciones(tenant_id=T1, ahora=VENCIMIENTO - timedelta(seconds=1))
    despues = h.worker.procesar_expiraciones(tenant_id=T1, ahora=VENCIMIENTO)

    assert antes == []
    assert [s.id for s in despues] == [sena.id]
    assert h.sena(sena).liberada_en == VENCIMIENTO


def test_emite_el_mismo_puerto_que_c06() -> None:
    """7.7 — el espía recibe exactamente `(tenant_id, turno_id)`; no hay oferta acá."""
    h = HarnessSenaCiclo()
    h.sembrar_sena(expira_at=VENCIMIENTO)
    espia = HuecoEspia()
    h.ahora = VENCIMIENTO

    _worker(h, espia).procesar_expiraciones(tenant_id=T1, ahora=h.ahora)

    assert espia.llamadas == [(T1, TUR1)]
    # C-11 sólo emite el evento: la oferta la crea `ServicioAutoOferta` (C-07).
    assert h.eventos_hueco() == []


def test_fallo_al_emitir_hace_rollback() -> None:
    """7.8 — si falla la emisión del hueco no queda escritura parcial (F-14)."""
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena(expira_at=VENCIMIENTO)
    h.ahora = VENCIMIENTO

    with pytest.raises(RuntimeError):
        _worker(h, HuecoEspia(falla=True)).procesar_expiraciones(
            tenant_id=T1, ahora=h.ahora
        )

    assert h.sena(sena).estado == "PENDIENTE"
    turno = h.turnos.turno_de(tenant_id=T1, turno_id=TUR1)
    assert turno is not None and turno.estado == "PENDIENTE"
    assert h.auditoria.de_accion("SENA_LIBERADA") == []

    # El próximo barrido la vuelve a tomar y libera.
    liberadas = h.worker.procesar_expiraciones(tenant_id=T1, ahora=h.ahora)
    assert [s.id for s in liberadas] == [sena.id]
    assert h.sena(sena).estado == "LIBERADA"


def test_runner_registrado() -> None:
    """7.9 — el job queda registrado y una seña vencida se libera al ejecutarlo."""
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena(expira_at=VENCIMIENTO)
    h.ahora = VENCIMIENTO

    nombre = h.runner.registrar()

    assert nombre == JOB_EXPIRACIONES
    assert h.registro.nombres() == (JOB_EXPIRACIONES,)
    assert h.runner.intervalo_s == 60
    h.registro.ejecutar(JOB_EXPIRACIONES)
    assert h.sena(sena).estado == "LIBERADA"
    assert h.eventos_hueco() == [(T1, TUR1)]


def test_barrido_de_t1_no_toca_t2() -> None:
    """7.10 — el barrido de T1 no libera la seña vencida de T2 (F-20)."""
    h = HarnessSenaCiclo(inicio=d3("2026-11-20", 10))
    de_t1 = h.sembrar_sena(tenant_id=T1, turno_id=TUR1, expira_at=VENCIMIENTO)
    de_t2 = h.sembrar_sena(
        tenant_id=T2, turno_id=TUR2, expira_at=VENCIMIENTO, inicio=d3("2026-11-20", 11)
    )
    h.ahora = VENCIMIENTO

    espia = VencidasObservadas(h.senas)
    worker = ServicioSenasExpulsion(
        espia,  # type: ignore[arg-type]
        h.turnos,
        h.huecos,
        h.auditoria,
        reloj=lambda: h.ahora,
        uow_factory=lambda: UnidadDeTrabajoMemoria(h.senas, h.turnos, h.auditoria),
    )
    liberadas = worker.procesar_expiraciones(tenant_id=T1, ahora=h.ahora)

    assert [s.id for s in liberadas] == [de_t1.id]
    # El dominio pide siempre el barrido con un tenant explícito: nunca global.
    assert espia.tenants == [T1]
    assert h.sena(de_t1).estado == "LIBERADA"
    assert h.sena(de_t2).estado == "PENDIENTE"
    turno_t2 = h.turnos.turno_de(tenant_id=T2, turno_id=TUR2)
    assert turno_t2 is not None and turno_t2.estado == "PENDIENTE"
    assert h.eventos_hueco() == [(T1, TUR1)]
