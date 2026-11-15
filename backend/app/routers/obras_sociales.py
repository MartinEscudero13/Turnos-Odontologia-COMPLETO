"""Router FastAPI de obras sociales y liquidación — C-12.

RBAC: configuración sólo `ADMIN`; lectura y liquidaciones `ADMIN`/`RECEPCION`.
Los errores de dominio los mapea la app que hospeda el router (handler global de
`TurnoError` en `create_app`).
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Response

from app.obras_sociales.puertos import Cobertura, Liquidacion, ObraSocial, TramoCobertura
from app.obras_sociales.servicio import ServicioObrasSociales
from app.routers.turnos import actor_desde_headers
from app.schemas.obras_sociales import (
    CoberturaIn,
    CoberturaOut,
    EstadoObraSocialIn,
    LineaLiquidacionOut,
    LiquidacionIn,
    LiquidacionOut,
    ObraSocialIn,
    ObraSocialOut,
    TramoCoberturaOut,
)
from app.turnos.servicio import Actor

__all__ = ["crear_router"]


def _obra_social_out(obra: ObraSocial) -> ObraSocialOut:
    return ObraSocialOut(
        id=obra.id,
        nombre=obra.nombre,
        activa=obra.activa,
        creado_en=obra.creado_en,
    )


def _cobertura_out(cobertura: Cobertura) -> CoberturaOut:
    return CoberturaOut(
        id=cobertura.id,
        obra_social_id=cobertura.obra_social_id,
        prestacion_id=cobertura.prestacion_id,
        modo=cobertura.modo,
        valor=cobertura.valor,
        tope_centavos=cobertura.tope_centavos,
        validada_en_vivo=cobertura.validada_en_vivo,
        creado_en=cobertura.creado_en,
    )


def _tramo_out(tramo: TramoCobertura) -> TramoCoberturaOut:
    return TramoCoberturaOut(
        precio_base_centavos=tramo.precio_base_centavos,
        cobertura_os=tramo.cobertura_os,
        a_cargo_paciente=tramo.a_cargo_paciente,
        origen=tramo.origen,
        validada_en_vivo=tramo.validada_en_vivo,
    )


def _liquidacion_out(liquidacion: Liquidacion) -> LiquidacionOut:
    return LiquidacionOut(
        id=liquidacion.id,
        obra_social_id=liquidacion.obra_social_id,
        periodo_desde=liquidacion.periodo_desde,
        periodo_hasta=liquidacion.periodo_hasta,
        estado=liquidacion.estado,
        total_centavos=liquidacion.total_centavos,
        creado_en=liquidacion.creado_en,
        cerrada_en=liquidacion.cerrada_en,
        lineas=[
            LineaLiquidacionOut(
                turno_id=linea.turno_id,
                paciente_id=linea.paciente_id,
                prestacion_id=linea.prestacion_id,
                fecha=linea.fecha,
                monto_centavos=linea.monto_centavos,
            )
            for linea in liquidacion.lineas
        ],
    )


def crear_router(svc: ServicioObrasSociales) -> APIRouter:
    r = APIRouter()

    # -- catálogo -------------------------------------------------------
    @r.post("/api/obras-sociales", status_code=201, response_model=ObraSocialOut)
    def crear_obra_social(
        body: ObraSocialIn, actor: Actor = Depends(actor_desde_headers)
    ) -> ObraSocialOut:
        return _obra_social_out(svc.crear_obra_social(actor, nombre=body.nombre))

    @r.get("/api/obras-sociales", response_model=list[ObraSocialOut])
    def listar_obras_sociales(
        solo_activas: bool = False, actor: Actor = Depends(actor_desde_headers)
    ) -> list[ObraSocialOut]:
        return [
            _obra_social_out(obra)
            for obra in svc.listar_obras_sociales(actor, solo_activas=solo_activas)
        ]

    @r.patch("/api/obras-sociales/{obra_social_id}", response_model=ObraSocialOut)
    def cambiar_estado(
        obra_social_id: str,
        body: EstadoObraSocialIn,
        actor: Actor = Depends(actor_desde_headers),
    ) -> ObraSocialOut:
        return _obra_social_out(
            svc.cambiar_estado(actor, obra_social_id=obra_social_id, activa=body.activa)
        )

    # -- coberturas -----------------------------------------------------
    @r.put("/api/coberturas", response_model=CoberturaOut)
    def configurar_cobertura(
        body: CoberturaIn, actor: Actor = Depends(actor_desde_headers)
    ) -> CoberturaOut:
        return _cobertura_out(
            svc.configurar_cobertura(
                actor,
                obra_social_id=body.obra_social_id,
                prestacion_id=body.prestacion_id,
                modo=body.modo,
                valor=body.valor,
                tope_centavos=body.tope_centavos,
            )
        )

    @r.get("/api/coberturas", response_model=list[CoberturaOut])
    def listar_coberturas(
        obra_social_id: str | None = None, actor: Actor = Depends(actor_desde_headers)
    ) -> list[CoberturaOut]:
        return [
            _cobertura_out(cobertura)
            for cobertura in svc.listar_coberturas(actor, obra_social_id=obra_social_id)
        ]

    @r.get("/api/coberturas/preview", response_model=TramoCoberturaOut)
    def preview_cobertura(
        paciente_id: str,
        prestacion_id: str,
        actor: Actor = Depends(actor_desde_headers),
    ) -> TramoCoberturaOut:
        return _tramo_out(
            svc.preview_cobertura(actor, paciente_id=paciente_id, prestacion_id=prestacion_id)
        )

    # -- liquidaciones --------------------------------------------------
    @r.post("/api/liquidaciones", status_code=201, response_model=LiquidacionOut)
    def generar_liquidacion(
        body: LiquidacionIn, actor: Actor = Depends(actor_desde_headers)
    ) -> LiquidacionOut:
        return _liquidacion_out(
            svc.generar_liquidacion(
                actor,
                obra_social_id=body.obra_social_id,
                desde=body.desde,
                hasta=body.hasta,
            )
        )

    @r.get("/api/liquidaciones", response_model=list[LiquidacionOut])
    def listar_liquidaciones(
        obra_social_id: str | None = None,
        desde: date | None = None,
        hasta: date | None = None,
        actor: Actor = Depends(actor_desde_headers),
    ) -> list[LiquidacionOut]:
        return [
            _liquidacion_out(liquidacion)
            for liquidacion in svc.listar_liquidaciones(
                actor, obra_social_id=obra_social_id, desde=desde, hasta=hasta
            )
        ]

    @r.get("/api/liquidaciones/{liquidacion_id}", response_model=LiquidacionOut)
    def obtener_liquidacion(
        liquidacion_id: str, actor: Actor = Depends(actor_desde_headers)
    ) -> LiquidacionOut:
        return _liquidacion_out(
            svc.obtener_liquidacion(actor, liquidacion_id=liquidacion_id)
        )

    @r.post("/api/liquidaciones/{liquidacion_id}/cerrar", response_model=LiquidacionOut)
    def cerrar_liquidacion(
        liquidacion_id: str, actor: Actor = Depends(actor_desde_headers)
    ) -> LiquidacionOut:
        return _liquidacion_out(
            svc.cerrar_liquidacion(actor, liquidacion_id=liquidacion_id)
        )

    @r.get("/api/liquidaciones/{liquidacion_id}/export.csv")
    def exportar_liquidacion(
        liquidacion_id: str, actor: Actor = Depends(actor_desde_headers)
    ) -> Response:
        contenido = svc.exportar_liquidacion_csv(actor, liquidacion_id=liquidacion_id)
        return Response(
            content=contenido,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="liquidacion-{liquidacion_id}.csv"'
            },
        )

    return r
