"""Tasks 5.1–5.2 — contrato del puerto de C-09 visto desde C-10.

El adaptador de caja implementa `ImputacionPort` **sin cambiar la firma** (D6) y
reutiliza `MedioPago` importado de `app.presupuesto.puertos` (M11): no hay un
`Literal` propio en `app.caja`. Se comparan nombres, orden, tipo de parámetro
(todos keyword-only, sin defaults) y anotaciones reales, no sólo strings.
"""
from __future__ import annotations

import inspect
import re
from datetime import date
from pathlib import Path
from typing import Literal, get_args, get_origin, get_type_hints

from _caja_helpers import LINEA1, PAC1, PRESU1, U1, HarnessCaja
from conftest import T1

import app.caja.puertos as caja_puertos
import app.caja.servicio as caja_servicio
from app.caja.adaptador_imputacion import AdaptadorCaja
from app.presupuesto.puertos import ImputacionPort, MedioPago

PARAMETROS = (
    "tenant_id",
    "presupuesto_id",
    "linea_id",
    "paciente_id",
    "prestacion_id",
    "monto_paciente_centavos",
    "monto_os_centavos",
    "actor_id",
    "turno_id",
    "medio",
)
CAJA = Path(__file__).resolve().parents[1] / "backend" / "app" / "caja"
FECHA = date(2026, 11, 10)


def _firma(metodo: object) -> list[tuple[str, object, object]]:
    """Nombre, tipo de parámetro y default de cada argumento (sin `self`)."""
    return [
        (parametro.name, parametro.kind, parametro.default)
        for nombre, parametro in inspect.signature(metodo).parameters.items()  # type: ignore[arg-type]
        if nombre != "self"
    ]


def _llamada(**cambios: object) -> dict[str, object]:
    """Argumentos válidos de `imputar_caja` para el harness de caja."""
    base: dict[str, object] = {
        "tenant_id": T1,
        "presupuesto_id": PRESU1,
        "linea_id": LINEA1,
        "paciente_id": PAC1,
        "prestacion_id": "prestacion-1",
        "monto_paciente_centavos": 60000,
        "monto_os_centavos": 0,
        "actor_id": U1,
        "turno_id": None,
        "medio": "EFECTIVO",
    }
    base.update(cambios)
    return base


# ---------------------------------------------------------------------------
# 5.1 — la firma del adaptador es la de C-09 (todos keyword-only)
# ---------------------------------------------------------------------------


def test_firma_del_puerto_es_la_de_c09() -> None:
    protocolo = {
        nombre: parametro
        for nombre, parametro in inspect.signature(ImputacionPort.imputar_caja).parameters.items()
        if nombre != "self"
    }
    adaptador = inspect.signature(AdaptadorCaja.imputar_caja).parameters
    sin_self = [nombre for nombre in adaptador if nombre != "self"]

    # Mismos nombres y **mismo orden** que el protocolo de C-09.
    assert tuple(sin_self) == PARAMETROS
    assert tuple(protocolo) == PARAMETROS

    # Ninguno se puede pasar por posición: el contrato es keyword-only y sin
    # default explícito (el llamador de C-09 siempre pasa todos).
    for nombre in PARAMETROS:
        assert adaptador[nombre].kind is inspect.Parameter.KEYWORD_ONLY, nombre
        assert protocolo[nombre].kind is inspect.Parameter.KEYWORD_ONLY, nombre
        assert adaptador[nombre].default is inspect.Parameter.empty, nombre
        assert protocolo[nombre].default is inspect.Parameter.empty, nombre

    # El adaptador satisface el protocolo completo, `imputar_agenda` incluido.
    assert _firma(AdaptadorCaja.imputar_caja) == _firma(ImputacionPort.imputar_caja)
    assert _firma(AdaptadorCaja.imputar_agenda) == _firma(ImputacionPort.imputar_agenda)

    # `imputar_agenda` es no-op y no crea turnos (M10): no escribe caja, no
    # deja auditoría y el tenant no gana ningún turno.
    h = HarnessCaja()
    turnos_antes = h.turnos.total(T1)
    assert (
        h.adaptador.imputar_agenda(
            tenant_id=T1,
            presupuesto_id=PRESU1,
            linea_id=LINEA1,
            paciente_id=PAC1,
            prestacion_id="prestacion-1",
            monto_centavos=100000,
        )
        is None
    )
    assert h.movimientos.listar_por_fecha(tenant_id=T1, fecha=FECHA) == []
    assert h.pendientes.listar(tenant_id=T1) == []
    assert h.cuentas.total(T1) == 0
    assert h.auditoria.de_tenant(T1) == []
    assert h.turnos.total(T1) == turnos_antes


# ---------------------------------------------------------------------------
# 5.2 — `MedioPago` se importa, no se redeclara (M11)
# ---------------------------------------------------------------------------


def test_medio_pago_se_importa_no_se_redeclara() -> None:
    # Identidad: el objeto que usa `app.caja` es el de C-09, no una copia.
    assert caja_puertos.MedioPago is MedioPago
    assert caja_servicio.MedioPago is MedioPago

    # Y es exactamente el `Literal` de los cuatro medios de RN-CJ-01.
    assert get_origin(MedioPago) is Literal
    assert get_args(MedioPago) == ("EFECTIVO", "TRANSFERENCIA", "MP", "OS")

    # La anotación real del parámetro `medio` coincide con la del protocolo y
    # es `MedioPago | None`, no otro `Literal` equivalente.
    anotacion_adaptador = get_type_hints(AdaptadorCaja.imputar_caja)["medio"]
    anotacion_protocolo = get_type_hints(ImputacionPort.imputar_caja)["medio"]
    assert anotacion_adaptador == anotacion_protocolo
    assert get_args(anotacion_adaptador) == (MedioPago, type(None))

    # Cero `Literal` propio con valores de medio en todo `app.caja` (M11).
    propio = re.compile(r"Literal\[\s*[\"'](?:EFECTIVO|TRANSFERENCIA|MP|OS)[\"']")
    for archivo in sorted(CAJA.glob("*.py")):
        codigo = archivo.read_text(encoding="utf-8")
        assert not propio.search(codigo), f"{archivo.name} redeclara el Literal de medio"

    # El adaptador acepta el valor importado y lo persiste tal cual.
    h = HarnessCaja()
    assert h.adaptador.imputar_caja(**_llamada(medio=MedioPago.__args__[0])) is None  # type: ignore[attr-defined]
    creados = h.movimientos.listar_por_fecha(tenant_id=T1, fecha=FECHA)
    assert len(creados) == 1
    assert creados[0].medio == "EFECTIVO"
