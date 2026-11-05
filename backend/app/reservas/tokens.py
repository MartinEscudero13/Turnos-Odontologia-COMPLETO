"""Token público por turno — task 3.1 (D3).

UUID v4 no secuencial, uno por turno, emitido al crear y transferido al turno
nuevo al reprogramar. Expira por estado (no por reloj): el servicio es quien
decide si el turno apuntado sigue siendo gestionable.
"""
from __future__ import annotations

import threading
import uuid

from app.reservas.puertos import TokenResuelto


class TokenRepositorioEnMemoria:
    """Índice token → (tenant_id, turno_id) en memoria (Redis/DB en producción)."""

    def __init__(self) -> None:
        self._indice: dict[str, TokenResuelto] = {}
        self._lock = threading.Lock()

    def emitir(self, tenant_id: str, turno_id: str) -> str:
        token = str(uuid.uuid4())
        with self._lock:
            self._indice[token] = TokenResuelto(tenant_id=tenant_id, turno_id=turno_id)
        return token

    def resolver(self, tenant_id: str, token: str) -> TokenResuelto | None:
        resuelto = self._indice.get(token)
        if resuelto is None or resuelto.tenant_id != tenant_id:
            return None
        return resuelto

    def transferir(self, token: str, turno_nuevo_id: str) -> None:
        with self._lock:
            resuelto = self._indice.get(token)
            if resuelto is not None:
                self._indice[token] = TokenResuelto(
                    tenant_id=resuelto.tenant_id, turno_id=turno_nuevo_id
                )

    def revocar(self, token: str) -> None:
        with self._lock:
            self._indice.pop(token, None)
