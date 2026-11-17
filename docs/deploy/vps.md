# Despliegue en VPS con Docker + Caddy

Esta guía deja la demo pública en una VPS Linux (Ubuntu/Debian). Usa el mismo
`docker-compose.yml` local más un overlay `docker-compose.prod.yml` que agrega Caddy para TLS.

## Requisitos

- VPS con **2 GB de RAM** o más y 2 vCPU.
- Ubuntu 22.04/24.04 o Debian 12.
- Docker + Docker Compose plugin.
- Dominio apuntando a la IP de la VPS (recomendado para HTTPS). Sin dominio se puede usar HTTP en `:80`.
- Puertos **22, 80 y 443** abiertos.

## 1. Instalar Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
newgrp docker
docker compose version
```

## 2. Clonar el repo

```bash
git clone https://github.com/MartinEscudero13/Turnos-Odontologia-COMPLETO.git
cd Turnos-Odontologia-COMPLETO
```

## 3. Crear `.env`

```bash
cp .env.example .env
nano .env
```

Valores mínimos para producción:

```env
APP_ENV=development
APP_URL=https://app.tudominio.com
DOMAIN=app.tudominio.com

POSTGRES_PASSWORD=<password-larga>
POSTGRES_APP_PASSWORD=<otra-password-larga>
JWT_SECRET=<aleatorio-de-32+>
DEMO_PASSWORD=<password-fuerte-para-la-demo>

# La demo usa el adaptador fake; no requiere credenciales externas.
WA_PROVIDER=fake
DEMO_PHONE_RECIPIENT=

# Bindings sólo locales: Caddy es la única entrada pública.
DB_PORT=127.0.0.1:5433
REDIS_PORT=127.0.0.1:6379
API_PORT=127.0.0.1:8000
WEB_PORT=127.0.0.1:5173
```

Si **no** tenés dominio y vas a usar `http://IP`:

```env
APP_URL=http://IP_DE_LA_VPS
DOMAIN=:80
```

> `DOMAIN=:80` hace que Caddy sirva HTTP sin TLS. Para HTTPS, usá un dominio real y dejá
> `DOMAIN=app.tudominio.com`.

## 4. Firewall

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## 5. DNS (si usás dominio)

Creá un registro **A**:

```text
app.tudominio.com -> IP_DE_LA_VPS
```

Esperá la propagación antes de pedir el certificado.

## 6. Desplegar

```bash
chmod +x tools/deploy-vps.sh
./tools/deploy-vps.sh
```

El script:

1. Levanta PostgreSQL y Redis.
2. Corre migraciones y seed demo.
3. Levanta API y SPA.
4. Levanta Caddy en 80/443.

## 7. Verificar

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
curl -fsS https://app.tudominio.com/api/health
```

Abrí:

- `https://app.tudominio.com/login`
- `https://app.tudominio.com/app`
- `https://app.tudominio.com/r/demo`
- `https://app.tudominio.com/docs` (Swagger)

Login demo: tenant `demo` · `admin@demo.test` · `DEMO_PASSWORD`.

## 8. Actualizar

```bash
git pull --ff-only
./tools/deploy-vps.sh
```

## 9. Backup

```bash
docker compose exec -T db pg_dump -U turnos_owner -d turnos -Fc \
  > "turnos-$(date +%Y%m%d-%H%M%S).dump"
```

Restaurar (con el stack detenido o una base limpia):

```bash
docker compose exec -T db pg_restore -U turnos_owner -d turnos --clean --if-exists < archivo.dump
```

## Notas y límites

- **Estado en memoria**: agenda, clínica, caja, señas, OS, calendario y WhatsApp de la demo viven en
  el proceso de la API. Se pierden al reiniciar el contenedor; el seed restaura los datos base.
- **Auth/catálogos** sí están en PostgreSQL.
- **WhatsApp**: `WA_PROVIDER=fake`; los adaptadores Twilio/Meta están listos pero no hay credenciales.
- **Seguridad**: no expongas 5433/6379/8000/5173 al público. Los bindings `127.0.0.1` del `.env` y
  `ufw` lo evitan. Usá una `DEMO_PASSWORD` fuerte y no subas `.env` al repo.
- **Caddy** guarda certificados en los volúmenes `caddy-data` y `caddy-config`.
- Si cambiás el dominio, actualizá `DOMAIN` y `APP_URL` y reiniciá Caddy/API.
