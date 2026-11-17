"""Casos de uso de C-13: recordatorios, webhook Twilio, fallback y recall."""
from __future__ import annotations

import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from app.turnos.servicio import Actor, Invalido, NoAutenticado, NoEncontrado, Prohibido
from app.whatsapp.puertos import (
    AuditoriaPort,
    ConfigWhatsAppPort,
    EmailNoDisponible,
    EmailPort,
    EstadoMensaje,
    Mensaje,
    MensajeRepositorio,
    PasarelaWhatsAppPort,
    Plantilla,
    TurnosWhatsAppPort,
    WhatsAppNoDisponible,
)
from app.whatsapp.twilio import mapear_estado_twilio

_GESTION = frozenset({"ADMIN", "RECEPCION"})
_CLINICO = frozenset({"ADMIN", "ODONTOLOGO"})
_MAX_INTENTOS = 3
Reloj = Callable[[], datetime]


@dataclass(frozen=True)
class ResultadoWebhook:
    estado: EstadoMensaje | None
    respuesta: str | None
    turno_id: str | None
    link_confirmacion: str | None = None


@dataclass(frozen=True)
class ResultadoEnvio:
    enviados: int
    fallidos: int
    mensajes: tuple[Mensaje, ...]


class ServicioWhatsApp:
    def __init__(
        self,
        mensajes: MensajeRepositorio,
        turnos: TurnosWhatsAppPort,
        pasarela: PasarelaWhatsAppPort,
        email: EmailPort,
        config: ConfigWhatsAppPort,
        auditoria: AuditoriaPort,
        *,
        url_confirmacion: str = "https://demo.local/confirmar",
        reloj: Reloj | None = None,
    ) -> None:
        self._mensajes = mensajes
        self._turnos = turnos
        self._pasarela = pasarela
        self._email = email
        self._config = config
        self._auditoria = auditoria
        self._url_confirmacion = url_confirmacion
        self._reloj: Reloj = reloj or (lambda: datetime.now(UTC))

    # ------------------------------------------------------------------
    # Recordatorios
    # ------------------------------------------------------------------

    def programar_recordatorios(self, actor: Actor) -> ResultadoEnvio:
        self._exigir_gestion(actor)
        if not self._config.habilitado(tenant_id=actor.tenant_id):
            return ResultadoEnvio(0, 0, ())
        momento = self._reloj()
        hasta = momento + timedelta(hours=self._config.anticipacion_h(tenant_id=actor.tenant_id))
        enviados: list[Mensaje] = []
        fallidos = 0
        for turno in self._turnos.proximos(
            tenant_id=actor.tenant_id, desde=momento, hasta=hasta
        ):
            if not turno.telefono:
                continue
            existente = self._mensajes.por_turno_plantilla(
                tenant_id=actor.tenant_id,
                turno_id=turno.turno_id,
                plantilla="RECORDATORIO",
            )
            if existente is not None:
                if existente.estado != "FALLIDO":
                    continue
                actualizado = self._intentar(
                    mensaje=existente, destino=turno.telefono, actor=actor
                )
                if actualizado.estado == "FALLIDO":
                    fallidos += 1
                else:
                    enviados.append(actualizado)
                continue
            mensaje = self._crear(
                tenant_id=actor.tenant_id,
                paciente_id=turno.paciente_id,
                turno_id=turno.turno_id,
                plantilla="RECORDATORIO",
                cuerpo=(
                    f"Recordatorio: tenés un turno de {turno.prestacion} "
                    f"el {turno.inicio.isoformat()}. Respondé SI para confirmar o NO para cancelar."
                ),
                destino=turno.telefono,
                actor=actor,
            )
            if mensaje.estado == "FALLIDO":
                fallidos += 1
            else:
                enviados.append(mensaje)
        return ResultadoEnvio(len(enviados), fallidos, tuple(enviados))

    def procesar_pendientes(self, actor: Actor) -> ResultadoEnvio:
        self._exigir_gestion(actor)
        procesados: list[Mensaje] = []
        fallidos = 0
        for mensaje in self._mensajes.pendientes(tenant_id=actor.tenant_id):
            telefono = self._turnos.telefono_paciente(
                tenant_id=actor.tenant_id, paciente_id=mensaje.paciente_id
            )
            if not telefono:
                continue
            actualizado = self._intentar(
                mensaje=mensaje,
                destino=telefono,
                actor=actor,
            )
            if actualizado.estado == "FALLIDO":
                fallidos += 1
            else:
                procesados.append(actualizado)
        return ResultadoEnvio(len(procesados), fallidos, tuple(procesados))

    def _crear(
        self,
        *,
        tenant_id: str,
        paciente_id: str,
        turno_id: str | None,
        plantilla: Plantilla,
        cuerpo: str,
        destino: str,
        actor: Actor,
    ) -> Mensaje:
        mensaje = self._mensajes.crear(
            tenant_id=tenant_id,
            paciente_id=paciente_id,
            turno_id=turno_id,
            plantilla=plantilla,
            canal="WA",
            cuerpo=cuerpo,
            ahora=self._reloj(),
        )
        return self._intentar(mensaje=mensaje, destino=destino, actor=actor)

    def _intentar(self, *, mensaje: Mensaje, destino: str, actor: Actor) -> Mensaje:
        try:
            envio = self._pasarela.enviar(
                destino=destino, cuerpo=mensaje.cuerpo, turno_id=mensaje.turno_id
            )
        except WhatsAppNoDisponible:
            fallido = self._mensajes.actualizar(
                tenant_id=mensaje.tenant_id,
                mensaje_id=mensaje.id,
                estado="FALLIDO",
                intentos=mensaje.intentos + 1,
                proximo_intento=self._reloj() + timedelta(minutes=10),
                ahora=self._reloj(),
            )
            self._fallback_email(fallido, destino=destino, actor=actor)
            return fallido
        actualizado = self._mensajes.actualizar(
            tenant_id=mensaje.tenant_id,
            mensaje_id=mensaje.id,
            estado=envio.estado,
            provider_message_id=envio.provider_message_id,
            ahora=self._reloj(),
        )
        self._auditar(
            actor,
            "WHATSAPP_ENVIADO",
            "mensaje",
            actualizado.id,
            despues={"plantilla": actualizado.plantilla, "estado": actualizado.estado},
        )
        return actualizado

    def _fallback_email(self, mensaje: Mensaje, *, destino: str, actor: Actor) -> None:
        if mensaje.turno_id is not None and self._mensajes.por_turno_plantilla(
            tenant_id=mensaje.tenant_id,
            turno_id=mensaje.turno_id,
            plantilla=mensaje.plantilla,
            canal="EMAIL",
        ) is not None:
            return
        try:
            self._email.enviar(
                destino=destino,
                asunto="Recordatorio de turno",
                cuerpo=mensaje.cuerpo,
            )
            estado: EstadoMensaje = "ENVIADO"
        except EmailNoDisponible:
            estado = "FALLIDO"
        email = self._mensajes.crear(
            tenant_id=mensaje.tenant_id,
            paciente_id=mensaje.paciente_id,
            turno_id=mensaje.turno_id,
            plantilla=mensaje.plantilla,
            canal="EMAIL",
            cuerpo=mensaje.cuerpo,
            ahora=self._reloj(),
        )
        self._mensajes.actualizar(
            tenant_id=mensaje.tenant_id,
            mensaje_id=email.id,
            estado=estado,
            ahora=self._reloj(),
        )
        self._auditar(
            actor,
            "WHATSAPP_FALLBACK_EMAIL",
            "mensaje",
            email.id,
            despues={"estado": estado},
        )

    # ------------------------------------------------------------------
    # Webhook
    # ------------------------------------------------------------------

    def recibir_webhook(
        self,
        payload: dict[str, str],
        *,
        tenant_id: str | None = None,
        telefono: str | None = None,
        origen: str = "twilio",
    ) -> ResultadoWebhook:
        provider_id = payload.get("MessageSid") or payload.get("SmsSid")
        body = payload.get("Body")
        remitente = telefono or payload.get("From")
        if remitente and remitente.startswith("whatsapp:"):
            remitente = remitente[len("whatsapp:") :]
        mensaje = None
        if provider_id:
            mensaje = self._mensajes.por_provider(
                provider_message_id=provider_id, tenant_id=tenant_id
            )
        # Las respuestas no siempre traen el id del mensaje original: se resuelven
        # por el teléfono del paciente contra el último recordatorio enviado.
        if mensaje is None and body and remitente and tenant_id:
            paciente_id = self._turnos.paciente_por_telefono(
                tenant_id=tenant_id, telefono=remitente
            )
            if paciente_id is not None:
                mensaje = self._mensajes.ultimo_por_paciente(
                    tenant_id=tenant_id, paciente_id=paciente_id
                )
        if mensaje is None:
            if not provider_id and not remitente:
                raise Invalido("falta MessageSid")
            raise NoEncontrado("mensaje no encontrado")
        actor = Actor(tenant_id=mensaje.tenant_id, rol="ADMIN", user_id=origen)

        estado = None
        status = payload.get("MessageStatus") or payload.get("SmsStatus")
        if status:
            estado = mapear_estado_twilio(status)
            self._mensajes.actualizar(
                tenant_id=mensaje.tenant_id,
                mensaje_id=mensaje.id,
                estado=estado,
                ahora=self._reloj(),
            )

        respuesta: str | None = None
        turno_id = mensaje.turno_id
        link: str | None = None
        if body:
            normalizado = _normalizar(body)
            if normalizado in ("SI", "CONFIRMO", "1"):
                respuesta = "SI" if mensaje.turno_id is None or self._turnos.confirmar(
                    tenant_id=mensaje.tenant_id, turno_id=mensaje.turno_id
                ) else "NO_APLICADO"
            elif normalizado in ("NO", "CANCELO", "2"):
                respuesta = "NO" if mensaje.turno_id is None or self._turnos.cancelar(
                    tenant_id=mensaje.tenant_id, turno_id=mensaje.turno_id
                ) else "NO_APLICADO"
            else:
                respuesta = "AMBIGUA"
                link = f"{self._url_confirmacion}/{mensaje.id}"
            self._mensajes.actualizar(
                tenant_id=mensaje.tenant_id,
                mensaje_id=mensaje.id,
                estado=(estado or mensaje.estado),
                respuesta=respuesta,
                ahora=self._reloj(),
            )
        self._auditar(
            actor,
            "WHATSAPP_WEBHOOK",
            "mensaje",
            mensaje.id,
            despues={"estado": estado, "respuesta": respuesta},
        )
        return ResultadoWebhook(
            estado=estado, respuesta=respuesta, turno_id=turno_id, link_confirmacion=link
        )

    # ------------------------------------------------------------------
    # Recall y lectura
    # ------------------------------------------------------------------

    def crear_recall(
        self, actor: Actor, *, paciente_id: str, motivo: str, fecha_objetivo: date
    ) -> Mensaje:
        if actor.rol == "PACIENTE":
            raise NoAutenticado("sesión interna requerida")
        if actor.rol not in _CLINICO:
            raise Prohibido("sólo odontología o admin crean recall")
        if not motivo.strip():
            raise Invalido("el recall exige un motivo clínico")
        telefono = self._turnos.telefono_paciente(
            tenant_id=actor.tenant_id, paciente_id=paciente_id
        )
        if not telefono:
            raise NoEncontrado("paciente sin teléfono para recall")
        cuerpo = (
            f"Control clínico: {motivo.strip()}. "
            f"Fecha objetivo: {fecha_objetivo.isoformat()}. Respondé SI para coordinar."
        )
        return self._crear(
            tenant_id=actor.tenant_id,
            paciente_id=paciente_id,
            turno_id=None,
            plantilla="RECALL",
            cuerpo=cuerpo,
            destino=telefono,
            actor=actor,
        )

    def listar_mensajes(
        self, actor: Actor, *, turno_id: str | None = None
    ) -> list[Mensaje]:
        self._exigir_gestion(actor)
        return self._mensajes.listar(tenant_id=actor.tenant_id, turno_id=turno_id)

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    @staticmethod
    def _exigir_gestion(actor: Actor) -> None:
        if actor.rol == "PACIENTE":
            raise NoAutenticado("sesión interna requerida")
        if actor.rol not in _GESTION:
            raise Prohibido("rol sin permiso para gestionar recordatorios")

    def _auditar(
        self,
        actor: Actor,
        accion: str,
        entidad: str,
        entidad_id: str,
        *,
        antes: dict[str, object] | None = None,
        despues: dict[str, object] | None = None,
    ) -> None:
        self._auditoria.registrar(
            tenant_id=actor.tenant_id,
            accion=accion,
            actor=actor.user_id,
            entidad=entidad,
            entidad_id=entidad_id,
            antes=antes,
            despues=despues,
        )


def _normalizar(texto: str) -> str:
    sin_acentos = "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", texto.strip().upper())
        if not unicodedata.combining(caracter)
    )
    return sin_acentos
