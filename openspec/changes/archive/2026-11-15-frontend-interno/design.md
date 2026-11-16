# Design — Frontend interno

## Context

El SPA usa React 18 + TypeScript + Vite. El backend mezcla JWT (auth/catálogos) con actor por headers
(C-05…C-15). Ver `proposal.md`.

## Decisions

**D1 — Contexto de API único.**
`api.ts` guarda actor + token y agrega `X-Tenant-Id`, `X-User-Id`, `X-Rol`, `X-Profesional-Id` y
`Authorization` en cada request. Un solo `ApiError` traduce `{detalle, codigo}`.

**D2 — Sesión persistente.**
`AuthContext` guarda la sesión en `localStorage`. El login real llama `/api/auth/login` y `/api/auth/me`.
El botón demo usa las credenciales sembradas; si el seed no corrió, muestra un error accionable.

**D3 — Seed y Compose.**
`seed_demo.py` es idempotente y crea tenant, 3 usuarios, 2 profesionales, 2 sillones, 2 prestaciones y 2
pacientes ficticios. Compose agrega el servicio `migrate` (alembic + seed) y la API espera su éxito.

**D4 — Una página por módulo.**
Rutas `/app/agenda`, `/app/pacientes`, `/app/clinica`, `/app/caja`, `/app/senas`,
`/app/obras-sociales`, `/app/calendario`, `/app/config`. Clínica usa `?paciente=<id>` para el historial.

**D5 — UI de operación, no de marketing.**
Tablas con acciones, formularios compactos, métricas y estados con badges. Se reutilizan tokens y
componentes de F-01; se agregan estilos de tabla y formulario responsive.

**D6 — Descargas autenticadas.**
CSV/JSON se piden con `fetch` + headers y se descargan como blob; un `<a href>` directo perdería el
actor y el JWT.

## Risks / Trade-offs

- El token de acceso puede vencer en una sesión larga; no hay refresh automático en el SPA.
- La UI no pagina listados: es demo de 1–3 sillones.
- Las acciones clínicas requieren elegir profesional; no se autoselecciona por sesión.
- El login demo depende del seed; sin Compose hay que correr `seed_demo.py`.
- No hay UI de WhatsApp/C-13 (bloqueado por PO-03).

## Verification

- `npm run typecheck`, `npm run lint`, `npm test`, `npm run build`.
- Seed idempotente + login + endpoints internos contra PostgreSQL real.
- `ruff`/`mypy` del backend y `openspec validate --all --strict`.
