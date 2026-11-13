"""Router FastAPI de odontograma — C-09 (§7, backend-only, inyectable).

Mapea el dominio a HTTP: `201` al registrar o derivar la primera vez, `200` al
replay idempotente o al resolver, `404` cross-tenant, `403` RBAC, `409` gate de
consentimiento / doble resolución / key reutilizada, `422` payload inválido y
`401` cuando la petición trae identidad de paciente (v1 no tiene sesión de
paciente). No existe `PATCH` ni `DELETE`: el contenido clínico es inmutable (D2).

El actor se resuelve por headers (`actor_desde_headers`) igual que C-05/C-07/C-08.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Header, Request, Response
from fastapi.responses import JSONResponse

from app.odontograma.puertos import Hallazgo
from app.odontograma.servicio import Derivacion, ServicioOdontograma
from app.routers.turnos import actor_desde_headers
from app.schemas.odontograma import DerivacionOut, HallazgoIn, HallazgoOut
from app.schemas.turno import ErrorOut
from app.turnos.servicio import Actor, TurnoError


def _hallazgo_out(h: Hallazgo) -> HallazgoOut:
    return HallazgoOut(
        id=h.id,
        paciente_id=h.paciente_id,
        pieza_fdi=h.pieza_fdi,
        superficie=h.superficie,
        hallazgo=h.hallazgo,
        fecha=h.fecha,
        profesional_id=h.profesional_id,
        resuelto=h.resuelto,
        creado_en=h.creado_en,
    )


def _derivacion_out(d: Derivacion) -> DerivacionOut:
    return DerivacionOut(
        hallazgo_id=d.hallazgo.id, linea_id=d.linea.id, creada=d.creada
    )


def _error_body(exc: TurnoError) -> dict[str, object]:
    return ErrorOut(detalle=exc.mensaje).model_dump(mode="json")


def crear_router(svc: ServicioOdontograma) -> APIRouter:
    """Router de odontograma inyectando el servicio (testeable sin DB)."""
    r = APIRouter()

    @r.post(
        "/api/odontograma",
        status_code=201,
        response_model=HallazgoOut | DerivacionOut,
    )
    def registrar(
        body: HallazgoIn,
        response: Response,
        actor: Actor = Depends(actor_desde_headers),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> HallazgoOut | DerivacionOut:
        if body.derivar is None:
            return _hallazgo_out(
                svc.registrar_hallazgo(
                    actor,
                    paciente_id=body.paciente_id,
                    pieza_fdi=body.pieza_fdi,
                    superficie=body.superficie,
                    hallazgo=body.hallazgo,
                    fecha=body.fecha,
                    profesional_id=body.profesional_id,
                )
            )
        resultado = svc.derivar(
            actor,
            paciente_id=body.paciente_id,
            pieza_fdi=body.pieza_fdi,
            superficie=body.superficie,
            hallazgo=body.hallazgo,
            fecha=body.fecha,
            profesional_id=body.profesional_id,
            prestacion_id=body.derivar.prestacion_id,
            monto=body.derivar.monto,
            idempotency_key=idempotency_key,
        )
        if not resultado.creada:
            # Replay del mismo payload ⇒ 200 con los mismos ids (D3.1).
            response.status_code = 200
        return _derivacion_out(resultado)

    @r.get("/api/odontograma", response_model=list[HallazgoOut])
    def historial(
        paciente_id: str,
        pieza_fdi: int | None = None,
        actor: Actor = Depends(actor_desde_headers),
    ) -> list[HallazgoOut]:
        return [
            _hallazgo_out(h)
            for h in svc.listar_historial(
                actor, paciente_id=paciente_id, pieza_fdi=pieza_fdi
            )
        ]

    @r.post("/api/odontograma/{hallazgo_id}/resolver", response_model=HallazgoOut)
    def resolver(
        hallazgo_id: str, actor: Actor = Depends(actor_desde_headers)
    ) -> HallazgoOut:
        return _hallazgo_out(svc.resolver(actor, hallazgo_id=hallazgo_id))

    return r


def crear_app(svc: ServicioOdontograma) -> FastAPI:
    """App mínima del change (patrón `crear_app` de C-05/C-06/C-07/C-08)."""
    app = FastAPI(title="Turnos-Odontologia C-09 odontograma")

    @app.exception_handler(TurnoError)
    async def _turno_error(_request: Request, exc: TurnoError) -> JSONResponse:
        return JSONResponse(status_code=exc.codigo, content=_error_body(exc))

    app.include_router(crear_router(svc))
    return app
