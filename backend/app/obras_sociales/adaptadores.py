"""Adaptadores de C-12 hacia C-09 — cobertura real para el presupuesto.

C-09 define `CoberturaPort` con su propio `CoberturaConfigurada`. Este adaptador
traduce la cobertura persistida por C-12 sin acoplar el dominio del presupuesto a
las tablas de obras sociales.
"""
from __future__ import annotations

from app.obras_sociales.servicio import ServicioObrasSociales
from app.presupuesto.puertos import CoberturaConfigurada

__all__ = ["CoberturaPresupuesto"]


class CoberturaPresupuesto:
    """`CoberturaPort` de C-09 sobre el catálogo de C-12."""

    def __init__(self, servicio: ServicioObrasSociales) -> None:
        self._servicio = servicio

    def cobertura(
        self, *, tenant_id: str, obra_social_id: str | None, prestacion_id: str
    ) -> CoberturaConfigurada | None:
        if obra_social_id is None:
            return None
        cobertura = self._servicio.cobertura_para(
            tenant_id=tenant_id,
            obra_social_id=obra_social_id,
            prestacion_id=prestacion_id,
        )
        if cobertura is None:
            return None
        return CoberturaConfigurada(
            modo=cobertura.modo,
            valor=cobertura.valor,
            tope=cobertura.tope_centavos,
        )
