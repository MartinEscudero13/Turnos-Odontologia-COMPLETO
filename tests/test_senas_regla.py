"""Tasks 2.1–2.7 — regla efectiva de la seña (PO-01 / RN-SE-05): RED primero.

La regla es `prestacion.sena_modo ?? tenant_parametros['sena_modo']`, con
`SIN_SENA` como override válido, `SIN_SENA` cuando no hay configuración y
**fail-open a no cobrar** cuando la configuración almacenada es inválida. El
monto se trunca hacia abajo al centavo (`precio_base * valor // 100`, C11-OQ-01).

`tenant_parametros` es clave/valor (D1): la regla se lee de un `Mapping`, no de
columnas nuevas. Datos ficticios (RN-GL-03); ningún test toca red ni base.

Los escenarios 2.4–2.6 de `tasks.md` también exigen que la reserva responda
`201`, pero eso es el enganche de §4 (`reserva-publica`); acá se verifica el
contrato que lo habilita: `ReglaSena.exige_sena is False`.
"""
from __future__ import annotations

import logging
from typing import Any

import pytest
from conftest import T1

from app.senas.regla import CODIGO_REGLA_INVALIDA, PrestacionSena, resolver_regla

TENANT_PORCENTAJE: dict[str, object] = {"sena_modo": "PORCENTAJE", "sena_valor": 30}


def prestacion(**overrides: object) -> PrestacionSena:
    datos: dict[str, Any] = {
        "id": "prestacion-1",
        "precio_base_centavos": 10000,
        "sena_modo": None,
        "sena_valor": None,
    }
    datos.update(overrides)
    return PrestacionSena(**datos)


def parametros(**overrides: object) -> dict[str, object]:
    datos = dict(TENANT_PORCENTAJE)
    datos.update(overrides)
    return datos


def invalidas(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [
        registro
        for registro in caplog.records
        if getattr(registro, "codigo", None) == CODIGO_REGLA_INVALIDA
    ]


# ---------------------------------------------------------------------------
# 2.1 — el override de la prestación gana al default del tenant
# ---------------------------------------------------------------------------


def test_override_monto_fijo_gana_al_tenant(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="app.senas.regla")

    regla = resolver_regla(
        tenant_id=T1,
        prestacion=prestacion(sena_modo="MONTO_FIJO", sena_valor=5000),
        parametros=parametros(),
    )

    assert regla.modo == "MONTO_FIJO"
    assert regla.valor == 5000
    assert regla.monto_centavos == 5000
    assert regla.exige_sena is True
    assert invalidas(caplog) == []


# ---------------------------------------------------------------------------
# 2.2 — SIN_SENA es un override válido
# ---------------------------------------------------------------------------


def test_sin_sena_es_override_valido(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="app.senas.regla")

    regla = resolver_regla(
        tenant_id=T1,
        prestacion=prestacion(sena_modo="SIN_SENA"),
        parametros=parametros(),
    )

    assert regla.modo == "SIN_SENA"
    assert regla.valor is None
    assert regla.monto_centavos == 0
    assert regla.exige_sena is False
    # Un override explícito de no cobrar no es una configuración inválida.
    assert invalidas(caplog) == []


# ---------------------------------------------------------------------------
# 2.3 — sin override la prestación hereda el default del tenant
# ---------------------------------------------------------------------------


def test_herencia_del_tenant_porcentaje() -> None:
    regla = resolver_regla(
        tenant_id=T1,
        prestacion=prestacion(precio_base_centavos=10000),
        parametros=parametros(),
    )

    assert regla.modo == "PORCENTAJE"
    assert regla.valor == 30
    assert regla.precio_base_centavos == 10000
    assert regla.monto_centavos == 3000
    assert regla.exige_sena is True


# ---------------------------------------------------------------------------
# 2.4 — sin configuración en ningún nivel no se cobra
# ---------------------------------------------------------------------------


def test_sin_configuracion_no_cobra(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="app.senas.regla")

    regla = resolver_regla(
        tenant_id=T1,
        prestacion=prestacion(),
        parametros={},
    )

    assert regla.modo == "SIN_SENA"
    assert regla.monto_centavos == 0
    assert regla.exige_sena is False
    # Ausencia de configuración no es inválida: no se ensucia el log.
    assert invalidas(caplog) == []


# ---------------------------------------------------------------------------
# 2.5 — una configuración inválida no rompe nada: fail-open a no cobrar
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("configuracion", "motivo"),
    [
        ({"sena_modo": "MITAD", "sena_valor": 50}, "modo_desconocido"),
        ({"sena_modo": "PORCENTAJE", "sena_valor": 0}, "valor_fuera_de_rango"),
        ({"sena_modo": "PORCENTAJE", "sena_valor": 101}, "valor_fuera_de_rango"),
        ({"sena_modo": "PORCENTAJE"}, "valor_faltante"),
        ({"sena_modo": "MONTO_FIJO", "sena_valor": 0}, "valor_fuera_de_rango"),
    ],
)
def test_configuracion_invalida_fail_open(
    caplog: pytest.LogCaptureFixture,
    configuracion: dict[str, object],
    motivo: str,
) -> None:
    caplog.set_level(logging.WARNING, logger="app.senas.regla")

    regla = resolver_regla(
        tenant_id=T1,
        prestacion=prestacion(),
        parametros=configuracion,
    )

    # Fail-open: nunca se cobra un monto inventado ni se rompe la reserva.
    assert regla.modo == "SIN_SENA"
    assert regla.monto_centavos == 0
    assert regla.exige_sena is False
    assert regla.motivo_invalidez == motivo

    registros = invalidas(caplog)
    assert len(registros) == 1
    registro = registros[0]
    assert registro.codigo == CODIGO_REGLA_INVALIDA
    assert registro.tenant_id == T1
    assert registro.prestacion_id == "prestacion-1"
    assert registro.motivo == motivo
    # RN-CL-04: ni el mensaje ni los campos llevan datos del paciente.
    assert "paciente" not in registro.getMessage().lower()


# ---------------------------------------------------------------------------
# 2.6 — un monto calculado en cero no genera seña
# ---------------------------------------------------------------------------


def test_monto_cero_no_genera_sena(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="app.senas.regla")

    regla = resolver_regla(
        tenant_id=T1,
        prestacion=prestacion(precio_base_centavos=0),
        parametros=parametros(),
    )

    # La regla es válida (PORCENTAJE 30) pero el monto da 0: no hay seña.
    assert regla.modo == "PORCENTAJE"
    assert regla.monto_centavos == 0
    assert regla.exige_sena is False
    assert invalidas(caplog) == []


# ---------------------------------------------------------------------------
# 2.7 — truncar al centavo, nunca redondear para arriba (C11-OQ-01)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("precio_base", "porcentaje", "esperado"),
    [
        (10000, 33, 3300),
        (333, 50, 166),
        (1, 50, 0),
    ],
)
def test_truncado_al_centavo(precio_base: int, porcentaje: int, esperado: int) -> None:
    regla = resolver_regla(
        tenant_id=T1,
        prestacion=prestacion(precio_base_centavos=precio_base),
        parametros=parametros(sena_valor=porcentaje),
    )

    assert regla.monto_centavos == esperado
    assert regla.monto_centavos != esperado + 1


def test_truncado_no_redondea_166_a_167() -> None:
    regla = resolver_regla(
        tenant_id=T1,
        prestacion=prestacion(precio_base_centavos=333),
        parametros=parametros(sena_valor=50),
    )

    assert regla.monto_centavos == 166
    assert regla.monto_centavos != 167
