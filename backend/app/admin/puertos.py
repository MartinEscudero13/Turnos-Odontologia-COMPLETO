"""Puertos y adaptadores en memoria de C-15 (admin del tenant)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Protocol

from app.turnos.servicio import TurnoError

CODIGO_USUARIO_DUPLICADO = "USUARIO_DUPLICADO"
CODIGO_AUTO_DESACTIVACION = "AUTO_DESACTIVACION"

Reloj = Callable[[], datetime]

__all__ = [
    "CODIGO_AUTO_DESACTIVACION",
    "CODIGO_USUARIO_DUPLICADO",
    "AuditoriaMemoria",
    "AuditoriaPort",
    "ConfigMemoria",
    "ConfigRepositorio",
    "ConflictoAdmin",
    "DatosReporte",
    "ExportacionMemoria",
    "ExportacionRepositorio",
    "Kpis",
    "ReportesMemoria",
    "ReportesRepositorio",
    "UsuarioAdmin",
    "UsuarioAdminRepositorio",
    "UsuarioDuplicado",
    "UsuariosMemoria",
]


class ConflictoAdmin(TurnoError):
    """`409` de admin con código de dominio."""

    codigo = 409

    def __init__(self, codigo_dominio: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.codigo_dominio: str = codigo_dominio


class UsuarioDuplicado(Exception):
    """Señal de repositorio: email ya usado en el tenant."""


@dataclass(frozen=True)
class UsuarioAdmin:
    id: str
    tenant_id: str
    nombre: str
    email: str
    rol: str
    activo: bool
    creado_en: datetime


@dataclass(frozen=True)
class DatosReporte:
    """Números crudos del período; el servicio calcula porcentajes."""

    total_turnos: int
    por_estado: dict[str, int]
    online: int
    facturacion_por_profesional: tuple[tuple[str, int], ...]
    reasignados_2h: int
    minutos_ocupados: int = 0
    minutos_disponibles: int = 0


@dataclass(frozen=True)
class Kpis:
    desde: date
    hasta: date
    total_turnos: int
    turnos_por_estado: dict[str, int]
    ausentismo_pct: float
    reservas_online_pct: float
    facturacion_por_profesional: tuple[tuple[str, int], ...]
    reasignados_2h: int
    ocupacion_pct: float


class ConfigRepositorio(Protocol):
    def obtener(self, *, tenant_id: str) -> dict[str, object]: ...

    def actualizar(
        self, *, tenant_id: str, valores: dict[str, object], ahora: datetime
    ) -> dict[str, object]: ...


class UsuarioAdminRepositorio(Protocol):
    def listar(self, *, tenant_id: str) -> list[UsuarioAdmin]: ...

    def obtener(self, *, tenant_id: str, usuario_id: str) -> UsuarioAdmin | None: ...

    def por_email(self, *, tenant_id: str, email: str) -> UsuarioAdmin | None: ...

    def crear(
        self,
        *,
        tenant_id: str,
        nombre: str,
        email: str,
        password_hash: str,
        rol: str,
        ahora: datetime,
    ) -> UsuarioAdmin: ...

    def cambiar_activo(
        self, *, tenant_id: str, usuario_id: str, activo: bool
    ) -> UsuarioAdmin: ...


class ExportacionRepositorio(Protocol):
    def exportar(self, *, tenant_id: str) -> dict[str, list[dict[str, object]]]: ...


class ReportesRepositorio(Protocol):
    def datos(self, *, tenant_id: str, desde: date, hasta: date) -> DatosReporte: ...


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


class ConfigMemoria:
    def __init__(self, seed: dict[str, dict[str, object]] | None = None) -> None:
        self._items = {tenant: dict(valores) for tenant, valores in (seed or {}).items()}

    def obtener(self, *, tenant_id: str) -> dict[str, object]:
        return dict(self._items.get(tenant_id, {}))

    def actualizar(
        self, *, tenant_id: str, valores: dict[str, object], ahora: datetime
    ) -> dict[str, object]:
        del ahora
        actual = self._items.get(tenant_id, {})
        actual.update(valores)
        self._items[tenant_id] = actual
        return dict(actual)


class UsuariosMemoria:
    def __init__(self, seed: list[UsuarioAdmin] | None = None) -> None:
        self._items: dict[str, UsuarioAdmin] = {u.id: u for u in (seed or [])}
        self._secuencia = len(self._items)

    def listar(self, *, tenant_id: str) -> list[UsuarioAdmin]:
        return sorted(
            (u for u in self._items.values() if u.tenant_id == tenant_id),
            key=lambda u: u.email,
        )

    def obtener(self, *, tenant_id: str, usuario_id: str) -> UsuarioAdmin | None:
        usuario = self._items.get(usuario_id)
        return usuario if usuario is not None and usuario.tenant_id == tenant_id else None

    def por_email(self, *, tenant_id: str, email: str) -> UsuarioAdmin | None:
        for usuario in self._items.values():
            if usuario.tenant_id == tenant_id and usuario.email == email:
                return usuario
        return None

    def crear(
        self,
        *,
        tenant_id: str,
        nombre: str,
        email: str,
        password_hash: str,
        rol: str,
        ahora: datetime,
    ) -> UsuarioAdmin:
        del password_hash
        if self.por_email(tenant_id=tenant_id, email=email) is not None:
            raise UsuarioDuplicado(email)
        self._secuencia += 1
        usuario = UsuarioAdmin(
            id=f"usuario-{self._secuencia}",
            tenant_id=tenant_id,
            nombre=nombre,
            email=email,
            rol=rol,
            activo=True,
            creado_en=ahora,
        )
        self._items[usuario.id] = usuario
        return usuario

    def cambiar_activo(
        self, *, tenant_id: str, usuario_id: str, activo: bool
    ) -> UsuarioAdmin:
        usuario = self.obtener(tenant_id=tenant_id, usuario_id=usuario_id)
        if usuario is None:
            raise KeyError(usuario_id)
        actualizado = replace(usuario, activo=activo)
        self._items[usuario_id] = actualizado
        return actualizado


class ExportacionMemoria:
    def __init__(self, seed: dict[str, dict[str, list[dict[str, object]]]] | None = None) -> None:
        self._items = seed or {}

    def exportar(self, *, tenant_id: str) -> dict[str, list[dict[str, object]]]:
        return {seccion: list(filas) for seccion, filas in self._items.get(tenant_id, {}).items()}


class ReportesMemoria:
    def __init__(self, seed: dict[str, DatosReporte] | None = None) -> None:
        self._items = seed or {}

    def datos(self, *, tenant_id: str, desde: date, hasta: date) -> DatosReporte:
        del desde, hasta
        return self._items.get(tenant_id, DatosReporte(0, {}, 0, (), 0))


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
