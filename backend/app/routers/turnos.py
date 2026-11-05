"""Router FastAPI de turnos — C-05 (tasks 3.1–3.4).

Mapea el dominio a HTTP: 201 crear, 409 + 3 alternativas ante solape,
422 payload/transición, 403 RBAC/anticipación, 404 cross-tenant.

Autenticación: el actor llega por headers (`X-Tenant-Id`, `X-User-Id`,
`X-Rol`, `X-Profesional-Id` opcional) SOLO como sostén standalone del
change. El JWT real (access + refresh + RBAC C-03) llega en C-03 y
reemplaza esta dependencia sin cambiar el contrato del router.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.lista_espera.puertos import HuecoLiberadoPort
from app.schemas.turno import (
    ActualizarTurnoIn,
    AlternativaOut,
    CrearTurnoIn,
    ErrorOut,
    MotivoIn,
    ReprogramarIn,
    TurnoOut,
)
from app.turnos.servicio import (
    Actor,
    ConflictoSolape,
    Rol,
    ServicioTurnos,
    Turno,
    TurnoError,
)

ROLES: tuple[str, ...] = ("PACIENTE", "ODONTOLOGO", "RECEPCION", "ADMIN")


def actor_desde_headers(
    x_tenant_id: str = Header(),
    x_user_id: str = Header(),
    x_rol: str = Header(),
    x_profesional_id: str | None = Header(default=None),
) -> Actor:
    """Dependencia provisoria de actor (JWT en C-03)."""
    if x_rol not in ROLES:
        raise HTTPException(status_code=422, detail=f"rol inválido: {x_rol}")
    rol: Rol = x_rol  # type: ignore[assignment]
    return Actor(
        tenant_id=x_tenant_id, rol=rol, user_id=x_user_id, profesional_id=x_profesional_id
    )


def _error_body(exc: TurnoError) -> dict[str, object]:
    alts = exc.alternativas if isinstance(exc, ConflictoSolape) else []
    return ErrorOut(
        detalle=exc.mensaje,
        alternativas=[AlternativaOut(inicio=a.inicio, fin=a.fin) for a in alts],
    ).model_dump(mode="json")


def crear_router(svc: ServicioTurnos, hueco_port: HuecoLiberadoPort | None = None) -> APIRouter:
    """Router de turnos inyectando el servicio (testeable sin DB)."""
    r = APIRouter()

    @r.post("/api/turnos", status_code=201, response_model=TurnoOut)
    def crear(body: CrearTurnoIn, actor: Actor = Depends(actor_desde_headers)) -> Turno:
        return svc.crear(
            actor,
            profesional_id=body.profesional_id,
            sillon_id=body.sillon_id,
            paciente_id=body.paciente_id,
            prestacion_id=body.prestacion_id,
            inicio=body.inicio,
            duracion_min=body.duracion_min,
            fin_cliente=body.fin_cliente,
            sobreturno=body.sobreturno,
            motivo_sobreturno=body.motivo_sobreturno,
            origen=body.origen,
        )

    @r.get("/api/turnos", response_model=list[TurnoOut])
    def listar(actor: Actor = Depends(actor_desde_headers)) -> list[Turno]:
        return svc.listar(actor)

    @r.get("/api/turnos/{turno_id}", response_model=TurnoOut)
    def obtener(turno_id: str, actor: Actor = Depends(actor_desde_headers)) -> Turno:
        return svc.obtener(actor, turno_id)

    @r.patch("/api/turnos/{turno_id}", response_model=TurnoOut)
    def actualizar(
        turno_id: str, body: ActualizarTurnoIn, actor: Actor = Depends(actor_desde_headers)
    ) -> Turno:
        return svc.actualizar(actor, turno_id, paciente_id=body.paciente_id)

    @r.post("/api/turnos/{turno_id}/sobreturno", response_model=TurnoOut)
    def sobreturno(
        turno_id: str, body: MotivoIn, actor: Actor = Depends(actor_desde_headers)
    ) -> Turno:
        return svc.sobreturno(actor, turno_id, motivo=body.motivo)

    @r.post("/api/turnos/{turno_id}/cancelar", response_model=TurnoOut)
    def cancelar(turno_id: str, actor: Actor = Depends(actor_desde_headers)) -> Turno:
        turno = svc.cancelar(actor, turno_id)
        if hueco_port is not None:
            hueco_port.emitir(tenant_id=actor.tenant_id, turno_id=turno_id)
        return turno

    @r.post("/api/turnos/{turno_id}/reprogramar")
    def reprogramar(
        turno_id: str, body: ReprogramarIn, actor: Actor = Depends(actor_desde_headers)
    ) -> dict[str, object]:
        res = svc.reprogramar(
            actor, turno_id, nuevo_inicio=body.nuevo_inicio, duracion_min=body.duracion_min
        )
        if hueco_port is not None:
            hueco_port.emitir(tenant_id=actor.tenant_id, turno_id=turno_id)
        return {
            "original": TurnoOut.model_validate(res.original, from_attributes=True).model_dump(
                mode="json"
            ),
            "nuevo": TurnoOut.model_validate(res.nuevo, from_attributes=True).model_dump(mode="json"),
        }

    return r


def crear_app(
    svc: ServicioTurnos | None = None, hueco_port: HuecoLiberadoPort | None = None
) -> FastAPI:
    """App mínima del change (adelanto parcial de C-01, no entrega C-01)."""
    app = FastAPI(title="Turnos-Odontologia C-05")
    servicio = svc if svc is not None else ServicioTurnos()

    @app.exception_handler(TurnoError)
    async def _turno_error(_request: Request, exc: TurnoError) -> JSONResponse:
        return JSONResponse(status_code=exc.codigo, content=_error_body(exc))

    app.include_router(crear_router(servicio, hueco_port))
    return app
