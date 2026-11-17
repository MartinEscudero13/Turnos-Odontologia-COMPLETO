# Despliegue en EasyPanel

EasyPanel levanta el stack Docker y maneja el dominio + HTTPS con Traefik. No hace falta Caddy ni
abrir puertos de base de datos.

## 1. Crear la app

1. En EasyPanel, creá un proyecto (por ejemplo `turnos`).
2. **Create Service → App**.
3. Source: **GitHub**.
4. Repositorio: `MartinEscudero13/Turnos-Odontologia-COMPLETO`.
5. Branch: `master`.
6. Build: **Docker Compose**.
7. Compose file: `docker-compose.easypanel.yml`.
8. Deploy.

## 2. Variables de entorno

En **Environment** de la app, cargá:

```env
POSTGRES_PASSWORD=<password-larga>
POSTGRES_APP_PASSWORD=<otra-password-larga>
JWT_SECRET=<aleatorio-de-32+>
DEMO_PASSWORD=<password-fuerte-para-la-demo>
APP_URL=https://app.tudominio.com
WA_PROVIDER=fake
DEMO_PHONE_RECIPIENT=
```

Opcionales para WhatsApp real:

```env
META_WA_TOKEN=
META_PHONE_NUMBER_ID=
META_VERIFY_TOKEN=
META_APP_SECRET=
META_API_VERSION=v23.0
```

No cargues `.env` en el repo; EasyPanel guarda estas variables.

## 3. Dominio del frontend

1. En la app, **Domains → Add Domain**.
2. Servicio: `web`.
3. Container port: **80**.
4. Dominio: `app.tudominio.com`.
5. Activá **HTTPS / Let's Encrypt**.

El `web` (nginx) ya hace proxy de `/api` a `api:8000` dentro de la red de Docker; no necesitás
configurar CORS.

## 4. Dominio del API/Swagger (opcional, recomendado)

Para abrir Swagger y recibir webhooks:

1. **Domains → Add Domain**.
2. Servicio: `api`.
3. Container port: **8000**.
4. Dominio: `api.tudominio.com`.
5. HTTPS.

Quedaría:

- App: `https://app.tudominio.com`
- Swagger: `https://api.tudominio.com/docs`
- Webhook Meta: `https://api.tudominio.com/api/webhooks/whatsapp/meta?tenant=a0000000-0000-4000-8000-000000000001`

## 5. Primer despliegue

El servicio `migrate`:

1. Corre `alembic upgrade head`.
2. Ejecuta `seed_demo.py`.
3. Termina y queda `exited` (es normal).

La `api` espera a que `migrate` termine. Si EasyPanel no respeta `depends_on` en Compose:

1. Ejecutá `migrate` manualmente una vez desde la consola del servicio.
2. Luego reiniciá `api`.

## 6. Verificar

```text
https://app.tudominio.com/api/health   -> {"status":"UP",...}
https://app.tudominio.com/login
https://app.tudominio.com/app
https://app.tudominio.com/r/demo
https://api.tudominio.com/docs
```

Login demo: tenant `demo` · `admin@demo.test` · `DEMO_PASSWORD`.

## 7. Actualizar

1. Push a `master`.
2. En EasyPanel, **Deploy** de la app.
3. El `migrate` vuelve a correr; es idempotente.

## 8. Backup

Desde la terminal del servicio `db`:

```bash
pg_dump -U turnos_owner -d turnos -Fc > /tmp/turnos.dump
```

O desde tu máquina, si exponés el puerto temporalmente:

```bash
docker compose exec -T db pg_dump -U turnos_owner -d turnos -Fc > turnos.dump
```

## Notas y límites

- **Estado en memoria**: agenda, clínica, caja, señas, OS, calendario y WhatsApp viven en el proceso
  de la API. Se reinicia al redeploy; el seed restaura los datos base.
- **Auth/catálogos**: PostgreSQL.
- **WhatsApp**: `WA_PROVIDER=fake`; los adaptadores Twilio/Meta quedan listos.
- **Un solo contenedor de API**: no escales `api` a más de 1 réplica si querés conservar el estado de
  la demo.
- **Seguridad**: no publiques los puertos de `db`/`redis`; EasyPanel solo debe enrutar `web:80` y,
  opcionalmente, `api:8000`.
- **Migrate**: si EasyPanel lo marca como fallido por haber terminado, configuralo como one-shot o
  ignorá el estado; lo importante es que la API arranque.
