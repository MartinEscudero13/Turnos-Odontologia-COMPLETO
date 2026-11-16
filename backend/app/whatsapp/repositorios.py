"""Repositorios SQLAlchemy de C-13 (mensajes, turnos y configuración)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.models.catalogos import Paciente
from app.models.tenant import ParametroTenant
from app.models.turno import Turno
from app.models.whatsapp import MensajeWA as MensajeModel
from app.whatsapp.puertos import (
    Canal,
    EstadoMensaje,
    Mensaje,
    Plantilla,
    TurnoMensaje,
)

__all__ = ["ConfigWhatsAppSQL", "MensajeSQL", "TurnosWhatsAppSQL"]


def _uuid(valor: str) -> uuid.UUID:
    return uuid.UUID(valor)


def _fijar_tenant(session: Session, tenant_id: str) -> None:
    session.execute(
        text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": tenant_id}
    )


def _rowcount(resultado: Any) -> int:
    return int(getattr(resultado, "rowcount", 0))


def _a_mensaje(modelo: MensajeModel) -> Mensaje:
    return Mensaje(
        id=str(modelo.id),
        tenant_id=str(modelo.tenant_id),
        paciente_id=str(modelo.paciente_id),
        turno_id=None if modelo.turno_id is None else str(modelo.turno_id),
        plantilla=modelo.plantilla,  # type: ignore[arg-type]
        canal=modelo.canal,  # type: ignore[arg-type]
        estado=modelo.estado,  # type: ignore[arg-type]
        provider_message_id=modelo.provider_message_id,
        intentos=modelo.intentos,
        proximo_intento=modelo.proximo_intento,
        cuerpo=modelo.cuerpo,
        respuesta=modelo.respuesta,
        creado_en=modelo.creado_en,
    )


class MensajeSQL:
    def __init__(self, session: Session) -> None:
        self._session = session

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
        _fijar_tenant(self._session, tenant_id)
        modelo = MensajeModel(
            tenant_id=_uuid(tenant_id),
            paciente_id=_uuid(paciente_id),
            turno_id=None if turno_id is None else _uuid(turno_id),
            plantilla=plantilla,
            canal=canal,
            estado="PENDIENTE",
            intentos=0,
            proximo_intento=ahora,
            cuerpo=cuerpo,
            creado_en=ahora,
            actualizado_en=ahora,
        )
        self._session.add(modelo)
        self._session.flush()
        return _a_mensaje(modelo)

    def obtener(self, *, tenant_id: str, mensaje_id: str) -> Mensaje | None:
        _fijar_tenant(self._session, tenant_id)
        modelo = self._session.scalar(
            select(MensajeModel).where(
                MensajeModel.id == _uuid(mensaje_id),
                MensajeModel.tenant_id == _uuid(tenant_id),
            )
        )
        return None if modelo is None else _a_mensaje(modelo)

    def por_provider(
        self, *, provider_message_id: str, tenant_id: str | None = None
    ) -> Mensaje | None:
        if tenant_id is not None:
            _fijar_tenant(self._session, tenant_id)
        modelo = self._session.scalar(
            select(MensajeModel).where(
                MensajeModel.provider_message_id == provider_message_id
            )
        )
        return None if modelo is None else _a_mensaje(modelo)

    def por_turno_plantilla(
        self,
        *,
        tenant_id: str,
        turno_id: str,
        plantilla: Plantilla,
        canal: Canal = "WA",
    ) -> Mensaje | None:
        _fijar_tenant(self._session, tenant_id)
        modelo = self._session.scalar(
            select(MensajeModel).where(
                MensajeModel.tenant_id == _uuid(tenant_id),
                MensajeModel.turno_id == _uuid(turno_id),
                MensajeModel.plantilla == plantilla,
                MensajeModel.canal == canal,
            )
        )
        return None if modelo is None else _a_mensaje(modelo)

    def listar(self, *, tenant_id: str, turno_id: str | None = None) -> list[Mensaje]:
        _fijar_tenant(self._session, tenant_id)
        consulta = select(MensajeModel).where(MensajeModel.tenant_id == _uuid(tenant_id))
        if turno_id is not None:
            consulta = consulta.where(MensajeModel.turno_id == _uuid(turno_id))
        return [
            _a_mensaje(modelo)
            for modelo in self._session.scalars(
                consulta.order_by(MensajeModel.creado_en.desc())
            )
        ]

    def pendientes(self, *, tenant_id: str) -> list[Mensaje]:
        _fijar_tenant(self._session, tenant_id)
        return [
            _a_mensaje(modelo)
            for modelo in self._session.scalars(
                select(MensajeModel).where(
                    MensajeModel.tenant_id == _uuid(tenant_id),
                    MensajeModel.canal == "WA",
                    MensajeModel.estado == "FALLIDO",
                    MensajeModel.intentos < 3,
                )
            )
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
        _fijar_tenant(self._session, tenant_id)
        modelo = self._session.scalar(
            select(MensajeModel).where(
                MensajeModel.id == _uuid(mensaje_id),
                MensajeModel.tenant_id == _uuid(tenant_id),
            )
        )
        if modelo is None:
            raise KeyError(mensaje_id)
        modelo.estado = estado
        if provider_message_id is not None:
            modelo.provider_message_id = provider_message_id
        if intentos is not None:
            modelo.intentos = intentos
        if proximo_intento is not None:
            modelo.proximo_intento = proximo_intento
        if respuesta is not None:
            modelo.respuesta = respuesta
        modelo.actualizado_en = ahora
        self._session.flush()
        return _a_mensaje(modelo)


class TurnosWhatsAppSQL:
    def __init__(self, session: Session) -> None:
        self._session = session

    def proximos(
        self, *, tenant_id: str, desde: datetime, hasta: datetime
    ) -> list[TurnoMensaje]:
        _fijar_tenant(self._session, tenant_id)
        filas = self._session.execute(
            select(
                Turno.id,
                Turno.paciente_id,
                Paciente.telefono,
                Turno.inicio,
                Turno.fin,
                Turno.estado,
                Turno.prestacion_id,
            )
            .join(Paciente, Paciente.id == Turno.paciente_id)
            .where(
                Turno.tenant_id == _uuid(tenant_id),
                Turno.estado.in_(("PENDIENTE", "CONFIRMADO")),
                Turno.inicio >= desde,
                Turno.inicio <= hasta,
            )
            .order_by(Turno.inicio)
        ).all()
        return [
            TurnoMensaje(
                turno_id=str(fila[0]),
                paciente_id=str(fila[1]),
                telefono=fila[2],
                inicio=fila[3],
                fin=fila[4],
                estado=fila[5],
                prestacion=str(fila[6]),
            )
            for fila in filas
        ]

    def telefono_paciente(self, *, tenant_id: str, paciente_id: str) -> str | None:
        _fijar_tenant(self._session, tenant_id)
        return self._session.scalar(
            select(Paciente.telefono).where(
                Paciente.id == _uuid(paciente_id),
                Paciente.tenant_id == _uuid(tenant_id),
            )
        )

    def confirmar(self, *, tenant_id: str, turno_id: str) -> bool:
        _fijar_tenant(self._session, tenant_id)
        resultado = self._session.execute(
            update(Turno)
            .where(
                Turno.id == _uuid(turno_id),
                Turno.tenant_id == _uuid(tenant_id),
                Turno.estado == "PENDIENTE",
            )
            .values(estado="CONFIRMADO")
        )
        return bool(_rowcount(resultado))

    def cancelar(self, *, tenant_id: str, turno_id: str) -> bool:
        _fijar_tenant(self._session, tenant_id)
        resultado = self._session.execute(
            update(Turno)
            .where(
                Turno.id == _uuid(turno_id),
                Turno.tenant_id == _uuid(tenant_id),
                Turno.estado.in_(("PENDIENTE", "CONFIRMADO")),
            )
            .values(estado="CANCELADO")
        )
        return bool(_rowcount(resultado))


class ConfigWhatsAppSQL:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _parametros(self, tenant_id: str) -> dict[str, object]:
        _fijar_tenant(self._session, tenant_id)
        filas = self._session.scalars(
            select(ParametroTenant).where(ParametroTenant.tenant_id == _uuid(tenant_id))
        )
        return {fila.clave: fila.valor for fila in filas}

    def habilitado(self, *, tenant_id: str) -> bool:
        valor = self._parametros(tenant_id).get("recordatorios_habilitados", True)
        return bool(valor)

    def anticipacion_h(self, *, tenant_id: str) -> int:
        valor = self._parametros(tenant_id).get("recordatorio_anticipacion_h", 24)
        return valor if isinstance(valor, int) else 24
