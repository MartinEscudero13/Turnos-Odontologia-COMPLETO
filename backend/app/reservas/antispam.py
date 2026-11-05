"""Anti-spam: rate-limit por (tenant, IP) y (tenant, acción) + verificación single-use.

D5: dos capas. (1) contador por `(tenant, ip)` y por `(tenant, acción)` sobre
`ContadorPort` → `429` con `Retry-After` sin mutar; (2) verificación liviana de un
solo uso emitida por el router y exigida en reservar/cancelar/reprogramar.

El proveedor del desafío (captcha u OTP) es indistinto para el dominio (OQ-2): el
`VerificadorPort` no fija el canal; lo recibe como configuración.
"""
from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timedelta

from app.reservas.puertos import AccionPublica, DesafioPublico


class ContadorMemoria:
    """Contador por clave con ventana deslizante simple (TTL)."""

    def __init__(self) -> None:
        self._claves: dict[str, tuple[float, int]] = {}  # clave -> (expira_ts, cuenta)
        self._lock = threading.Lock()

    def incrementar(self, clave: str, ventana_s: int) -> int:
        ahora = time.monotonic()
        with self._lock:
            expira, cuenta = self._claves.get(clave, (0.0, 0))
            if ahora >= expira:
                cuenta = 0
                expira = ahora + ventana_s
            cuenta += 1
            self._claves[clave] = (expira, cuenta)
            return cuenta

    def ttl_s(self, clave: str) -> int:
        ahora = time.monotonic()
        expira, _ = self._claves.get(clave, (0.0, 0))
        return max(0, int(expira - ahora))


class VerificadorMemoria:
    """Verificación liviana single-use en memoria (Redis en producción, D10)."""

    def __init__(self, *, ttl_min: int, canal: str) -> None:
        self._ttl_min = ttl_min
        self._canal = canal
        self._desafios: dict[tuple[str, str, str], DesafioPublico] = {}
        self._consumidos: set[tuple[str, str, str]] = set()
        self._lock = threading.Lock()

    def desafio(
        self, *, tenant_id: str, accion: AccionPublica, ip: str, ahora: datetime
    ) -> DesafioPublico:
        del ip  # el canal real (captcha/OTP) puede usar la IP; acá es indistinta
        verificacion_id = str(uuid.uuid4())
        expira_at = ahora + timedelta(minutes=self._ttl_min)
        desafio = DesafioPublico(
            verificacion_id=verificacion_id, expira_at=expira_at, canal=self._canal
        )
        with self._lock:
            self._desafios[(tenant_id, accion, verificacion_id)] = desafio
        return desafio

    def verificar(
        self,
        *,
        tenant_id: str,
        accion: AccionPublica,
        prueba: str,
        ip: str,
        ahora: datetime,
    ) -> bool:
        del ip
        clave = (tenant_id, accion, prueba)
        with self._lock:
            desafio = self._desafios.get(clave)
            if desafio is None or clave in self._consumidos:
                return False
            if ahora > desafio.expira_at:
                return False
            self._consumidos.add(clave)
            return True
