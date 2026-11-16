# Turnos-Odontologia

SaaS multi-tenant argentino de agenda odontológica: turnos con anti-solape real, reserva online, WhatsApp, Mercado Pago y obras sociales.

## Estado del proyecto (corte 2026-11-13)

| | |
|---|---|
| Changes archivados | **21** de 21 — C-01…C-15, F-01…F-06 (C-15 parcial) |
| Specs vivas | **21** capabilities en `openspec/specs/` |
| Migraciones | 001 → **012**, con `downgrade` verificado contra PostgreSQL real |
| Tests backend | **806 passed, 53 skipped** en local · **859 passed, 0 skipped** con `C02_DATABASE_URL` |
| Calidad | `mypy` 123 archivos · `ruff check .` · `openspec validate --all --strict` en verde |
| Frontend | **SPA interno C-05…C-15** + landing pública F-02 · 32 tests, lint, typecheck y build |

> ⚠️ **Antes de mirar el alcance, leé [Límites declarados](#límites-declarados-del-alcance)**: C-05 a C-15
> están montados en `create_app` sobre adaptadores en memoria. Lo que falta es UI, persistencia SQL de
> esos dominios y las integraciones externas reales.

## Equipo

Trabajo grupal de **Martin Escudero** y **Lautaro Naranjo**. Alcance, roles y aclaración sobre entregas anteriores: [`AUTHORS.md`](AUTHORS.md).

- Descubrimiento del problema y alcance: [`docs/discovery/`](docs/discovery/) (informe + checklist).
- Fuente de verdad del dominio (actores, datos, reglas RN-XX, historias US-XXX, arquitectura): [`knowledge-base/`](knowledge-base/README.md).
- Plan de implementación por changes: [`CHANGES.md`](CHANGES.md). Reglas para agentes: [`AGENTS.md`](AGENTS.md).
- Integración MCP (Context7) y documentación del TP «skill propia + MCP»: [`docs/skills-mcp/`](docs/skills-mcp/README.md).
- Fundación C-01: prerequisitos, arquitectura, setup, `docker-compose` y comandos de verificación: [`docs/foundation/bootstrap.md`](docs/foundation/bootstrap.md).
- Sistema visual, skill `visual-turnos` y MCP de diseño (Figma/Stitch): [`docs/design/README.md`](docs/design/README.md) · [`PRODUCT.md`](PRODUCT.md) · [`DESIGN.md`](DESIGN.md).
- Contrato público de reserva: [`docs/api-publica-reserva.md`](docs/api-publica-reserva.md). Decisiones de las preguntas abiertas OQ-1..OQ-9: [`docs/decisiones-oq.md`](docs/decisiones-oq.md).

## Prerrequisitos

| Requisito | Versión | Notas |
|-----------|---------|-------|
| Python | 3.12+ | Se usa el launcher `py` (verificado con Python **3.14.0**; `python` apunta al Store y no se usa). |
| Node.js | 20+ | Frontend verificado con **Node 24**. |
| PostgreSQL | 15+ | En desarrollo se levanta con Docker Compose. |
| Docker / Compose | v25+ | Necesario para el smoke test de la stack. |

Verificá tu entorno:

```bash
py --version
node --version
docker compose version
```

## Instalación

```bash
git clone https://github.com/MartinEscudero13/Turnos-Odontologia-COMPLETO.git
cd Turnos-Odontologia-COMPLETO
py -m pip install -r requirements-dev.txt
cd frontend
npm ci
cd ..
cp .env.example .env
# editá .env: POSTGRES_PASSWORD, POSTGRES_APP_PASSWORD, JWT_SECRET y DEMO_PASSWORD
docker compose up -d --build
```

Para solo compilar o inspeccionar la base compilada, ver `docs/foundation/bootstrap.md` y `scripts/verify-foundation.ps1`.

## Cómo se levanta y qué responde hoy

```bash
docker compose up -d --build
```

Compose levanta PostgreSQL, Redis, corre las migraciones, siembra la demo y arranca API + SPA.

**Credenciales demo** (datos ficticios; la password la definís en `.env` como `DEMO_PASSWORD`):

- Tenant: `demo`
- Usuarios: `admin@demo.test`, `recepcion@demo.test`, `odontologo@demo.test`
- Password: la que hayas puesto en `DEMO_PASSWORD` (mínimo 8 caracteres)

**Frontend interno**: <http://localhost:5173/login> con esas credenciales.
**Reserva pública**: <http://localhost:5173/r/demo> · **Swagger**: <http://localhost:8000/docs>.

Para desarrollo sin Docker:

```bash
docker compose up -d db
$env:DATABASE_OWNER_URL = "postgresql+psycopg://turnos_owner:<POSTGRES_PASSWORD>@localhost:5433/turnos"
$env:DEMO_PASSWORD = "<DEMO_PASSWORD>"
py -m alembic -c backend/alembic.ini upgrade head
py backend/seed_demo.py
$env:DATABASE_URL = "postgresql+psycopg://turnos_app:<POSTGRES_APP_PASSWORD>@localhost:5433/turnos"
cd backend; py -m uvicorn app.main:app --reload --port 8000
```

Rutas del SPA: `/app` resumen · `/app/agenda` · `/app/pacientes` · `/app/clinica` · `/app/caja` ·
`/app/senas` · `/app/whatsapp` · `/app/obras-sociales` · `/app/calendario` · `/app/config`.

## Tests

```bash
py -m pytest tests/                       # 806 passed, 53 skipped (addopts ya trae -q)
py -m ruff check .
py -m mypy --config-file pyproject.toml

cd frontend
npm run lint
npm run typecheck
npm test
npm run build
```

### Suite completa con PostgreSQL real

Los 51 tests que se saltean en local son los que necesitan una base viva (RLS real, `EXCLUDE` de
anti-solape, carreras entre dos conexiones, migraciones). Para correrlos:

```bash
docker compose up -d db
$env:C02_DATABASE_URL = "postgresql+psycopg://turnos_owner:<POSTGRES_PASSWORD>@localhost:5433/turnos"
py -m pytest tests/                       # 859 passed, 0 skipped
docker compose stop db
```

Si `C02_DATABASE_URL` no está definida, esos tests se saltean de forma explícita (no fallan en
silencio). El gate de cada change exige `skipped == 0` con la variable seteada.

Estado verificado al cierre de **C-13 (2026-11-16)**: backend `806 passed, 53 skipped` local y
`859 passed, 0 skipped` con PostgreSQL; `mypy` y `ruff` en verde; `openspec validate --all --strict`
21/21. El frontend incluye el SPA interno C-05…C-15 y la landing pública F-02: `32 passed` +
lint/typecheck/build en verde.

## WhatsApp: Twilio Sandbox

La demo usa **Twilio WhatsApp Sandbox**. Sin credenciales, `WA_PROVIDER=fake` y no se toca la red.

1. Creá una cuenta en <https://www.twilio.com/try-twilio>.
2. En **Messaging → Try it out → Send a WhatsApp message**, uní tu teléfono con el código del sandbox.
3. Copiá `Account SID`, `Auth Token` y el número del sandbox a `.env`:

```env
WA_PROVIDER=twilio
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
```

4. Configurá el webhook de Twilio a una URL pública (ngrok o dominio):

```text
https://TU-TUNEL/api/webhooks/whatsapp?tenant=a0000000-0000-4000-8000-000000000001
```

5. Reiniciá la API y probá desde `/app/whatsapp`: programar recordatorios, listar mensajes y recall.
   Las respuestas `SI`/`NO` confirman o cancelan el turno.

El sandbox sólo envía a números unidos y la sesión dura 24 h; no es producción. El fallback email es
un log hasta configurar SMTP.

## Type hints

Todo el código Python lleva type hints obligatorios (regla dura de `AGENTS.md`); el chequeo automático corre con `mypy` en CI y localmente.

## MCP: Context7

Usamos el servidor MCP **Context7** (Upstash) para traer documentación actualizada de librerías al contexto
del agente. Es una **integración, no una skill**: no se carga con la herramienta `skill`, no vive en
`.opencode/skills/` y no se registra en el skill registry. Se configura en el cliente y expone herramientas.

| Ítem | Dato |
|---|---|
| Endpoint | `https://mcp.context7.com/mcp` (remoto, transporte HTTP) |
| Herramientas | `resolve-library-id` (nombre de librería → ID) y `query-docs` (documentación y ejemplos de un ID) |
| Credenciales | Ninguna obligatoria: la conexión funciona sin headers (verificado). API key opcional vía `Authorization: Bearer {env:CONTEXT7_API_KEY}` |
| Config viva | `~/.config/opencode/opencode.json` (fuera del repo); el repo solo versiona el ejemplo |

### Cuándo usarlo

- Al escribir `design.md` o deltas de spec que tocan APIs del stack: sesiones y transacciones de SQLAlchemy 2.0,
  `op.execute`/EXCLUDE en Alembic, `Depends`/`BackgroundTasks` en FastAPI, validadores de Pydantic v2.
- Ante cualquier librería o servicio que **no esté en la KB** (por ejemplo, SDK de Mercado Pago en C-11 o
  Google Calendar en C-14).
- **No** para decisiones de dominio: reglas RN-XX, alcance y datos salen de `knowledge-base/`.

### Configuración

1. Copiá el bloque de [`docs/skills-mcp/mcp.json.example`](docs/skills-mcp/mcp.json.example).
2. Pegalo en el `opencode.json` del cliente:
   - **Proyecto**: `opencode.json` en la raíz del repo o `.opencode/opencode.json`.
   - **Global**: `~/.config/opencode/opencode.json` (Windows: `C:\Users\<usuario>\.config\opencode\opencode.json`).
3. Precedencia: **proyecto > global**. Si el mismo servidor está definido en ambos, gana la definición del
   proyecto (y reemplaza el objeto completo). En máquinas administradas, la config del sistema
   (`%ProgramData%\opencode`) tiene precedencia sobre ambas.
4. Reiniciá opencode si estaba abierto y comprobá la conexión.

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "context7": {
      "type": "remote",
      "url": "https://mcp.context7.com/mcp",
      "enabled": true
    }
  }
}
```

> **Versión del esquema**: el ejemplo usa la forma 1.x (`mcp.<nombre>` + `enabled`). opencode 2.2.0 la acepta
> (verificado), y el esquema canónico de 2.x es `mcp.servers.<nombre>` con `disabled` en lugar de `enabled`.
> Si tu cliente es 2.x y preferís el formato nuevo, movés el bloque un nivel abajo; el endpoint y las
> herramientas no cambian.

### Comprobar la conexión

```bash
opencode mcp list
```

Salida esperada (verificada con opencode v2.2.0):

```
✓ context7  connected
```

Después, una llamada real: pedir `resolve-library-id` para `FastAPI` y `query-docs` sobre
`/websites/fastapi_tiangolo`. Si devuelve documentación, el servidor está operativo.

`opencode mcp debug context7` no está disponible en v2.2.0 (`Unknown subcommand "debug"`; la CLI solo expone
`list`, `add`, `auth` y `logout`). [NO VERIFICADO] que exista en otras versiones; si tu build lo tiene, sirve
para probar conectividad y estado de autenticación.

### Solución de problemas

| Síntoma | Causa probable | Verificación / solución |
|---|---|---|
| `opencode mcp list` no muestra `context7` | El bloque no está en la config que lee el cliente, o hay otra config con mayor precedencia | Confirmá desde qué directorio corrés el comando y revisá `opencode.json` / `.opencode/opencode.json`; recordá proyecto > global |
| Aparece `needs authentication` | opencode 2.x intenta OAuth por defecto en servidores remotos | `opencode mcp auth context7` (o `/mcps` y completar el login); Context7 también expone `/mcp/oauth` |
| El servidor figura pero las herramientas no responden | Red, proxy o firewall; timeout de arranque | Probá una llamada real y corré `opencode --print-logs mcp list`; si el arranque tarda, subí `mcp.timeout.startup` |
| `429 Too Many Requests` | Límite anónimo alcanzado [NO VERIFICADO: el número no está publicado en la página de API keys] | Crear una API key en el dashboard de Context7, exportarla en `.env` y pasarla por header `Authorization: Bearer {env:CONTEXT7_API_KEY}` |

### Límites

Solo lectura de documentación pública: no modifica el repo ni la base de datos. **Nunca** se le pasan datos de
pacientes, PHI, credenciales ni dumps (regla dura de `AGENTS.md`). La API key, si se usa, va en `.env` y nunca
al repo. Si el servidor no responde, el trabajo continúa con la KB: el MCP es apoyo, no dependencia de build
ni de tests.

## Estructura del repo

| Directorio / archivo | Qué es |
|----------------------|--------|
| `backend/app/core/` | Core de la fundación C-01: `Settings`, logger JSON sin PHI, correlation IDs, excepciones |
| `backend/app/app.py` | Factory FastAPI (`create_app`) con middleware y mapeo de errores; monta `health`, `auth`, `catalogos` y los routers de C-05 a C-11 (turnos, reserva, lista de espera, ficha, odontograma, presupuesto, caja y señas) |
| `backend/app/main.py` | Entrypoint Uvicorn (`app.main:app`) usado por el contenedor |
| `backend/app/db.py` | Engine/session factories SQLAlchemy 2.0 |
| `backend/app/turnos/` | Dominio C-05: `overlap()`, cálculo de `fin`, 3 alternativas ante 409, máquina de estados, servicio + auditoría |
| `backend/app/reservas/` | Dominio C-06 + catálogo F-02: puertos/adaptadores, disponibilidad pública, verificación, tokens, antispam |
| `backend/app/lista_espera/` | C-07: cola de espera, auto-oferta ante hueco liberado y vencimiento de ofertas |
| `backend/app/ficha_clinica/` | C-08: ficha clínica y consentimiento informado con control de acceso |
| `backend/app/odontograma/` | C-09: odontograma FDI por diente/cara y hallazgos |
| `backend/app/presupuesto/` | C-09: presupuesto con ítems, aceptación y vínculo con el odontograma |
| `backend/app/caja/` | C-10: movimientos multi-medio, imputación de prestaciones, cobros pendientes, anulación y ajustes post-cierre |
| `backend/app/caja/cierre.py` | C-10: cierre diario inmutable con `pg_advisory_xact_lock` y snapshot de totales |
| `backend/app/senas/` | C-11: seña atada al turno, preferencia MP, webhook idempotente, expiración, aplicación a caja y devoluciones |
| `backend/app/routers/` | Routers inyectables por change (`crear_router` / `crear_app…`): `turnos`, `reservas_publicas`, `lista_espera`, `ficha_clinica`, `odontograma`, `presupuesto`, `caja`, `senas`, `senas_internas`, `webhooks_mp` |
| `backend/app/routers/health.py` | `GET /api/health` |
| `backend/app/routers/auth.py` | `/api/auth/login`, `refresh`, `logout`, `me`, `admin-check` (montado) |
| `backend/app/routers/catalogos.py` | CRUD de catálogos y pacientes con RBAC (montado) |
| `backend/app/schemas/` | Schemas Pydantic v2 del borde API (strict donde el contrato lo exige) |
| `backend/app/models/` | Modelos SQLAlchemy (`tenant_id` everywhere, `timestamptz`, CHECKs, RLS) |
| `backend/app/auth/` | Autenticación C-03: Argon2, JWT, refresh tokens, TOTP, rate-limit |
| `backend/alembic/versions/` | 001 núcleo tenant + RLS · 002 catálogo/pacientes · 003 turnos · 004 auth · 005 lista de espera · 006 ficha clínica · 007 odontograma/presupuesto · 008 caja/cierre · 009 señas/pagos MP |
| `backend/seed_test.py` | Seed ficticio idempotente (`aplicar_seed()` + `seed_sql()` para PG real) |
| `backend/requirements.txt` | Pines de runtime verificados |
| `requirements-dev.txt` | Pines de desarrollo y CI |
| `frontend/` | SPA React + TypeScript + Vite, lint/typecheck/test/build. Incluye la landing pública `/r/:tokenTenant` (F-02) y la gestión por token `/r/:tokenTenant/turno/:token` |
| `docs/api-publica-reserva.md` | Contrato público que consume la landing (allow-list y códigos) |
| `docs/decisiones-oq.md` | Resolución de OQ-1..OQ-9 de C-06 |
| `docs/decisiones-po.md` | Decisiones de producto PO-01/PO-03/PO-06 y las OQ de C-09, C-10 y C-11 |
| `docker-compose.yml` | Servicios locales `db`, `redis`, `migrate`, `api` y `web` con healthchecks |
| `.env.example` | Variables de entorno ejemplo sin secretos reales |
| `.github/workflows/quality.yml` | CI paralela: backend, frontend y Compose |
| `tests/` | Suite completa por change: fundación, auth, catálogos, turnos, reservas, lista de espera, ficha, odontograma, presupuesto, caja, señas, migraciones y aislamiento |
| `openspec/specs/` | 21 specs vivas (una por capability) |
| `openspec/changes/archive/` | 21 changes archivados con proposal, design, specs y tasks |
| `docs/foundation/bootstrap.md` | Setup, verificación, compose, troubleshooting |
| `docs/foundation/verification-report.md` | Evidencia ejecutable del cierre C-01 |
| `docs/discovery/` | Informe y checklist de Discovery |
| `docs/skills-mcp/` | TP «skill propia + MCP»: ficha de investigación, ejemplo de configuración de Context7, vendor de la skill creadora y evidencias |
| `knowledge-base/` | Dominio: visión, stack, actores/RBAC, modelo de datos, reglas de negocio, funcionalidades, flujos, arquitectura, decisiones, preguntas abiertas, integraciones |
| `CHANGES.md` | Índice canónico de los 17 changes y su estado |

## Estado del ciclo C-01 (`foundation-setup`)

- **Aislamiento multi-tenant y autenticación** quedan fuera de este change: llegan en C-02 y C-03 respectivamente.
- **C-01** aporta la base reproducible: FastAPI con `/api/health`, SPA React + TypeScript + Vite, PostgreSQL/Redis en Compose, CI paralela, Alembic inicializado y `mypy`/`ruff`.
- **Verificación ejecutable**: [`docs/foundation/verification-report.md`](docs/foundation/verification-report.md).
- **Archivo archivado**: `openspec/changes/archive/2026-11-03-c-01-foundation-setup/`; spec principal en `openspec/specs/foundation-setup/spec.md`; 8 requisitos aprobados.
- **Desvío documentado**: 001 y 002 están implementadas; 003 y 004 también.
- **Continuación histórica**: en ese corte el siguiente change era C-03 `auth-rbac-auditoria` (cerrado el 2026-11-03).

## Estado del ciclo C-04 (`catalogos-pacientes-base`)

- **Estado**: implementado, verificado y archivado el 2026-11-03; modelos de profesionales, sillones, prestaciones, horarios, bloqueos y pacientes.
- **Archivo**: `openspec/changes/archive/2026-11-03-c-04-catalogos-pacientes-base/`.
- **Migración 002**: catálogo base con RLS forzada.
- **Seed**: `seed_catalogo` materializa Sillón 1 y las dos prestaciones base desde la configuración del tenant.
- **Verificación ejecutable**: [`docs/foundation/verification-c04.md`](docs/foundation/verification-c04.md).
- **Deuda declarada**: los endpoints de horarios/bloqueos quedan para la evolución de C-04/C-05; los valores de duración del catálogo son provisionales hasta PO-01.

## Estado del ciclo C-03 (`auth-rbac-auditoria`)

- **Estado**: implementado, verificado y archivado el 2026-11-03; login Argon2, access JWT, refresh rotado, logout, `/me`, 2FA TOTP, RBAC y auditoría de accesos.
- **Archivo**: `openspec/changes/archive/2026-11-03-c-03-auth-rbac-auditoria/`.
- **Migración 004**: `refresh_tokens` con RLS y `two_factor_secret` cifrado.
- **Verificación ejecutable**: [`docs/foundation/verification-c03.md`](docs/foundation/verification-c03.md) — 152 tests, RLS real, migración upgrade/downgrade y rate-limit.
- **Deuda declarada**: rate-limit en proceso; C-05 conserva headers provisorios hasta el change que migre esas rutas.

## Estado del ciclo C-02 (`core-models-multitenant`)

- **Estado**: implementado, verificado y archivado el 2026-11-03; modelos `Tenant`, `Usuario`, `Auditoria` y `ParametroTenant`, migración 001 y RLS forzada.
- **Archivo**: `openspec/changes/archive/2026-11-03-c-02-core-models-multitenant/`.
- **Roles**: `turnos_owner` para migraciones/seed; `turnos_app` para la API, sin UPDATE/DELETE sobre auditoría.
- **Verificación ejecutable**: [`docs/foundation/verification-c02.md`](docs/foundation/verification-c02.md) — 130 tests, RLS contra PostgreSQL real, upgrade/downgrade/re-upgrade y seed idempotente.
- **Deuda declarada**: C-04 materializó el catálogo; la duración demo de 30 min es provisional hasta que el dueño defina el catálogo real.

## Estado de la fundación visual (F-01)

- **Estado**: implementado, verificado y archivado el 2026-11-03; design system, router, home, login, shell interno protegido, 404 y skill `visual-turnos`.
- **Archivo**: `openspec/changes/archive/2026-11-03-frontend-visual-foundation/`.
- **Evidencia**: [`docs/design/screenshots/`](docs/design/screenshots/) (375/768/1440) · auditoría Figma/Stitch/code-first en [`docs/design/README.md`](docs/design/README.md).
- **MCP de diseño**: Figma documentado como primario opcional (`https://mcp.figma.com/mcp`), Stitch como opcional; esta pasada fue code-first porque no había MCP autenticado.
- **Alcance**: sólo fundación + login/404; agenda, pacientes, reserva, caja y reportes se construyen como pages por change.

## Estado del ciclo C-05 (`turnos-anti-solape`)

- **Estado: archivado** el 2026-10-01 y **reimplementado en Python** el 2026-10-02 (spec intacto). En `CHANGES.md` figura `[x]` completado con nota de reimplementación.
- **Spec aprobado**: [`openspec/specs/turnos-anti-solape/spec.md`](openspec/specs/turnos-anti-solape/spec.md) — 6 requisitos (anti-solape por profesional/sillón con 409 + 3 alternativas, adyacencia exacta, cancelados/reprogramados que liberan hueco, sobreturno explícito auditado, cancelar/reprogramar con anticipación).
- **Tests**: [`tests/`](tests/) — 104/104 en verde con `py -m pytest tests/ -q`.
- **Desvíos documentados del ciclo**: sin PostgreSQL en el entorno (revisión 003 verificada por tests estructurales, no contra DB viva); tasks 4.1–4.3 green-first de aceptación (RED por módulo observado en 1.x–3.x, y 4.1 aportó un fallo real que se corrigió); sin chequeo automático de hints (para el CI de C-01). Detalle en `reimplementacion-python.md` del archive.
- **Continuación histórica**: en ese corte el siguiente change era C-06 `reserva-online-publica` (cerrado el 2026-11-05).

## Estado del ciclo C-06 (`reserva-online-publica`)

- **Estado: archivado** el 2026-11-05. Implementa disponibilidad server-side, reserva sin login con token por turno, cancelar/reprogramar con anticipación exacta y anti-spam (captcha) con rate-limit.
- **Spec aprobado**: [`openspec/specs/reserva-publica/spec.md`](openspec/specs/reserva-publica/spec.md).
- **Contrato**: [`docs/api-publica-reserva.md`](docs/api-publica-reserva.md). OQ resueltas: [`docs/decisiones-oq.md`](docs/decisiones-oq.md).
- **Archivo**: `openspec/changes/archive/2026-11-05-c-06-reserva-online-publica/`.
- **Deuda declarada (D9)**: el dominio usa adaptadores en memoria inyectables; el wiring SQLAlchemy real (tablas de tokens/verificación y conexión al catálogo C-04) es un follow-up explícito.

## Estado de la landing pública (F-02)

- **Estado: archivado** el 2026-11-05. Landing mobile-first `/r/:tokenTenant` que consume la API pública: catálogo → prestación → huecos → nombre/teléfono/verificación → confirmación con token; gestión por token en `/r/:tokenTenant/turno/:token` (consultar/cancelar/reprogramar).
- **Enabler backend incluido**: `GET /api/publico/{tokenTenant}/catalogo` (OQ-F1), solo lectura, tenant-scoped, `404` uniforme y allow-list sin PHI.
- **Archivo**: `openspec/changes/archive/2026-11-05-f-02-reserva-publica-landing/`; capturas en `.../mockups/previews/`.
- **Pendiente declarado**: proveedor real de captcha (hoy placeholder accesible), persistencia SQL real de la reserva (hoy la demo corre en memoria) y WhatsApp de producción (la demo usa Twilio Sandbox).

## Estado de los ciclos C-07 a C-11

- **C-07 `lista-espera-auto-oferta`** — archivado el 2026-11-05. Cola de espera por prestación/profesional, auto-oferta ante hueco liberado, aceptación/rechazo por token y vencimiento de la oferta con reintento al siguiente candidato. 42 tests nuevos.
- **C-08 `ficha-clinica-consentimiento`** — archivado el 2026-11-06. Ficha clínica con control de acceso por rol y consentimiento informado versionado. 46 tests nuevos.
- **C-09 `odontograma-presupuesto`** — archivado el 2026-11-12. Odontograma FDI por diente/cara, presupuesto con ítems y aceptación, e imputación posterior a caja. Migración 007. Suite 416 passed + 10 skipped local; 426 + 0 con PostgreSQL.
- **C-10 `caja-cierre-diario`** — archivado el 2026-11-13. Movimientos multi-medio, imputación de prestaciones y obras sociales, cobros pendientes, anulación con motivo, **cierre diario inmutable** con `pg_advisory_xact_lock` y snapshot de totales, ajustes post-cierre en ledger separado y reportes base. Migración 008. Suite 552 + 27 local; 579 + 0 con PostgreSQL.
- **C-11 `senas-mercadopago`** — archivado el 2026-11-13. Seña atada 1:1 al turno (monto por prestación con override, truncado hacia abajo), preferencia de Mercado Pago con reintento y backoff, token público opaco, **webhook idempotente que verifica HMAC y re-consulta el pago** (nunca confía en el cuerpo; `503` fail-closed sin secreto), expiración atómica con auto-oferta a C-07, aplicación a caja vía C-10 con bloqueo por presupuesto aceptado, devolución como estado contable y transferencia de la seña al reprogramar. Migración 009. Suite 678 + 42 local; 720 + 0 con PostgreSQL.
- **Montaje demo (F-03, F-04, F-05)** — la API real expone C-05 a C-11 sobre un composition root en memoria (`backend/app/demo.py`): reserva pública con seña, lista de espera, ficha y consentimiento, odontograma, presupuesto, caja y señas. El estado se pierde al reiniciar y las aceptaciones de presupuesto no impactan caja.
- **C-12 `obras-sociales-liquidacion`** — archivado el 2026-11-15. Catálogo de obras sociales por tenant, cobertura configurable por (OS × prestación) con modo `PORCENTAJE`/`MONTO` y tope, cálculo de tramos para presupuestos, liquidación por período de turnos `PRESENTE`, cierre inmutable y export CSV. Migración 010. La cobertura es **configurada, no validada en vivo** (RN-OS-01).
- **C-14 `google-calendar-sync`** — archivado el 2026-11-15. Link OAuth por profesional, push idempotente de turnos, eventos externos como bloqueo informativo, conflicto a favor del sistema, cola con backoff y token revocado sin romper la agenda. Migración **011** (renumerada mientras C-13 estaba bloqueado).
- **C-13 `whatsapp-recordatorios`** — archivado el 2026-11-16. Recordatorios idempotentes, Twilio Sandbox, webhook firmado con respuestas `SI`/`NO`, confirmación/cancelación con auto-oferta a C-07, fallback email y recall clínico. Migración **012**.
- **C-15 `admin-plataforma-exportacion` (parcial)** — archivado el 2026-11-15. Configuración del tenant con whitelist, usuarios con Argon2, exportación JSON/CSV sin secretos y KPIs base. Fuera de alcance: superadmin, respaldo automático y ocupación.

## Alcance completo vs pendiente (TPI)

| Área | Estado |
|---|---|
| Fundación (C-01, C-02, C-03, C-04) | ✅ archivada y verificada |
| Agenda anti-solape (C-05) | ✅ archivada y reimplementada en Python |
| Reserva online + landing (C-06, F-02) | ✅ archivadas, con tests de backend y frontend |
| Fundación visual (F-01) | ✅ archivada |
| Lista de espera con auto-oferta (C-07) | ✅ archivada |
| Ficha clínica y consentimiento (C-08) | ✅ archivada |
| Odontograma y presupuesto (C-09) | ✅ archivada |
| Caja y cierre diario (C-10) | ✅ archivada |
| Señas con Mercado Pago (C-11) | ✅ archivada |
| Skill propia + MCP | ✅ `revisor-escenarios-turnos`, `visual-turnos` y MCP Context7 documentados y aplicados |
| C-12 obras sociales y liquidación | ✅ archivada |
| C-14 Google Calendar sync | ✅ archivada |
| C-13 WhatsApp con Twilio | ✅ archivada (sandbox para demo; producción pendiente) |
| C-15 admin, exportación y KPIs (parcial) | ✅ archivada (superadmin, respaldo y ocupación fuera de alcance) |
| SPA interno (F-06) | ✅ agenda, pacientes, clínica, caja, señas, WhatsApp, OS, calendario y configuración |
| Montaje de routers en `create_app` | ✅ C-05…C-15 (adaptadores en memoria) |

## Límites declarados del alcance

El TPI admite alcance parcial, pero exige declararlo con precisión. Estos son los límites reales al
2026-11-16, sin maquillaje:

1. **El bootstrap de la API monta C-05 a C-15.** `backend/app/app.py` registra `health`, `auth`,
   `catalogos`, turnos, reserva pública, lista de espera, ficha clínica, odontograma, presupuesto,
   caja, señas, obras sociales, Google Calendar y WhatsApp, todos sobre adaptadores en memoria. Los
   repositorios SQLAlchemy de caja, presupuesto, señas y WhatsApp existen y están probados contra
   PostgreSQL, pero no reemplazan a los adaptadores en el camino de la API.
   Consecuencia concreta: por `uvicorn` se puede recorrer el núcleo completo, pero el estado se pierde
   al reiniciar y las aceptaciones de presupuesto no escriben en caja.
2. **La persistencia real solo aplica a `auth` y `catalogos`.** El resto de los dominios corre sobre
   puertos con adaptadores en memoria en tests y en la demo: el estado se pierde al reiniciar. Los
   repositorios SQL están escritos y probados contra PostgreSQL, pero no reemplazan a los adaptadores en
   el camino de la API.
3. **La UI interna cubre C-05 a C-15, incluido WhatsApp.** El SPA permite operar agenda, pacientes,
   clínica, caja, señas, WhatsApp, obras sociales, calendario, configuración, exportación y KPIs.
   Quedan fuera el superadmin cross-tenant y las pantallas de edición avanzada.
4. **Integraciones externas.** Mercado Pago y Google Calendar se ejercitan con adaptadores fake que
   respetan el contrato. WhatsApp se integra con **Twilio Sandbox** cuando `WA_PROVIDER=twilio` y las
   credenciales están en `.env`; sin credenciales usa `PasarelaWhatsAppFake`. El sandbox sólo envía a
   números unidos y no es producción.
5. **Los bloqueos de Google Calendar no alteran la disponibilidad de C-06.** Se guardan y se consultan
   por `/api/calendar/bloqueos`, pero el motor de reservas todavía no los lee; cablearlos es un
   follow-up que toca C-05/C-06.
6. **La cobertura de obras sociales es configurada, no validada.** No hay WS/SOAP con la OS (PO-04) ni
   aranceles por OS (PO-08): la liquidación usa `prestaciones.precio_base` y declara
   `validada_en_vivo = false`.
7. **Reembolso de seña manual.** El estado `DEVUELTA` es contable: el reintegro en Mercado Pago lo ejecuta
   una persona desde el panel del proveedor. No hay API de reembolsos.
8. **El ingreso de la seña queda con `tramo=NULL`.** `ServicioCaja.registrar_movimiento` no expone ese
   parámetro y C-11 no puede escribir `movimientos_caja` directo. Corregirlo es un cambio en C-10.
9. **El access log del servidor HTTP puede registrar el token público** de `/pagar/:tokenSena`. El log
   estructurado de la aplicación lo redacta y hay test que lo verifica; la redacción del access log es
   de infraestructura.
10. **Admin parcial**: no hay superadmin cross-tenant, job de respaldo ni KPI de ocupación (requiere
   modelo de capacidad por horarios).

## Datos y secretos

- **Datos ficticios**: seed (`backend/seed_demo.py`) y tests usan datos inventados (1 tenant demo, profesionales/sillones/prestaciones/pacientes de prueba). NUNCA usar datos reales de pacientes en desarrollo, tests ni demos; nada de PHI en logs.
- **Secretos**: nada commiteado. No hay `.env`; el repo versiona únicamente [`.env.example`](.env.example) con placeholders de desarrollo sin valores productivos. `.gitignore` excluye `.env`, `.env.local`, `__pycache__/` y `.pytest_cache/`. Las variables reales (`MP_*`, `WA_*`, `GCAL_*`, etc.) se documentan cuando esos changes las necesitan. CI ejecuta `tools/secret_scan.py` para no incorporar patrones comunes de claves.
