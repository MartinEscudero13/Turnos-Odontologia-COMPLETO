# Turnos-Odontologia

SaaS multi-tenant argentino de agenda odontológica: turnos con anti-solape real, reserva online, WhatsApp, Mercado Pago y obras sociales.

- Descubrimiento del problema y alcance: [`docs/discovery/`](docs/discovery/) (informe + checklist).
- Fuente de verdad del dominio (actores, datos, reglas RN-XX, historias US-XXX, arquitectura): [`knowledge-base/`](knowledge-base/README.md).
- Plan de implementación por changes: [`CHANGES.md`](CHANGES.md). Reglas para agentes: [`AGENTS.md`](AGENTS.md).

## Prerrequisitos

| Requisito | Versión | Notas |
|-----------|---------|-------|
| Node.js | 20+ | `package.json` no declara campo `engines`; el stack del proyecto exige Node 20 LTS (`AGENTS.md`). Verificado con Node **v24.16.0**. |
| npm | 10+ | Verificado con npm **11.13.0**. |
| PostgreSQL | 15+ | Solo necesario desde la persistencia real (migraciones Prisma). El ciclo C-05 corre sin Postgres (ver Estado). |

Verificá tu entorno:

```bash
node --version
npm --version
```

## Instalación

```bash
git clone <url-del-repo>
cd Turnos-Odontologia
npm install
```

## Tests

```bash
npx vitest run
```

Salida esperada (verificada): **13 archivos, 79 tests, todos en verde** (`Test Files 13 passed`, `Tests 79 passed`).

## Chequeo de tipos

```bash
npx tsc --noEmit
```

Salida esperada (verificada): sin errores (exit 0). Tipado estricto (`strict`, sin `any`).

## Estructura del repo

| Directorio / archivo | Qué es |
|----------------------|--------|
| `src/turnos/` | Dominio C-05: `overlap()`, cálculo de `fin`, 3 alternativas ante 409, máquina de estados, servicio con zod + auditoría |
| `tests/` | 13 suites vitest del ciclo C-05 (solape, fin, alternativas, estados, sobreturno, auditoría, concurrencia, 409, API, cancelar/reprogramar, migración, seed, regresión) |
| `prisma/` | `schema.prisma`, `migrations/` (migración 003: tabla `turnos` + EXCLUDE anti-solape + RLS) y `seed-test.ts` |
| `openspec/specs/turnos-anti-solape/` | Spec vigente de C-05 (requisitos y escenarios aprobados) |
| `openspec/changes/archive/2026-10-01-c-05-turnos-anti-solape/` | Change C-05 archivado: `proposal.md`, `design.md`, `tasks.md`, delta de specs, `explore-notes.md` |
| `docs/discovery/` | Informe y checklist de Discovery |
| `knowledge-base/` | Dominio: visión, stack, actores/RBAC, modelo de datos, reglas de negocio, funcionalidades, flujos, arquitectura, decisiones, preguntas abiertas, integraciones |
| `CHANGES.md` | Índice canónico de los 15 changes y su estado |
| `package.json` / `tsconfig.json` / `package-lock.json` | Dependencias (`zod`, `vitest`, `typescript`, `prisma`), TS estricto |
| `node_modules/` / `dist/` | Generados (no versionados) |

## Estado del ciclo C-05 (`turnos-anti-solape`)

- **Estado: archivado** el 2026-10-01 (commits `1193b77` apply + `109c8a8` archive). En `CHANGES.md` figura `[x]` completado.
- **Spec aprobado**: [`openspec/specs/turnos-anti-solape/spec.md`](openspec/specs/turnos-anti-solape/spec.md) — 6 requisitos (anti-solape por profesional/sillón con 409 + 3 alternativas, adyacencia exacta, cancelados/reprogramados que liberan hueco, sobreturno explícito auditado, cancelar/reprogramar con anticipación).
- **Tests**: [`tests/`](tests/) — 79/79 en verde con `npx vitest run`.
- **Desvíos documentados del ciclo**: sin PostgreSQL en el entorno (migración 003 verificada por tests, no contra DB viva) y fase RED no observada en los tasks 3.2–4.3 (código y test escritos juntos en la sesión apply).
- **Siguiente**: `C-06 reserva-online-publica` (depende de C-05 archivado).

## Datos y secretos

- **Datos ficticios**: seed (`prisma/seed-test.ts`) y tests usan datos inventados (1 tenant, profesional/sillón/prestación de prueba). NUNCA usar datos reales de pacientes en desarrollo, tests ni demos; nada de PHI en logs.
- **Secretos**: nada commiteado. No hay `.env` ni `.env.example` en el repo; `.gitignore` excluye `.env`, `.env.local`, `node_modules/` y `dist/`. Las variables reales (`DATABASE_URL`, `AUTH_SECRET`, `MP_*`, `WA_*`, etc.) se documentarán en el change que las necesite (C-01/C-10/C-11/C-13 según `CHANGES.md`).
