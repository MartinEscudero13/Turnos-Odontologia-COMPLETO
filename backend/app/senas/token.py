"""Token opaco de la página de pago de la seña — D6 / F-16 (C-11 §5).

`secrets.token_urlsafe(32)` = 256 bits de entropía, **nunca** derivado de ids ni
correlativo. La base guarda sólo `sha256(token)` (`senas.token_hash`, UNIQUE
global); el token en claro se entrega una única vez en la respuesta de la
reserva y después sólo se acepta como path param.

El token no es un login (PO-06 sigue abierta): no crea sesión, no identifica al
paciente y no habilita ninguna otra ruta.
"""
from __future__ import annotations

import hashlib
import secrets

__all__ = ["BYTES_TOKEN", "generar_token", "hash_token"]

BYTES_TOKEN = 32


def generar_token() -> str:
    """Token urlsafe de 32 bytes (43 caracteres en base64url sin padding)."""
    return secrets.token_urlsafe(BYTES_TOKEN)


def hash_token(token: str) -> str:
    """SHA-256 hexadecimal del token; es lo único que se persiste."""
    if not token:
        raise ValueError("el token de pago no puede ser vacío")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
