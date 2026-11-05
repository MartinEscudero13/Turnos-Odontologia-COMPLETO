"""Servicio de lista de espera — alta/baja/listar/compatibles (C-07).

Dominio puro: programa contra `ListaEsperaRepositorio`/`OfertaRepositorio` y los
puertos de catálogo/paciente de C-06; no toca DB ni Redis. Valida que paciente,
prestación y profesional de preferencia pertenezcan al mismo tenant (404 en caso
contrario) y que no exista una entrada activa duplicada (409).
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from app.lista_espera.puertos import (
    AccionListaEspera,
    AuditoriaPort,
    Entrada,
    EntradaDuplicada,
    ListaEsperaRepositorio,
    OfertaRepositorio,
)
from app.reservas.puertos import CatalogoPort, PacientePort
from app.turnos.servicio import Actor, NoEncontrado, Prohibido, TurnoError


class Conflicto(TurnoError):
    """409 — conflicto de dominio (alta duplicada, oferta ya reclamada, etc.)."""

    codigo = 409


_ACTORES_GESTION = frozenset({"RECEPCION", "ADMIN"})
_ESTADOS_GESTIONABLES = frozenset({"PENDIENTE", "OFRECIDO"})


class ServicioListaEspera:
    """Casos de uso de gestión de la lista de espera (actor recepción/admin)."""

    def __init__(
        self,
        repositorio: ListaEsperaRepositorio,
        ofertas: OfertaRepositorio,
        catalogo: CatalogoPort,
        pacientes: PacientePort,
        auditoria: AuditoriaPort,
        reloj: Callable[[], datetime] | None = None,
    ) -> None:
        self._repo = repositorio
        self._ofertas = ofertas
        self._catalogo = catalogo
        self._pacientes = pacientes
        self._auditoria = auditoria
        self._reloj = reloj or (lambda: datetime.now(UTC))

    def _momento(self, ahora: datetime | None) -> datetime:
        return ahora if ahora is not None else self._reloj()

    @staticmethod
    def _exigir_gestion(actor: Actor) -> None:
        if actor.rol not in _ACTORES_GESTION:
            raise Prohibido("solo recepción o admin gestionan la lista de espera")

    def alta(
        self,
        actor: Actor,
        *,
        paciente_id: str,
        prestacion_id: str,
        profesional_pref: str | None = None,
        ventana_desde: datetime | None = None,
        ventana_hasta: datetime | None = None,
        ahora: datetime | None = None,
    ) -> Entrada:
        self._exigir_gestion(actor)
        momento = self._momento(ahora)
        tenant_id = actor.tenant_id
        if self._pacientes.paciente(tenant_id, paciente_id) is None:
            raise NoEncontrado("paciente no encontrado")
        if self._catalogo.prestacion(tenant_id, prestacion_id) is None:
            raise NoEncontrado("prestación no encontrada")
        if profesional_pref is not None and self._catalogo.profesional(tenant_id, profesional_pref) is None:
            raise NoEncontrado("profesional no encontrado")
        try:
            entrada = self._repo.alta(
                tenant_id=tenant_id,
                paciente_id=paciente_id,
                prestacion_id=prestacion_id,
                profesional_pref=profesional_pref,
                ventana_desde=ventana_desde,
                ventana_hasta=ventana_hasta,
                ahora=momento,
            )
        except EntradaDuplicada as exc:
            raise Conflicto("ya existe una entrada activa") from exc
        self._auditar(
            tenant_id, "ALTA", actor.user_id,
            entrada_id=entrada.id, estado_despues=entrada.estado,
        )
        return entrada

    def baja(self, actor: Actor, *, entrada_id: str, ahora: datetime | None = None) -> Entrada:
        self._exigir_gestion(actor)
        tenant_id = actor.tenant_id
        entrada = self._repo.obtener(tenant_id=tenant_id, entrada_id=entrada_id)
        if entrada is None or entrada.estado not in _ESTADOS_GESTIONABLES:
            raise NoEncontrado("entrada no encontrada")
        # Anular la oferta vigente (si la hay) libera el hueco retenido.
        oferta = self._ofertas.vigente_para_entrada(tenant_id=tenant_id, entrada_id=entrada_id)
        if oferta is not None:
            self._ofertas.cancelar(tenant_id=tenant_id, oferta_id=oferta.id)
            self._auditar(
                tenant_id, "OFERTA_CANCELADA", actor.user_id,
                entrada_id=entrada_id, oferta_id=oferta.id,
                estado_antes="PENDIENTE", estado_despues="CANCELADA",
            )
        retirada = self._repo.baja(tenant_id=tenant_id, entrada_id=entrada_id, ahora=self._momento(ahora))
        self._auditar(
            tenant_id, "BAJA", actor.user_id,
            entrada_id=entrada_id, estado_antes=entrada.estado, estado_despues="VENCIDO",
        )
        return retirada

    def listar(
        self,
        actor: Actor,
        *,
        prestacion_id: str | None = None,
        profesional_id: str | None = None,
    ) -> list[Entrada]:
        self._exigir_gestion(actor)
        return self._repo.listar(
            tenant_id=actor.tenant_id,
            prestacion_id=prestacion_id,
            profesional_id=profesional_id,
        )

    def compatibles(
        self,
        tenant_id: str,
        *,
        prestacion_id: str,
        profesional_id: str,
        inicio: datetime,
        ahora: datetime | None = None,
    ) -> list[Entrada]:
        return self._repo.compatibles(
            tenant_id=tenant_id,
            prestacion_id=prestacion_id,
            profesional_id=profesional_id,
            inicio=inicio,
            ahora=ahora,
        )

    def _auditar(
        self,
        tenant_id: str,
        accion: AccionListaEspera,
        actor_id: str,
        *,
        entrada_id: str | None = None,
        oferta_id: str | None = None,
        turno_id: str | None = None,
        estado_antes: str | None = None,
        estado_despues: str | None = None,
    ) -> None:
        self._auditoria.registrar(
            tenant_id=tenant_id,
            accion=accion,
            actor=actor_id,
            entrada_id=entrada_id,
            oferta_id=oferta_id,
            turno_id=turno_id,
            estado_antes=estado_antes,
            estado_despues=estado_despues,
        )
