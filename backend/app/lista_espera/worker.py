"""Worker de auto-oferta de huecos liberados y rotación por expiración (C-07).

Dominio puro: consume `ServicioTurnos` (sólo lectura del slot del turno liberado y
creación del turno aceptado) y los puertos de lista de espera; no toca Redis ni DB.
En producción `HuecoLiberadoPort` encola un job Redis con clave idempotente
`auto_oferta:{turno_id}`; acá el worker es síncrono e idempotente por oferta vigente.

D3/D4/D5/D8: la expiración se acota a `min(ahora + OFERTA_TTL_MIN, slot.inicio)`; si
el slot ya pasó el hueco queda público directo; la aceptación reclama la oferta en
transacción y revalida el solape con `ServicioTurnos.crear` antes de convertir.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.lista_espera.puertos import (
    AccionListaEspera,
    AuditoriaPort,
    ListaEsperaRepositorio,
    NotificadorNulo,
    NotificadorPort,
    Oferta,
    OfertaRepositorio,
)
from app.lista_espera.servicio import Conflicto
from app.turnos.servicio import (
    Actor,
    ConflictoSolape,
    NoEncontrado,
    ServicioTurnos,
    Turno,
)


class ServicioAutoOferta:
    """Procesa huecos liberados, rota ofertas vencidas y acepta ofertas por token."""

    def __init__(
        self,
        servicio_turnos: ServicioTurnos,
        repositorio: ListaEsperaRepositorio,
        ofertas: OfertaRepositorio,
        auditoria: AuditoriaPort,
        notificador: NotificadorPort | None = None,
        *,
        oferta_ttl_min: int,
        reloj: Callable[[], datetime] | None = None,
    ) -> None:
        self._servicio_turnos = servicio_turnos
        self._repo = repositorio
        self._ofertas = ofertas
        self._auditoria = auditoria
        self._notificador = notificador or NotificadorNulo()
        self._oferta_ttl_min = oferta_ttl_min
        self._reloj = reloj or (lambda: datetime.now(UTC))

    def _momento(self, ahora: datetime | None) -> datetime:
        return ahora if ahora is not None else self._reloj()

    @staticmethod
    def _actor(tenant_id: str) -> Actor:
        return Actor(tenant_id=tenant_id, rol="RECEPCION", user_id="lista-espera")

    # ---- hueco liberado ----

    def procesar_hueco_liberado(
        self, tenant_id: str, turno_id: str, ahora: datetime | None = None
    ) -> Oferta | None:
        momento = self._momento(ahora)
        if self._ofertas.vigente_para(tenant_id=tenant_id, hueco_turno_id=turno_id) is not None:
            return None  # idempotencia: ya hay oferta vigente para este hueco
        return self._ofertar(tenant_id, turno_id, momento)

    # ---- expiración / rotación ----

    def procesar_expiracion(self, tenant_id: str, ahora: datetime | None = None) -> list[Oferta]:
        momento = self._momento(ahora)
        huecos: set[str] = set()
        for oferta in self._ofertas.vencidas(tenant_id=tenant_id, ahora=momento):
            self._ofertas.marcar(tenant_id=tenant_id, oferta_id=oferta.id, estado="VENCIDA")
            self._repo.cambiar_estado(
                tenant_id=tenant_id, entrada_id=oferta.entrada_id, estado="PENDIENTE"
            )
            self._auditar(
                tenant_id, "OFERTA_VENCIDA", "worker",
                entrada_id=oferta.entrada_id, oferta_id=oferta.id,
                estado_antes="PENDIENTE", estado_despues="VENCIDA",
            )
            if oferta.hueco_turno_id is not None:
                huecos.add(oferta.hueco_turno_id)
        creadas: list[Oferta] = []
        for turno_id in sorted(huecos):
            nueva = self._ofertar(tenant_id, turno_id, momento)
            if nueva is not None:
                creadas.append(nueva)
        return creadas

    # ---- aceptación ----

    def aceptar(self, tenant_id: str, token: str, ahora: datetime | None = None) -> Turno:
        momento = self._momento(ahora)
        oferta = self._ofertas.por_token(tenant_id=tenant_id, token=token)
        if oferta is None:
            raise NoEncontrado("oferta no encontrada")
        if oferta.estado != "PENDIENTE":
            raise Conflicto("oferta no vigente")
        if oferta.expira_at <= momento:
            self._marcar_vencida(tenant_id, oferta, "expiró sin aceptación")
            raise Conflicto("oferta vencida")
        reclamada = self._ofertas.aceptar(tenant_id=tenant_id, token=token, ahora=momento)
        if reclamada is None:
            raise Conflicto("oferta ya reclamada")  # perdió la carrera del doble-accept
        entrada = self._repo.obtener(tenant_id=tenant_id, entrada_id=oferta.entrada_id)
        if entrada is None or oferta.hueco_turno_id is None:
            raise NoEncontrado("oferta no encontrada")
        hueco = self._servicio_turnos.obtener(self._actor(tenant_id), oferta.hueco_turno_id)
        duracion_min = round((hueco.fin - hueco.inicio).total_seconds() / 60)
        try:
            turno = self._servicio_turnos.crear(
                self._actor(tenant_id),
                profesional_id=hueco.profesional_id,
                sillon_id=hueco.sillon_id,
                paciente_id=entrada.paciente_id,
                prestacion_id=entrada.prestacion_id,
                inicio=hueco.inicio,
                duracion_min=duracion_min,
                origen="LISTA_ESPERA",
            )
        except ConflictoSolape as exc:
            # El hueco ya lo ocupó otro canal: oferta VENCIDA y entrada vuelve PENDIENTE.
            self._ofertas.marcar(tenant_id=tenant_id, oferta_id=oferta.id, estado="VENCIDA")
            self._repo.cambiar_estado(
                tenant_id=tenant_id, entrada_id=entrada.id, estado="PENDIENTE"
            )
            self._auditar(
                tenant_id, "OFERTA_VENCIDA", "lista-espera",
                entrada_id=entrada.id, oferta_id=oferta.id,
                estado_antes="PENDIENTE", estado_despues="VENCIDA",
            )
            raise Conflicto("hueco ocupado") from exc
        self._repo.cambiar_estado(tenant_id=tenant_id, entrada_id=entrada.id, estado="CONVERTIDO")
        self._auditar(
            tenant_id, "OFERTA_ACEPTADA", "lista-espera",
            entrada_id=entrada.id, oferta_id=oferta.id, turno_id=turno.id,
            estado_antes="OFRECIDO", estado_despues="CONVERTIDO",
        )
        return turno

    # ---- helpers ----

    def _ofertar(self, tenant_id: str, turno_id: str, momento: datetime) -> Oferta | None:
        turno = self._servicio_turnos.obtener(self._actor(tenant_id), turno_id)
        if momento >= turno.inicio:
            return None  # hueco con inicio ya pasado → público directo
        ofertadas = self._ofertas.entradas_ofertadas(tenant_id=tenant_id, hueco_turno_id=turno_id)
        compatibles = self._repo.compatibles(
            tenant_id=tenant_id,
            prestacion_id=turno.prestacion_id,
            profesional_id=turno.profesional_id,
            inicio=turno.inicio,
            ahora=momento,
        )
        for entrada in compatibles:
            if entrada.id in ofertadas:
                continue
            expira_at = min(momento + timedelta(minutes=self._oferta_ttl_min), turno.inicio)
            oferta = self._ofertas.crear(
                tenant_id=tenant_id,
                entrada_id=entrada.id,
                hueco_turno_id=turno_id,
                expira_at=expira_at,
                token=uuid4().hex,
                ahora=momento,
            )
            self._repo.cambiar_estado(
                tenant_id=tenant_id, entrada_id=entrada.id, estado="OFRECIDO"
            )
            self._auditar(
                tenant_id, "OFRECIDO", "worker",
                entrada_id=entrada.id, oferta_id=oferta.id, turno_id=turno_id,
                estado_antes="PENDIENTE", estado_despues="OFRECIDO",
            )
            self._notificador.oferta_emitida(tenant_id=tenant_id, oferta_id=oferta.id)
            return oferta
        return None

    def _marcar_vencida(self, tenant_id: str, oferta: Oferta, motivo: str) -> None:
        del motivo
        self._ofertas.marcar(tenant_id=tenant_id, oferta_id=oferta.id, estado="VENCIDA")
        self._repo.cambiar_estado(
            tenant_id=tenant_id, entrada_id=oferta.entrada_id, estado="PENDIENTE"
        )
        self._auditar(
            tenant_id, "OFERTA_VENCIDA", "worker",
            entrada_id=oferta.entrada_id, oferta_id=oferta.id,
            estado_antes="PENDIENTE", estado_despues="VENCIDA",
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
