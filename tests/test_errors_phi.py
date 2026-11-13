"""Exception handling contract: no PHI and no internals in error payloads."""
from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import http_exception_response, unexpected_response
from app.middleware import RequestIdMiddleware


def test_unexpected_exception_returns_generic_contract() -> None:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("patient alice@example.test phone +5491100000000")

    @app.exception_handler(Exception)
    async def handler(request, exc: Exception):  # type: ignore[override]
        return unexpected_response(exc, request)

    response = TestClient(app, raise_server_exceptions=False).get(
        "/boom", headers={"X-Correlation-ID": "corr-boom"}
    )
    assert response.status_code == 500
    payload = response.json()
    assert payload["error"]["code"] == "INTERNAL_ERROR"
    assert payload["error"]["correlation_id"] == "corr-boom"
    assert "alice@example.test" not in response.text
    assert "+5491100000000" not in response.text
    assert "RuntimeError" not in response.text


def test_http_exception_keeps_known_message_but_correlation() -> None:
    from fastapi import HTTPException
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/guarded")
    def guarded() -> None:
        raise HTTPException(status_code=403, detail="No autorizado")

    @app.exception_handler(HTTPException)
    async def handler(request, exc: HTTPException):  # type: ignore[override]
        return http_exception_response(exc, request)

    response = TestClient(app).get("/guarded")
    assert response.status_code == 403
    assert response.json()["error"]["correlation_id"] != "-"
    assert response.json()["error"]["code"] == "FORBIDDEN"


# ---------------------------------------------------------------------------
# 11.13 — un error de seña no vuelca PHI
# ---------------------------------------------------------------------------


def test_error_de_sena_sin_phi(caplog: pytest.LogCaptureFixture) -> None:
    """El error de dominio y el log llevan sólo código, `sena_id`, tenant y monto.

    El caso elegido tiene el dato personal **en la mano** del dominio: la seña es
    de "Paciente Demo", el guard de presupuesto de C-09 lo consulta y la
    aplicación se rechaza con `409 PRESUPUESTO_CON_SENA`. Ni la respuesta ni el
    log estructurado pueden nombrarlo (RN-CL-04, design D15).
    """
    from _senas_helpers import T1, U1, HarnessSenaAplicacion

    h = HarnessSenaAplicacion()
    sena = h.sembrar_sena(estado="ACREDITADA", paciente_id="Paciente Demo")
    h.presupuestos.marcar(tenant_id=T1, paciente_id="Paciente Demo")

    with caplog.at_level(logging.WARNING, logger="app.senas.aplicacion"):
        response = h.client_interno.post(
            f"/api/senas/{sena.id}/aplicar",
            json={"concepto": "TRATAMIENTO"},
            headers={"X-Tenant-Id": T1, "X-User-Id": U1, "X-Rol": "RECEPCION"},
        )

    # THEN el body es la allow-list del error: código y detalle, sin PHI.
    assert response.status_code == 409, response.text
    assert set(response.json()) == {"detalle", "codigo"}
    assert response.json()["codigo"] == "PRESUPUESTO_CON_SENA"
    assert "Paciente Demo" not in response.text
    assert "+5491100000000" not in response.text

    # AND el log lleva sólo código, sena_id, tenant_id y monto.
    registros = [
        registro
        for registro in caplog.records
        if registro.name == "app.senas.aplicacion"
    ]
    assert registros, "falta el log estructurado del rechazo"
    registro = registros[-1]
    assert registro.codigo == "PRESUPUESTO_CON_SENA"
    assert registro.sena_id == sena.id
    assert registro.tenant_id == T1
    assert registro.monto_centavos == 3000
    assert "Paciente Demo" not in registro.getMessage()
    assert "Paciente Demo" not in repr(getattr(registro, "__dict__", {}))
    assert "+5491100000000" not in caplog.text


def test_log_del_webhook_sin_phi(caplog: pytest.LogCaptureFixture) -> None:
    """El webhook que sí tiene el turno en la mano tampoco loguea al paciente.

    Acreditar exige leer el turno (`turno_de`), y esa vista trae `paciente_id`:
    el log estructurado sólo puede llevar ids de seña/pago/pasarela, nunca el
    paciente ni su nombre (RN-CL-04, D15).
    """
    from _senas_helpers import T1, HarnessSenaCiclo

    h = HarnessSenaCiclo()
    sena = h.sembrar_sena(paciente_id="Paciente Demo")

    with caplog.at_level(logging.INFO, logger="app.senas.webhook"):
        respuesta = h.notificar(sena=sena, mp_payment_id="PAG-1")

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["resultado"] == "ACREDITADA"
    assert "Paciente Demo" not in caplog.text
    assert "Paciente Demo" not in respuesta.text
    assert "+5491100000000" not in caplog.text
    # El log del camino feliz nombra la seña y el pago, no el paciente.
    registro = [
        r for r in caplog.records if r.name == "app.senas.webhook"
    ][-1]
    assert sena.id in registro.getMessage()
    assert "PAG-1" in registro.getMessage()
    assert T1 in registro.getMessage()


def test_log_del_request_no_incluye_el_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """El token del link público viaja en el path: el log no lo copia.

    Limitación conocida y fuera de este change: el *access log* del servidor HTTP
    (uvicorn/gunicorn) puede registrar la URL cruda; su redacción es de
    infraestructura. Lo que C-11 garantiza es el log estructurado de la
    aplicación (`app.http`), que sí pasa por acá.
    """
    from app.middleware import ruta_para_log

    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/api/publico/{token_tenant}/senas/{token}")
    def leer_sena(token_tenant: str, token: str) -> dict[str, str]:
        # El token se recibe como path param en la ruta real; acá sólo importa
        # que el middleware no lo copie al log.
        del token
        return {"tenant": token_tenant}

    with caplog.at_level(logging.INFO, logger="app.http"):
        response = TestClient(app).get("/api/publico/t1/senas/TOK-S-secreto")

    assert response.status_code == 200
    registro = [r for r in caplog.records if r.name == "app.http"][-1]
    assert registro.path == "/api/publico/t1/senas/[REDACTED]"
    assert "TOK-S-secreto" not in caplog.text
    # La ruta interna de la seña no cambia y el path público sin token tampoco.
    assert ruta_para_log("/api/senas/123") == "/api/senas/123"
    assert ruta_para_log("/api/publico/t1/senas") == "/api/publico/t1/senas"
    assert (
        ruta_para_log("/api/publico/t1/senas/TOK/preferencia")
        == "/api/publico/t1/senas/[REDACTED]/preferencia"
    )
