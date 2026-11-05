"""Router FastAPI de lista de espera — C-07 (gestión interna + aceptación pública).

Gestión (`/api/lista-espera`) resuelve el actor por headers (recepción/admin) igual
que C-05. Aceptación (`/api/publico/{token_tenant}/ofertas/{token}/aceptar`) resuelve
el tenant por el path público, como C-06. Errores de dominio → `TurnoError` mapeado
a `{detalle, alternativas}` sin trazas.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.lista_espera.puertos import Entrada
from app.lista_espera.servicio import ServicioListaEspera
from app.lista_espera.worker import ServicioAutoOferta
from app.reservas.puertos import TenantPort
from app.routers.turnos import actor_desde_headers
from app.schemas.lista_espera import (
    AltaListaEsperaIn,
    EntradaListaEsperaOut,
    OfertaAceptadaOut,
)
from app.schemas.turno import ErrorOut
from app.turnos.servicio import Actor, NoEncontrado, TurnoError


def _entrada_out(e: Entrada) -> EntradaListaEsperaOut:
    return EntradaListaEsperaOut(
        id=e.id,
        paciente_id=e.paciente_id,
        prestacion_id=e.prestacion_id,
        profesional_pref=e.profesional_pref,
        ventana_desde=e.ventana_desde,
        ventana_hasta=e.ventana_hasta,
        estado=e.estado,
        creado_en=e.creado_en,
    )


def _error_body(exc: TurnoError) -> dict[str, object]:
    return ErrorOut(detalle=exc.mensaje).model_dump(mode="json")


def crear_router(
    svc_lista: ServicioListaEspera,
    svc_ofertas: ServicioAutoOferta,
    tenants: TenantPort,
) -> APIRouter:
    r = APIRouter()

    @r.post("/api/lista-espera", status_code=201, response_model=EntradaListaEsperaOut)
    def alta(body: AltaListaEsperaIn, actor: Actor = Depends(actor_desde_headers)) -> EntradaListaEsperaOut:
        entrada = svc_lista.alta(
            actor,
            paciente_id=body.paciente_id,
            prestacion_id=body.prestacion_id,
            profesional_pref=body.profesional_pref,
            ventana_desde=body.ventana_desde,
            ventana_hasta=body.ventana_hasta,
        )
        return _entrada_out(entrada)

    @r.get("/api/lista-espera", response_model=list[EntradaListaEsperaOut])
    def listar(
        prestacion_id: str | None = None,
        profesional_id: str | None = None,
        actor: Actor = Depends(actor_desde_headers),
    ) -> list[EntradaListaEsperaOut]:
        return [
            _entrada_out(e)
            for e in svc_lista.listar(
                actor, prestacion_id=prestacion_id, profesional_id=profesional_id
            )
        ]

    @r.delete("/api/lista-espera/{entrada_id}", status_code=204)
    def baja(entrada_id: str, actor: Actor = Depends(actor_desde_headers)) -> Response:
        svc_lista.baja(actor, entrada_id=entrada_id)
        return Response(status_code=204)

    @r.post(
        "/api/publico/{token_tenant}/ofertas/{token}/aceptar",
        status_code=201,
        response_model=OfertaAceptadaOut,
    )
    def aceptar(token_tenant: str, token: str) -> OfertaAceptadaOut:
        tenant_id = tenants.resolver(token_tenant)
        if tenant_id is None:
            raise NoEncontrado("oferta no encontrada")
        turno = svc_ofertas.aceptar(tenant_id, token)
        return OfertaAceptadaOut(
            turno_id=turno.id,
            estado=turno.estado,
            inicio=turno.inicio,
            fin=turno.fin,
            origen=turno.origen,
            prestacion=turno.prestacion_id,
            sillon_id=turno.sillon_id,
        )

    return r


def crear_app(
    svc_lista: ServicioListaEspera,
    svc_ofertas: ServicioAutoOferta,
    tenants: TenantPort,
) -> FastAPI:
    """App mínima del change (patrón `crear_app` de C-05/C-06)."""
    app = FastAPI(title="Turnos-Odontologia C-07 lista de espera")

    @app.exception_handler(TurnoError)
    async def _turno_error(_request: Request, exc: TurnoError) -> JSONResponse:
        return JSONResponse(status_code=exc.codigo, content=_error_body(exc))

    app.include_router(crear_router(svc_lista, svc_ofertas, tenants))
    return app
