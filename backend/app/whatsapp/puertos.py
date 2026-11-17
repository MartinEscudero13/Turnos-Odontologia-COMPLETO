"""Puertos y adaptadores en memoria de C-13 (WhatsApp)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal, Protocol

from app.turnos.servicio import Actor, TurnoError

Plantilla = Literal["RECORDATORIO", "CONFIRMACION", "CANCELACION", "RECALL"]
Canal = Literal["WA", "EMAIL"]
EstadoMensaje = Literal["PENDIENTE", "ENVIADO", "ENTREGADO", "LEIDO", "FALLIDO"]

CODIGO_FIRMA_INVALIDA = "FIRMA_INVALIDA"
CODIGO_WEBHOOK_NO_CONFIGURADO = "WEBHOOK_NO_CONFIGURADO"

Reloj = Callable[[], datetime]

__all__ = [
    "CODIGO_FIRMA_INVALIDA",
    "CODIGO_WEBHOOK_NO_CONFIGURADO",
    "AuditoriaMemoria",
    "AuditoriaPort",
    "Canal",
    "ConfigWhatsAppMemoria",
    "ConfigWhatsAppPort",
    "EmailFake",
    "EmailPort",
    "EnvioWA",
    "EstadoMensaje",
    "FirmaInvalida",
    "Mensaje",
    "MensajeMemoria",
    "MensajeRepositorio",
    "PasarelaWhatsAppFake",
    "PasarelaWhatsAppPort",
    "Plantilla",
    "TurnoMensaje",
    "TurnosWhatsAppMemoria",
    "TurnosWhatsAppPort",
    "WhatsAppNoDisponible",
]


class FirmaInvalida(TurnoError):
    codigo = 401
    codigo_dominio = CODIGO_FIRMA_INVALIDA


class WebhookNoConfigurado(TurnoError):
    codigo = 503
    codigo_dominio = CODIGO_WEBHOOK_NO_CONFIGURADO


class WhatsAppNoDisponible(Exception):
    """Twilio no responde o rechaza el envío."""


class EmailNoDisponible(Exception):
    """El fallback de email tampoco está disponible."""


@dataclass(frozen=True)
class Mensaje:
    id: str
    tenant_id: str
    paciente_id: str
    turno_id: str | None
    plantilla: Plantilla
    canal: Canal
    estado: EstadoMensaje
    provider_message_id: str | None
    intentos: int
    proximo_intento: datetime
    cuerpo: str
    respuesta: str | None
    creado_en: datetime


@dataclass(frozen=True)
class TurnoMensaje:
    turno_id: str
    paciente_id: str
    telefono: str | None
    inicio: datetime
    fin: datetime
    estado: str
    prestacion: str


@dataclass(frozen=True)
class EnvioWA:
    provider_message_id: str
    estado: EstadoMensaje


class MensajeRepositorio(Protocol):
    def crear(
        self,
        *,
        tenant_id: str,
        paciente_id: str,
        turno_id: str | None,
        plantilla: Plantilla,
        canal: Canal,
        cuerpo: str,
        ahora: datetime,
    ) -> Mensaje: ...

    def obtener(self, *, tenant_id: str, mensaje_id: str) -> Mensaje | None: ...

    def por_provider(
        self, *, provider_message_id: str, tenant_id: str | None = None
    ) -> Mensaje | None: ...

    def por_turno_plantilla(
        self,
        *,
        tenant_id: str,
        turno_id: str,
        plantilla: Plantilla,
        canal: Canal = "WA",
    ) -> Mensaje | None: ...

    def ultimo_por_paciente(
        self, *, tenant_id: str, paciente_id: str, canal: Canal = "WA"
    ) -> Mensaje | None: ...

    def listar(self, *, tenant_id: str, turno_id: str | None = None) -> list[Mensaje]: ...

    def pendientes(self, *, tenant_id: str) -> list[Mensaje]: ...

    def actualizar(
        self,
        *,
        tenant_id: str,
        mensaje_id: str,
        estado: EstadoMensaje,
        provider_message_id: str | None = None,
        intentos: int | None = None,
        proximo_intento: datetime | None = None,
        respuesta: str | None = None,
        ahora: datetime,
    ) -> Mensaje: ...


class TurnosWhatsAppPort(Protocol):
    def proximos(
        self, *, tenant_id: str, desde: datetime, hasta: datetime
    ) -> list[TurnoMensaje]: ...

    def telefono_paciente(self, *, tenant_id: str, paciente_id: str) -> str | None: ...

    def paciente_por_telefono(self, *, tenant_id: str, telefono: str) -> str | None: ...

    def confirmar(self, *, tenant_id: str, turno_id: str) -> bool: ...

    def cancelar(self, *, tenant_id: str, turno_id: str) -> bool: ...


class PasarelaWhatsAppPort(Protocol):
    def enviar(
        self, *, destino: str, cuerpo: str, turno_id: str | None = None
    ) -> EnvioWA: ...


class EmailPort(Protocol):
    def enviar(self, *, destino: str, asunto: str, cuerpo: str) -> None: ...


class ConfigWhatsAppPort(Protocol):
    def habilitado(self, *, tenant_id: str) -> bool: ...

    def anticipacion_h(self, *, tenant_id: str) -> int: ...


class AuditoriaPort(Protocol):
    def registrar(
        self,
        *,
        tenant_id: str,
        accion: str,
        actor: str,
        entidad: str,
        entidad_id: str,
        antes: dict[str, object] | None = None,
        despues: dict[str, object] | None = None,
    ) -> None: ...


# ---------------------------------------------------------------------------
# Adaptadores en memoria
# ---------------------------------------------------------------------------


class MensajeMemoria:
    def __init__(self, reloj: Reloj | None = None) -> None:
        self._reloj = reloj or (lambda: datetime.now(UTC))
        self._items: dict[str, Mensaje] = {}
        self._secuencia = 0

    def crear(
        self,
        *,
        tenant_id: str,
        paciente_id: str,
        turno_id: str | None,
        plantilla: Plantilla,
        canal: Canal,
        cuerpo: str,
        ahora: datetime,
    ) -> Mensaje:
        self._secuencia += 1
        mensaje = Mensaje(
            id=f"mensaje-{self._secuencia}",
            tenant_id=tenant_id,
            paciente_id=paciente_id,
            turno_id=turno_id,
            plantilla=plantilla,
            canal=canal,
            estado="PENDIENTE",
            provider_message_id=None,
            intentos=0,
            proximo_intento=ahora,
            cuerpo=cuerpo,
            respuesta=None,
            creado_en=ahora,
        )
        self._items[mensaje.id] = mensaje
        return mensaje

    def obtener(self, *, tenant_id: str, mensaje_id: str) -> Mensaje | None:
        mensaje = self._items.get(mensaje_id)
        return mensaje if mensaje is not None and mensaje.tenant_id == tenant_id else None

    def por_provider(
        self, *, provider_message_id: str, tenant_id: str | None = None
    ) -> Mensaje | None:
        del tenant_id
        for mensaje in self._items.values():
            if mensaje.provider_message_id == provider_message_id:
                return mensaje
        return None

    def por_turno_plantilla(
        self,
        *,
        tenant_id: str,
        turno_id: str,
        plantilla: Plantilla,
        canal: Canal = "WA",
    ) -> Mensaje | None:
        for mensaje in self._items.values():
            if (
                mensaje.tenant_id == tenant_id
                and mensaje.turno_id == turno_id
                and mensaje.plantilla == plantilla
                and mensaje.canal == canal
            ):
                return mensaje
        return None

    def ultimo_por_paciente(
        self, *, tenant_id: str, paciente_id: str, canal: Canal = "WA"
    ) -> Mensaje | None:
        candidatos = [
            mensaje
            for mensaje in self._items.values()
            if mensaje.tenant_id == tenant_id
            and mensaje.paciente_id == paciente_id
            and mensaje.canal == canal
        ]
        if not candidatos:
            return None
        return max(candidatos, key=lambda mensaje: mensaje.creado_en)

    def listar(self, *, tenant_id: str, turno_id: str | None = None) -> list[Mensaje]:
        return sorted(
            (
                mensaje
                for mensaje in self._items.values()
                if mensaje.tenant_id == tenant_id
                and (turno_id is None or mensaje.turno_id == turno_id)
            ),
            key=lambda mensaje: mensaje.creado_en,
            reverse=True,
        )

    def pendientes(self, *, tenant_id: str) -> list[Mensaje]:
        return [
            mensaje
            for mensaje in self._items.values()
            if mensaje.tenant_id == tenant_id
            and mensaje.canal == "WA"
            and mensaje.estado == "FALLIDO"
            and mensaje.intentos < 3
        ]

    def actualizar(
        self,
        *,
        tenant_id: str,
        mensaje_id: str,
        estado: EstadoMensaje,
        provider_message_id: str | None = None,
        intentos: int | None = None,
        proximo_intento: datetime | None = None,
        respuesta: str | None = None,
        ahora: datetime,
    ) -> Mensaje:
        del ahora
        mensaje = self.obtener(tenant_id=tenant_id, mensaje_id=mensaje_id)
        if mensaje is None:
            raise KeyError(mensaje_id)
        actualizado = replace(
            mensaje,
            estado=estado,
            provider_message_id=(
                mensaje.provider_message_id
                if provider_message_id is None
                else provider_message_id
            ),
            intentos=mensaje.intentos if intentos is None else intentos,
            proximo_intento=(
                mensaje.proximo_intento if proximo_intento is None else proximo_intento
            ),
            respuesta=mensaje.respuesta if respuesta is None else respuesta,
        )
        self._items[mensaje_id] = actualizado
        return actualizado


class ConfigWhatsAppMemoria:
    def __init__(
        self,
        seed: dict[str, dict[str, object]] | None = None,
        *,
        habilitado: bool = True,
        anticipacion_h: int = 24,
    ) -> None:
        self._seed = seed or {}
        self._habilitado = habilitado
        self._anticipacion_h = anticipacion_h

    def habilitado(self, *, tenant_id: str) -> bool:
        valor = self._seed.get(tenant_id, {}).get("recordatorios_habilitados", self._habilitado)
        return bool(valor)

    def anticipacion_h(self, *, tenant_id: str) -> int:
        valor = self._seed.get(tenant_id, {}).get("anticipacion_h", self._anticipacion_h)
        return valor if isinstance(valor, int) else self._anticipacion_h


class PasarelaWhatsAppFake:
    def __init__(self) -> None:
        self.fallar = False
        self.enviados: list[dict[str, object]] = []
        self._secuencia = 0

    def enviar(self, *, destino: str, cuerpo: str, turno_id: str | None = None) -> EnvioWA:
        if self.fallar:
            raise WhatsAppNoDisponible("twilio no disponible")
        self._secuencia += 1
        provider_id = f"SM{self._secuencia:04d}"
        self.enviados.append(
            {"destino": destino, "cuerpo": cuerpo, "turno_id": turno_id, "sid": provider_id}
        )
        return EnvioWA(provider_message_id=provider_id, estado="ENVIADO")


class EmailFake:
    def __init__(self) -> None:
        self.fallar = False
        self.enviados: list[dict[str, str]] = []

    def enviar(self, *, destino: str, asunto: str, cuerpo: str) -> None:
        if self.fallar:
            raise EmailNoDisponible("smtp no disponible")
        self.enviados.append({"destino": destino, "asunto": asunto, "cuerpo": cuerpo})


class TurnosWhatsAppMemoria:
    """Adaptador demo sobre `ServicioTurnos` + `PacienteMemoria` + hueco de C-07."""

    def __init__(self, servicio_turnos: object, pacientes: object, hueco: object) -> None:
        self._turnos = servicio_turnos
        self._pacientes = pacientes
        self._hueco = hueco

    def _actor(self, tenant_id: str) -> Actor:
        return Actor(tenant_id=tenant_id, rol="RECEPCION", user_id="whatsapp")

    def proximos(
        self, *, tenant_id: str, desde: datetime, hasta: datetime
    ) -> list[TurnoMensaje]:
        filas: list[TurnoMensaje] = []
        for turno in self._turnos.listar(self._actor(tenant_id)):  # type: ignore[attr-defined]
            if turno.estado not in ("PENDIENTE", "CONFIRMADO") or not (
                desde <= turno.inicio <= hasta
            ):
                continue
            paciente = self._pacientes.paciente(tenant_id, turno.paciente_id)  # type: ignore[attr-defined]
            filas.append(
                TurnoMensaje(
                    turno_id=turno.id,
                    paciente_id=turno.paciente_id,
                    telefono=None if paciente is None else paciente.telefono,
                    inicio=turno.inicio,
                    fin=turno.fin,
                    estado=turno.estado,
                    prestacion=turno.prestacion_id,
                )
            )
        return sorted(filas, key=lambda fila: fila.inicio)

    def telefono_paciente(self, *, tenant_id: str, paciente_id: str) -> str | None:
        paciente = self._pacientes.paciente(tenant_id, paciente_id)  # type: ignore[attr-defined]
        return None if paciente is None else paciente.telefono

    def paciente_por_telefono(self, *, tenant_id: str, telefono: str) -> str | None:
        paciente = self._pacientes.buscar_por_telefono(  # type: ignore[attr-defined]
            tenant_id, telefono
        )
        return None if paciente is None else paciente.id

    def confirmar(self, *, tenant_id: str, turno_id: str) -> bool:
        try:
            self._turnos.confirmar(self._actor(tenant_id), turno_id)  # type: ignore[attr-defined]
        except Exception:
            return False
        return True

    def cancelar(self, *, tenant_id: str, turno_id: str) -> bool:
        try:
            self._turnos.cancelar(self._actor(tenant_id), turno_id)  # type: ignore[attr-defined]
        except Exception:
            return False
        self._hueco.emitir(tenant_id=tenant_id, turno_id=turno_id)  # type: ignore[attr-defined]
        return True


class AuditoriaMemoria:
    def __init__(self) -> None:
        self.entradas: list[dict[str, object]] = []

    def registrar(
        self,
        *,
        tenant_id: str,
        accion: str,
        actor: str,
        entidad: str,
        entidad_id: str,
        antes: dict[str, object] | None = None,
        despues: dict[str, object] | None = None,
    ) -> None:
        self.entradas.append(
            {
                "tenant_id": tenant_id,
                "accion": accion,
                "actor": actor,
                "entidad": entidad,
                "entidad_id": entidad_id,
                "antes": antes,
                "despues": despues,
            }
        )
