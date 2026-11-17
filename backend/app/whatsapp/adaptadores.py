"""Adaptadores de configuración de WhatsApp sobre el admin del tenant."""
from __future__ import annotations

from typing import Protocol

__all__ = ["ConfigWhatsAppAdmin"]


class _ConfigTenant(Protocol):
    def obtener(self, *, tenant_id: str) -> dict[str, object]: ...


class ConfigWhatsAppAdmin:
    """Lee la configuración de WhatsApp desde la misma fuente que `/app/config`.

    Evita el bug de tener dos configuraciones: el toggle de recordatorios de la
    pantalla de administración gobierna el envío real de recordatorios.
    """

    def __init__(self, config: _ConfigTenant) -> None:
        self._config = config

    def habilitado(self, *, tenant_id: str) -> bool:
        valor = self._config.obtener(tenant_id=tenant_id).get(
            "recordatorios_habilitados", True
        )
        return bool(valor)

    def anticipacion_h(self, *, tenant_id: str) -> int:
        valor = self._config.obtener(tenant_id=tenant_id).get(
            "recordatorio_anticipacion_h", 24
        )
        return valor if isinstance(valor, int) else 24
