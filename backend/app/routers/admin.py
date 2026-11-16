"""Router FastAPI del admin del tenant — C-15."""
from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Response

from app.admin.puertos import Kpis, UsuarioAdmin
from app.admin.servicio import ServicioAdmin
from app.routers.turnos import actor_desde_headers
from app.schemas.admin import (
    ConfigIn,
    KpisOut,
    UsuarioEstadoIn,
    UsuarioIn,
    UsuarioOut,
)
from app.turnos.servicio import Actor

__all__ = ["crear_router"]


def _usuario_out(usuario: UsuarioAdmin) -> UsuarioOut:
    return UsuarioOut(
        id=usuario.id,
        nombre=usuario.nombre,
        email=usuario.email,
        rol=usuario.rol,
        activo=usuario.activo,
        creado_en=usuario.creado_en,
    )


def _kpis_out(kpis: Kpis) -> KpisOut:
    return KpisOut(
        desde=kpis.desde.isoformat(),
        hasta=kpis.hasta.isoformat(),
        total_turnos=kpis.total_turnos,
        turnos_por_estado=kpis.turnos_por_estado,
        ausentismo_pct=kpis.ausentismo_pct,
        reservas_online_pct=kpis.reservas_online_pct,
        facturacion_por_profesional=[
            (profesional, total) for profesional, total in kpis.facturacion_por_profesional
        ],
        reasignados_2h=kpis.reasignados_2h,
        ocupacion_pct=kpis.ocupacion_pct,
    )


def crear_router(svc: ServicioAdmin) -> APIRouter:
    r = APIRouter()

    # -- configuración --------------------------------------------------
    @r.get("/api/tenant/config", response_model=dict[str, Any])
    def obtener_config(actor: Actor = Depends(actor_desde_headers)) -> dict[str, Any]:
        return svc.obtener_config(actor)

    @r.put("/api/tenant/config", response_model=dict[str, Any])
    def actualizar_config(
        body: ConfigIn, actor: Actor = Depends(actor_desde_headers)
    ) -> dict[str, Any]:
        return svc.actualizar_config(actor, valores=body.model_dump(exclude_unset=True))

    # -- usuarios -------------------------------------------------------
    @r.get("/api/tenant/usuarios", response_model=list[UsuarioOut])
    def listar_usuarios(actor: Actor = Depends(actor_desde_headers)) -> list[UsuarioOut]:
        return [_usuario_out(usuario) for usuario in svc.listar_usuarios(actor)]

    @r.post("/api/tenant/usuarios", status_code=201, response_model=UsuarioOut)
    def crear_usuario(
        body: UsuarioIn, actor: Actor = Depends(actor_desde_headers)
    ) -> UsuarioOut:
        return _usuario_out(
            svc.crear_usuario(
                actor,
                nombre=body.nombre,
                email=body.email,
                password=body.password,
                rol=body.rol,
            )
        )

    @r.patch("/api/tenant/usuarios/{usuario_id}", response_model=UsuarioOut)
    def cambiar_estado(
        usuario_id: str,
        body: UsuarioEstadoIn,
        actor: Actor = Depends(actor_desde_headers),
    ) -> UsuarioOut:
        return _usuario_out(
            svc.cambiar_estado_usuario(actor, usuario_id=usuario_id, activo=body.activo)
        )

    # -- exportación ----------------------------------------------------
    @r.get("/api/exportacion")
    def exportar(
        formato: str = "json", actor: Actor = Depends(actor_desde_headers)
    ) -> Response:
        media_type, contenido = svc.exportar(actor, formato=formato)
        extension = "json" if media_type == "application/json" else "csv"
        return Response(
            content=contenido,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="export-tenant.{extension}"'
            },
        )

    # -- KPIs -----------------------------------------------------------
    @r.get("/api/reportes/kpis", response_model=KpisOut)
    def kpis(
        desde: date,
        hasta: date,
        actor: Actor = Depends(actor_desde_headers),
    ) -> KpisOut:
        return _kpis_out(svc.kpis(actor, desde=desde, hasta=hasta))

    return r
