"""Tasks 3.1–3.10 — derivación atómica hallazgo → línea de presupuesto.

Dominio puro con adaptadores en memoria y datos ficticios ("Conducto Demo" con
`precio_base=150000` centavos). La garantía de concurrencia real (3.11) vive en
`test_derivacion_concurrente_pg.py` y se salta sin PostgreSQL.
"""
from __future__ import annotations

import pytest
from _odontograma_helpers import (
    KEY,
    PAC1,
    PAC9,
    PREST1,
    PREST9,
    HarnessOdontograma,
    actor,
    d3,
)
from conftest import P1, T1, T2

from app.ficha_clinica.servicio import Conflicto
from app.odontograma.puertos import UnidadDeTrabajoMemoria
from app.turnos.servicio import Invalido, NoEncontrado


def _derivar(
    h: HarnessOdontograma,
    *,
    pieza_fdi: object = 36,
    hallazgo: str = "caries oclusal",
    prestacion_id: str = PREST1,
    monto: int | None = None,
    idempotency_key: str | None = KEY,
):
    return h.svc.derivar(
        actor("ODONTOLOGO", profesional_id=P1),
        paciente_id=PAC1,
        pieza_fdi=pieza_fdi,
        hallazgo=hallazgo,
        fecha=d3(),
        prestacion_id=prestacion_id,
        monto=monto,
        idempotency_key=idempotency_key,
    )


# ---------------------------------------------------------------------------
# 3.1 / 3.2 — línea creada desde el hallazgo
# ---------------------------------------------------------------------------


def test_derivar_crea_hallazgo_y_linea_en_un_paso():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    resultado = _derivar(h)
    assert resultado.creada is True
    assert resultado.hallazgo.pieza_fdi == 36
    assert resultado.linea.pieza_fdi == 36
    assert resultado.linea.hallazgo_id == resultado.hallazgo.id
    assert resultado.linea.prestacion_id == PREST1
    assert resultado.linea.monto == 150000
    assert resultado.linea.cobertura_os == 0
    assert resultado.linea.a_cargo_paciente == 150000
    assert resultado.linea.origen_cobertura == "SIN_COBERTURA"
    assert resultado.linea.validada_en_vivo is False
    assert h.hallazgos.total(T1) == 1
    assert h.lineas.total(T1) == 1
    assert h.presupuestos.total(T1) == 1
    presupuesto = h.presupuestos.obtener(
        tenant_id=T1, presupuesto_id=resultado.linea.presupuesto_id
    )
    assert presupuesto is not None and presupuesto.estado == "BORRADOR"


def test_monto_explicito_reemplaza_precio_base():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    resultado = _derivar(h, monto=120000)
    assert resultado.linea.monto == 120000
    assert resultado.linea.a_cargo_paciente == 120000


def test_monto_cero_es_valido():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    resultado = _derivar(h, monto=0)
    assert resultado.linea.monto == 0
    assert resultado.linea.a_cargo_paciente == 0
    assert h.lineas.total(T1) == 1


# ---------------------------------------------------------------------------
# 3.3 / 3.4 — abortos sin persistir el hallazgo
# ---------------------------------------------------------------------------


def test_prestacion_inexistente_aborta_y_no_persiste_hallazgo():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    with pytest.raises(NoEncontrado) as exc:
        _derivar(h, prestacion_id=PREST9)
    assert exc.value.codigo == 404
    assert h.hallazgos.total(T1) == 0
    assert h.lineas.total(T1) == 0
    assert h.presupuestos.total(T1) == 0


def test_monto_negativo_aborta_y_no_persiste_hallazgo():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    with pytest.raises(Invalido) as exc:
        _derivar(h, monto=-1)
    assert exc.value.codigo == 422
    assert h.hallazgos.total(T1) == 0
    assert h.lineas.total(T1) == 0


# ---------------------------------------------------------------------------
# 3.5 — rollback de la unidad de trabajo
# ---------------------------------------------------------------------------


def test_fallo_de_unidad_de_trabajo_hace_rollback():
    h = HarnessOdontograma()
    uow = UnidadDeTrabajoMemoria([h.hallazgos, h.presupuestos, h.lineas])
    with pytest.raises(RuntimeError):  # noqa: SIM117 - la excepción debe verla el uow
        with uow:
            hallazgo = h.hallazgos.registrar(
                tenant_id=T1,
                paciente_id=PAC1,
                pieza_fdi=36,
                superficie=None,
                hallazgo="caries oclusal",
                fecha=d3(),
                profesional_id=P1,
            )
            presupuesto = h.presupuestos.crear(
                tenant_id=T1, paciente_id=PAC1, ahora=d3()
            )
            h.lineas.agregar(
                tenant_id=T1,
                presupuesto_id=presupuesto.id,
                prestacion_id=PREST1,
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
            raise RuntimeError("falla de la unidad de trabajo")
    assert h.hallazgos.total(T1) == 0
    assert h.presupuestos.total(T1) == 0
    assert h.lineas.total(T1) == 0


# ---------------------------------------------------------------------------
# 3.6 → 3.9 — idempotencia de la derivación
# ---------------------------------------------------------------------------


def test_primera_derivacion_con_key_201():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    resultado = _derivar(h)
    assert resultado.creada is True
    assert resultado.hallazgo.id
    assert resultado.linea.id
    assert h.hallazgos.total(T1) == 1
    assert h.lineas.total(T1) == 1


def test_replay_misma_key_mismo_payload_200_mismos_ids():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    primera = _derivar(h)
    replay = _derivar(h)
    assert primera.creada is True
    assert replay.creada is False
    assert replay.hallazgo.id == primera.hallazgo.id
    assert replay.linea.id == primera.linea.id
    assert h.hallazgos.total(T1) == 1
    assert h.lineas.total(T1) == 1
    # Los campos que completa el servidor no rompen el replay: el cliente
    # repite exactamente el mismo payload y la comparación los ignora.
    assert replay.linea.idempotency_key == KEY
    assert replay.linea.hallazgo_id == primera.hallazgo.id


def test_misma_key_payload_distinto_409():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    primera = _derivar(h)
    for cambio in ({"pieza_fdi": 37}, {"monto": 120000}, {"hallazgo": "otro texto"}):
        with pytest.raises(Conflicto) as exc:
            _derivar(h, **cambio)
        assert exc.value.codigo == 409
    assert h.hallazgos.total(T1) == 1
    assert h.lineas.total(T1) == 1
    persistida = h.lineas.por_idempotency_key(tenant_id=T1, idempotency_key=KEY)
    assert persistida is not None and persistida.id == primera.linea.id
    assert persistida.monto == 150000


def test_idempotency_key_ausente_o_invalida_422():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    for key in (None, "", "no-es-un-uuid", "12345"):
        with pytest.raises(Invalido) as exc:
            _derivar(h, idempotency_key=key)
        assert exc.value.codigo == 422
    assert h.hallazgos.total(T1) == 0
    assert h.lineas.total(T1) == 0


def test_misma_key_en_otro_tenant_es_independiente():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    h.seed_paciente(PAC9, tenant=T2)
    h.seed_profesional(P1, tenant=T2)
    h.seed_atiende(P1, PAC9, tenant=T2)
    h.seed_prestacion(PREST1, 150000, tenant=T2)
    h.dar_consentimiento(PAC9, tenant=T2)
    t1 = _derivar(h)
    t2 = h.svc.derivar(
        actor("ODONTOLOGO", tenant=T2, profesional_id=P1),
        paciente_id=PAC9,
        pieza_fdi=36,
        hallazgo="caries oclusal",
        fecha=d3(),
        prestacion_id=PREST1,
        idempotency_key=KEY,
    )
    assert t1.creada is True and t2.creada is True
    assert t1.linea.id != t2.linea.id
    assert h.lineas.total(T1) == 1
    assert h.lineas.total(T2) == 1
    assert h.lineas.por_idempotency_key(
        tenant_id=T1, idempotency_key=KEY
    ).id == t1.linea.id
    assert h.lineas.por_idempotency_key(
        tenant_id=T2, idempotency_key=KEY
    ).id == t2.linea.id
