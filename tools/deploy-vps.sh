#!/usr/bin/env bash
# Despliega/actualiza la demo en una VPS con Docker + Caddy.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "Falta .env. Copiá .env.example y completá los secretos antes de desplegar." >&2
  exit 1
fi

docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps

echo
echo "Demo desplegada. Revisá el dominio configurado en DOMAIN/APP_URL."
