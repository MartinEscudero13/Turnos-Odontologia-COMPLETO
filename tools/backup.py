"""Respaldo y restauración de la base PostgreSQL.

Genera un dump custom (comprimido) con ``pg_dump`` y lo restaura con
``pg_restore``. No guarda credenciales: la URL sale de ``DATABASE_URL`` (o
``C02_DATABASE_URL`` en local) y sólo se usa en memoria.

Uso:
    py tools/backup.py
    py tools/backup.py --output backups/turnos.dump
    py tools/backup.py --restore backups/turnos.dump

Si ``pg_dump`` no está en el PATH, el script muestra el comando equivalente de
Docker para no fallar en silencio.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL") or os.environ.get("C02_DATABASE_URL")
    if not url:
        raise SystemExit("definí DATABASE_URL (o C02_DATABASE_URL) con la base de datos")
    # pg_dump entiende libpq, no el dialecto SQLAlchemy.
    for prefijo in ("postgresql+psycopg://", "postgresql+psycopg2://"):
        if url.startswith(prefijo):
            return "postgresql://" + url[len(prefijo) :]
    return url


def _pg_dump() -> str:
    for nombre in ("pg_dump", "pg_dump.exe"):
        ruta = shutil.which(nombre)
        if ruta:
            return ruta
    raise SystemExit(
        "no encontré pg_dump en el PATH. Alternativa con Docker:\n"
        "  docker compose exec -T db pg_dump -U turnos_owner -Fc turnos > backups/turnos.dump"
    )


def _pg_restore() -> str:
    for nombre in ("pg_restore", "pg_restore.exe"):
        ruta = shutil.which(nombre)
        if ruta:
            return ruta
    raise SystemExit("no encontré pg_restore en el PATH")


def respaldar(destino: Path) -> int:
    destino.parent.mkdir(parents=True, exist_ok=True)
    comando = [
        _pg_dump(),
        "--dbname",
        _database_url(),
        "--format=custom",
        "--no-owner",
        "--file",
        str(destino),
    ]
    print(f"respaldando en {destino}")
    resultado = subprocess.run(comando, check=False)
    if resultado.returncode == 0:
        print(f"respaldo OK: {destino} ({destino.stat().st_size} bytes)")
    return resultado.returncode


def restaurar(origen: Path) -> int:
    if not origen.is_file():
        raise SystemExit(f"no existe el archivo {origen}")
    comando = [
        _pg_restore(),
        "--dbname",
        _database_url(),
        "--clean",
        "--if-exists",
        "--no-owner",
        str(origen),
    ]
    print(f"restaurando {origen}")
    resultado = subprocess.run(comando, check=False)
    if resultado.returncode == 0:
        print("restauración OK")
    return resultado.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Respaldo/restauración PostgreSQL")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("backups") / f"turnos-{datetime.now():%Y%m%d-%H%M%S}.dump",
        help="archivo de destino del respaldo",
    )
    parser.add_argument("--restore", type=Path, help="archivo a restaurar")
    args = parser.parse_args(argv)
    if args.restore is not None:
        return restaurar(args.restore)
    return respaldar(args.output)


if __name__ == "__main__":
    sys.exit(main())
