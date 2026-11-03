"""Exception handling contract: no PHI and no internals in error payloads."""
from __future__ import annotations

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
