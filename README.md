# Turnos-Odontologia

SaaS multi-tenant argentino de agenda odontológica: turnos con anti-solape real, reserva online, WhatsApp, Mercado Pago y obras sociales.

## Equipo

Trabajo grupal de **Martin Escudero** y **Lautaro Naranjo**. Alcance, roles y aclaración sobre entregas anteriores: [`AUTHORS.md`](AUTHORS.md).

- Descubrimiento del problema y alcance: [`docs/discovery/`](docs/discovery/) (informe + checklist).
- Fuente de verdad del dominio (actores, datos, reglas RN-XX, historias US-XXX, arquitectura): [`knowledge-base/`](knowledge-base/README.md).
- Plan de implementación por changes: [`CHANGES.md`](CHANGES.md). Reglas para agentes: [`AGENTS.md`](AGENTS.md).
- Integración MCP (Context7) y documentación del TP «skill propia + MCP»: [`docs/skills-mcp/`](docs/skills-mcp/README.md).
- Fundación C-01: prerequisitos, arquitectura, setup, `docker-compose` y comandos de verificación: [`docs/foundation/bootstrap.md`](docs/foundation/bootstrap.md).

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
git clone <url-del-repo>
cd Turnos-Odontologia
py -m pip install -r requirements-dev.txt
cd frontend
npm ci
cd ..
cp .env.example .env
docker compose up -d --build
```

Para solo compilar o inspeccionar la base compilada, ver `docs/foundation/bootstrap.md` y `scripts/verify-foundation.ps1`.

## Tests

```bash
py -m pytest tests/ -q
py -m ruff check .
py -m mypy --config-file pyproject.toml

cd frontend
npm run lint
npm run typecheck
npm test
npm run build
```

Estado verificado al cierre de C-01: backend/frontend verdes, `secret_scan` OK, `openspec validate c-01-foundation-setup --strict` en verde y smoke test de API/web con health `UP`.

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
| `backend/app/routers/health.py` | `GET /api/health` |
| `backend/app/db.py` | Engine/session factories SQLAlchemy 2.0 |
| `backend/app/app.py` | Factory FastAPI y middleware |
| `backend/app/turnos/` | Dominio C-05: `overlap()`, cálculo de `fin`, 3 alternativas ante 409, máquina de estados, servicio + auditoría |
| `backend/app/schemas/` | Schemas Pydantic v2 del borde API (strict donde el contrato lo exige) |
| `backend/app/models/` | Modelos SQLAlchemy (`tenant_id` everywhere, `timestamptz`, CHECKs) |
| `backend/app/auth/` | Autenticación C-03: Argon2, JWT, refresh tokens, TOTP, rate-limit |
| `backend/app/models/catalogos.py` | Profesionales, sillones, prestaciones, horarios, bloqueos y pacientes C-04 |
| `backend/app/routers/catalogos.py` | CRUD de catálogos y pacientes con RBAC |
| `backend/app/routers/auth.py` | Endpoints `/api/auth/login`, `refresh`, `logout`, `me`, `admin-check` |
| `backend/app/routers/` | Router FastAPI `/api/turnos` + `/api/auth`; C-05 mantiene actor por headers provisorio |
| `backend/alembic/versions/` | Migraciones: 001 núcleo tenant + RLS, 002 catálogo C-04, 003 turnos, 004 auth |
| `backend/seed_test.py` | Seed ficticio idempotente (`aplicar_seed()` + `seed_sql()` para PG real) |
| `backend/requirements.txt` | Pines de runtime verificados |
| `requirements-dev.txt` | Pines de desarrollo y CI |
| `frontend/` | SPA React + TypeScript + Vite, lint/typecheck/test/build |
| `docker-compose.yml` | Servicios locales `api`, `web`, `db` y `redis` con healthchecks |
| `.env.example` | Variables de entorno ejemplo sin secretos reales |
| `.github/workflows/quality.yml` | CI paralela: backend, frontend y Compose |
| `tests/` | Suite histórica C-05 más tests de fundación C-01 |
| `openspec/specs/turnos-anti-solape/` | Spec vigente de C-05 (requisitos y escenarios aprobados) |
| `openspec/changes/` | Planning artifacts; C-01 archived al cerrar esta entrega |
| `docs/foundation/bootstrap.md` | Setup, verificación, compose, troubleshooting |
| `docs/foundation/verification-report.md` | Evidencia ejecutable del cierre C-01 |
| `docs/discovery/` | Informe y checklist de Discovery |
| `docs/skills-mcp/` | TP «skill propia + MCP»: ficha de investigación, ejemplo de configuración de Context7, vendor de la skill creadora y evidencias |
| `knowledge-base/` | Dominio: visión, stack, actores/RBAC, modelo de datos, reglas de negocio, funcionalidades, flujos, arquitectura, decisiones, preguntas abiertas, integraciones |
| `CHANGES.md` | Índice canónico de los 15 changes y su estado |

## Estado del ciclo C-01 (`foundation-setup`)

- **Aislamiento multi-tenant y autenticación** quedan fuera de este change: llegan en C-02 y C-03 respectivamente.
- **C-01** aporta la base reproducible: FastAPI con `/api/health`, SPA React + TypeScript + Vite, PostgreSQL/Redis en Compose, CI paralela, Alembic inicializado y `mypy`/`ruff`.
- **Verificación ejecutable**: [`docs/foundation/verification-report.md`](docs/foundation/verification-report.md).
- **Archivo archivado**: `openspec/changes/archive/2026-11-03-c-01-foundation-setup/`; spec principal en `openspec/specs/foundation-setup/spec.md`; 8 requisitos aprobados.
- **Desvío documentado**: 001 y 002 están implementadas; 003 y 004 también.
- **Siguiente**: C-03 `auth-rbac-auditoria`.

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

## Estado del ciclo C-05 (`turnos-anti-solape`)

- **Estado: archivado** el 2026-10-01 y **reimplementado en Python** el 2026-10-02 (spec intacto). En `CHANGES.md` figura `[x]` completado con nota de reimplementación.
- **Spec aprobado**: [`openspec/specs/turnos-anti-solape/spec.md`](openspec/specs/turnos-anti-solape/spec.md) — 6 requisitos (anti-solape por profesional/sillón con 409 + 3 alternativas, adyacencia exacta, cancelados/reprogramados que liberan hueco, sobreturno explícito auditado, cancelar/reprogramar con anticipación).
- **Tests**: [`tests/`](tests/) — 104/104 en verde con `py -m pytest tests/ -q`.
- **Desvíos documentados del ciclo**: sin PostgreSQL en el entorno (revisión 003 verificada por tests estructurales, no contra DB viva); tasks 4.1–4.3 green-first de aceptación (RED por módulo observado en 1.x–3.x, y 4.1 aportó un fallo real que se corrigió); sin chequeo automático de hints (para el CI de C-01). Detalle en `reimplementacion-python.md` del archive.
- **Siguiente**: `C-06 reserva-online-publica` (depende de C-05 archivado).

## Datos y secretos

- **Datos ficticios**: seed (`backend/seed_test.py`) y tests usan datos inventados (1 tenant demo, profesional/sillón/prestación de prueba). NUNCA usar datos reales de pacientes en desarrollo, tests ni demos; nada de PHI en logs.
- **Secretos**: nada commiteado. No hay `.env`; el repo versiona únicamente [`.env.example`](.env.example) con placeholders de desarrollo sin valores productivos. `.gitignore` excluye `.env`, `.env.local`, `__pycache__/` y `.pytest_cache/`. Las variables reales (`MP_*`, `WA_*`, `GCAL_*`, etc.) se documentan cuando esos changes las necesitan. CI ejecuta `tools/secret_scan.py` para no incorporar patrones comunes de claves.




