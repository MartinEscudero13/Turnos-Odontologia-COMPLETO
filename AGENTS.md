# Turnos-Odontologia — Instrucciones para Agentes

> Este archivo (y su copia `CLAUDE.md`) es lo PRIMERO que todo agente lee al entrar al repo.
> Generado a partir de `knowledge-base/` y `CHANGES.md`. No editar a mano sin re-sincronizar ambos archivos.

---

## Continuidad del equipo

- Entrada corta para Lautaro: [`CONTINUAR.md`](CONTINUAR.md).
- Contexto extendido de entorno: [`docs/equipo/guia-lautaro.md`](docs/equipo/guia-lautaro.md).
- Alcance y autoría: [`AUTHORS.md`](AUTHORS.md).
- **C-02, C-03 y C-04 ya están archivados; C-06 `reserva-online-publica` está desbloqueado.**
- Los changes **C-01 a C-04** y **F-01** corresponden a Martin Escudero; **C-06** y la pieza skill+MCP del TP2 corresponden a Lautaro Naranjo.

---

## Stack Tecnológico

| Capa | Tecnología | Versión |
|------|------------|---------|
| Backend API | FastAPI (Python), SQLAlchemy ORM, migraciones Alembic | Python 3.12+, FastAPI vigente |
| Frontend SPA | React + TypeScript + Vite | React 18+, Vite 5+ |
| Base de datos | PostgreSQL con aislamiento por tenant (`tenant_id` + Row-Level Security) | PostgreSQL 15+ |
| Colas / async | Redis (workers: recordatorios, auto-oferta, reintentos) | Redis 7+ |
| Auth / sesión | JWT (access corto + refresh rotado), 2FA para roles internos | — |
| Pagos | Mercado Pago (Checkout Pro / link de pago + webhooks) | API v1 vigente |
| Mensajería | WhatsApp Business Cloud API oficial (proveedor/BSP a definir) + email fallback (SMTP) | Cloud API vigente |
| Calendario | Google Calendar API v3 (OAuth2 por profesional, sync bidireccional) | v3 |
| Deploy | Contenedores Docker + Compose (api/web/db/redis) + PostgreSQL gestionado con backup diario | — |
| Observabilidad | Logs estructurados + auditoría en DB + alertas de webhooks caídos | — |

Detalle completo: [knowledge-base/02_descripcion_general.md](knowledge-base/02_descripcion_general.md)

---

## Base de Conocimiento

La fuente de verdad del dominio vive en `knowledge-base/`. **Leé el archivo relevante ANTES de implementar.**

| Archivo | Cuándo leerlo |
|---------|---------------|
| [01_vision_y_objetivos.md](knowledge-base/01_vision_y_objetivos.md) | Entender propósito, alcance v1.0 y métricas |
| [02_descripcion_general.md](knowledge-base/02_descripcion_general.md) | Stack, arquitectura general, integraciones y API |
| [03_actores_y_roles.md](knowledge-base/03_actores_y_roles.md) | Auth, RBAC, permisos y rutas públicas |
| [04_modelo_de_datos.md](knowledge-base/04_modelo_de_datos.md) | Entidades, ERD, migraciones, seed |
| [05_reglas_de_negocio.md](knowledge-base/05_reglas_de_negocio.md) | Reglas codificadas (RN-XX) |
| [06_funcionalidades.md](knowledge-base/06_funcionalidades.md) | Historias de usuario por épica (US-001…US-052) |
| [07_flujos_principales.md](knowledge-base/07_flujos_principales.md) | Flujos E2E (reserva, WA, caja, lista de espera) |
| [08_arquitectura_propuesta.md](knowledge-base/08_arquitectura_propuesta.md) | Patrones, estructura, env vars, seguridad |
| [09_decisiones_y_supuestos.md](knowledge-base/09_decisiones_y_supuestos.md) | Decisiones DD-01…DD-06 y supuestos antes de proponer un change |
| [10_preguntas_abiertas.md](knowledge-base/10_preguntas_abiertas.md) | ⚠️ Inconsistencias a resolver ANTES de codear |
| [11_integraciones.md](knowledge-base/11_integraciones.md) | WA / MP / GCal / OS / ARCA: alcance v1 vs roadmap + guion de demo |
| [README.md](knowledge-base/README.md) | Índice de la KB y quick start para desarrolladores |

> ⚠️ Resolver las preguntas de prioridad **Alta** de `10_preguntas_abiertas.md` antes de arrancar el primer change.

---

## Skills Disponibles

| Agente | Rol | Skills que carga |
|--------|-----|------------------|
| **Backend Core** | Postgres multi-tenant / SQLAlchemy / RLS / anti-solape + debugging root-cause | `supabase-postgres-best-practices`, `prisma-postgres` (NO APLICABLE con el stack actual — no usar), `systematic-debugging` |
| **Backend Aux** | Regresiones duras (cancelación, reprogramación, lista de espera) | `diagnosing-bugs` |
| **Frontend** | Reserva 24/7 y agenda (React + Vite, diseño mobile-first, a11y/UX, shadcn/ui) | `vercel-react-best-practices`, `frontend-design`, `web-design-guidelines`, `shadcn` |
| **Orquestación** | SDD / OPSX / docs (fases de fundación) | `discovery-research`, `kb-creator`, `roadmap-generator`, `skill-registry`, `agent-instruction` |
| **Proyecto** | Auditar specs de turnos antes de implementar | `revisor-escenarios-turnos` (propia, versionada en el repo) |
| **Proyecto visual** | Diseñar/rediseñar/auditar páginas y sistema visual | `visual-turnos` (propia, versionada en el repo; opcionalmente Figma/Stitch MCP) |

Cargá la skill correspondiente al contexto ANTES de escribir código.

> Los compact rules de cada skill los resuelve el orquestador desde `.atl/skill-registry.md` (generado por `skill-registry`; **versionado en el repo** — sección `## Project Skills` para las skills propias). Esta tabla solo mapea skill→rol.

### Skill propia: `revisor-escenarios-turnos`

Vive en `.opencode/skills/revisor-escenarios-turnos/SKILL.md` y está versionada en el repo.

- **Cuándo usarla**: al preparar o revisar un change de turnos (`/opsx:propose`, `/opsx:verify`), antes de
  escribirlo. Es obligatoria antes de `/opsx:apply` en cualquier change que toque agenda, turnos, anticipación,
  pagos, caja, obras sociales o lista de espera.
- **Qué necesita**: la ruta del change, la capability afectada y la lista de RN del scope (sale de
  "Leer antes" en `CHANGES.md`). Si falta alguno, lo pide; no completa el scope solo.
- **Qué devuelve**: tabla de cobertura RN × escenario, hallazgos con severidad (`BLOQUEANTE` / `MAYOR` /
  `MENOR`) y cita `archivo:línea`, preguntas abiertas detectadas y una sección "no verificado".
- **Cómo revisar su salida**: todo hallazgo tiene que citar una RN o un archivo de la KB; ningún valor
  numérico puede aparecer sin respaldo en la KB; los `BLOQUEANTE` se corrigen antes de implementar.
  La skill **solo reporta**, no reescribe la spec: el fix lo hacemos nosotros.

### Skill propia: `visual-turnos`

Vive en `.opencode/skills/visual-turnos/SKILL.md`, y su contexto de producto/diseño en
`PRODUCT.md` y `DESIGN.md`.

- **Cuándo usarla**: antes de crear o rediseñar cualquier página visual, componente de layout o
  auditoría de UI. Es obligatoria para pages de reserva pública, login, agenda, pacientes, caja y
  reportes.
- **Qué necesita**: ruta, modo (Persuade/Operate/Read), audiencia, job, estados, fuente de diseño
  (Figma/Stitch/code-first) y contenido real.
- **Qué devuelve**: page brief, archivos/tokens usados, evidencia visual, hallazgos de a11y/responsive
  y `MCP usado`.
- **MCP**: Figma es opcional (`https://mcp.figma.com/mcp`, OAuth); Stitch es opcional y su URL sale
  del setup. Sin MCP, la skill trabaja code-first y lo declara.

---

## MCP: Context7

> Es una **integración externa, NO una skill**: no se registra en `.atl/skill-registry.md` ni se delega como
> compact rule.

Expone `resolve-library-id` y `query-docs` para traer documentación vigente de librerías y APIs al contexto del
agente (útil al preparar `design.md` o al dudar del comportamiento real de FastAPI, SQLAlchemy, Alembic,
React, Vite, Mercado Pago, WhatsApp Cloud API o Google Calendar API). Configuración, límites y verificación:
[README.md](README.md) §MCP y `docs/skills-mcp/`.

---

## Roadmap de Changes

El plan de implementación completo está en [CHANGES.md](CHANGES.md). Resumen:

- **Total**: 15 changes en 8 fases (FASE 0 — Cimientos … FASE 7 — Administración y plataforma).
- **Camino crítico** (8): `C-01 → C-02 → C-03 → C-04 → C-05 → C-06 → C-10 → C-15`.
- **Primer change**: `C-01` (foundation-setup: scaffolding FastAPI + Vite + docker-compose + Alembic).

**Antes de cualquier `/opsx:propose`**: leé [CHANGES.md](CHANGES.md), identificá las dependencias del change y los archivos de "Leer antes".

---

## Reglas Duras

> Reglas **globales** ya definidas en `~/.claude/CLAUDE.md` (orquestador, governance, TDD, engram): el proyecto las **hereda**, no se repiten acá.

Acá van las reglas específicas de este proyecto, derivadas de su stack (FastAPI + SQLAlchemy/Alembic + PostgreSQL 15+ RLS por tenant + Redis + React 18+ TS + Vite + JWT + Mercado Pago + WhatsApp Cloud API + GCal API v3 + Docker Compose) y **confirmadas con el usuario**. Son contrato; romperlas es un defecto. Formato `NUNCA X → hacer Y`:

- NUNCA usar `any` en el frontend → tipado estricto TypeScript en todo el código TS (borde API validado con schemas compartidos/Pydantic en backend).
- NUNCA código Python sin type hints ni queries crudas → todo type-hinteado y acceso a datos solo vía SQLAlchemy (SQL crudo únicamente dentro de migraciones Alembic).
- NUNCA hacer una query sin tenant → toda tabla de negocio filtra por `tenant_id` y tiene RLS (`tenant_id = current_setting('app.tenant_id')`).
- NUNCA violar RN-AG-02/RN-AU-02 por conveniencia → anti-solape y aislamiento por tenant se cumplen siempre, sin atajos.
- NUNCA usar datos reales de pacientes → solo datos ficticios en desarrollo, tests y demos.
- NUNCA poner secretos en el repo → env vars (`.env.example` como referencia); sin PHI en logs ni en mensajes.
- NUNCA hacer commit/push sin pedido → conventional commits, sin co-autoría IA.
- NUNCA mergear agenda/caja/señas sin test de regresión → la regresión en verde es condición de merge.

---

## Flujo de Trabajo

```
1. Leer la KB relevante (knowledge-base/)        → entender el dominio
2. Identificar el change en CHANGES.md           → respetar dependencias
3. /opsx:propose C-NN-nombre                     → proposal + design + specs + tasks
4. Revisar la spec con revisor-escenarios-turnos → cerrar huecos y valores inventados
5. Implementar las tasks (cargando skills)       → respetando las reglas duras
6. /opsx:archive C-NN-nombre + marcar [x]        → cerrar el change
```

Aplicar TODAS las reglas duras en cada paso. Ante conflicto entre la KB y este archivo, las reglas duras prevalecen.
