# Design — C-05 `turnos-anti-solape`

## Context

Ver `proposal.md` (Why). Estado actual: repo sin código (`src/` no existe) y
sin specs previas; C-03 aporta RBAC + `lib/audit` append-only y C-04 las
entidades referenciadas (Profesional, Sillón, Paciente, Prestación, Bloqueos).
Este change define el núcleo de agenda. Reglas duras aplicables (`AGENTS.md`):
tipado estricto TS (zod en borde API), toda query con `tenant_id` + RLS,
anti-solape y auditoría no negociables, datos ficticios, regresión en verde
para agenda. Compact rules aplicadas de `supabase-postgres-best-practices`
(ver Decisiones D1–D3).

## Goals / Non-Goals

**Goals:** anti-solapamiento real garantizado por DB; sobreturno explícito
auditado; cancelar/reprogramar con revalidación servidor-side; 409 con 3
alternativas; módulo de dominio standalone testeable con Node 24.

**Non-Goals:** UI `(app)/agenda` (follow-up explícito); reserva pública (C-06);
lista de espera auto-oferta (C-07, solo se deja el hook: hueco liberado);
cobros/señas (C-10/C-11); sync GCal (C-14).

## Decisions

- **D1 — EXCLUDE en DB como fuente de verdad (no solo app).**
  Dos constraints `EXCLUDE USING gist` sobre `tstzrange(inicio, fin)`:
  `(tenant_id, profesional_id)` y `(tenant_id, sillon_id)`, parciales
  (`WHERE estado NOT IN ('CANCELADO','REPROGRAMADO') AND sobreturno = false`).
  Alternativa descartada: chequeo solo en aplicación → pierde ante
  concurrencia (doble-reserva simultánea). Requiere extensión `btree_gist`.
- **D2 — RLS + `tenant_id` en la llave del constraint.**
  RLS `tenant_id = current_setting('app.tenant_id')` en `turnos` (barrera
  C-03) y `tenant_id` dentro del EXCLUDE para aislamiento total entre
  consultorios. Nunca `SELECT *` en agenda; índices de D4 cubren los filtros.
- **D3 — `timestamptz`, `fin` calculado, rango `[inicio, fin)`.**
  `inicio/fin timestamptz` (nunca `timestamp`); `fin = inicio +
  prestacion.duracion_min` calculado servidor-side; el `fin` del cliente se
  ignora/valida. Semántica half-open ⇒ adyacencia exacta permitida por
  construcción. Timezone determinista (tenant `America/Argentina/Buenos_Aires`,
  persistencia UTC).
- **D4 — Índices + concurrencia.**
  `(tenant_id, profesional_id, inicio)`, `(tenant_id, sillon_id, inicio)`,
  `(tenant_id, estado)` (migración 003). Escrituras en transacción; ante
  carrera, el último en confirmar pierde (`409` + 3 alternativas calculadas
  servidor-side, RN-GL-02).
- **D5 — Sobreturno = flag + auditoría, jamás solape silencioso.**
  `sobreturno bool default false`; crearlo exige motivo no vacío y escribe
  entrada append-only (actor, motivo, antes/después). Sin motivo → `422`.
- **D6 — Cancelar/reprogramar como transiciones auditadas.**
  Cancelar → `CANCELADO`; reprogramar → original `REPROGRAMADO` + nuevo turno
  (revalida EXCLUDE). Anticipación mínima configurable (default 24 h);
  debajo del umbral solo recepción + auditoría. Estados finales no bloquean
  (predicado parcial de D1).
- **D7 — Módulo standalone testeable sin Postgres.**
  Lógica pura (`overlap([a,b),[c,d))`, `fin`, alternativas, validaciones)
  sin I/O, importable en `node:test`/vitest con Node 24; el EXCLUDE se
  verifica además con test de integración SQL en la migración 003. Prisma 5+
  modela `Turno`; la DDL del EXCLUDE va en migración SQL versionada
  (expand-contract si hay que evolucionar).

## Risks / Trade-offs

- [Carrera doble-reserva bajo carga] → Mitigación: EXCLUDE en DB + 409 con
  alternativas; test de concurrencia en tasks.
- [Zona horaria AR vs UTC] → Mitigación: `timestamptz` + tests de borde
  (turno a caballo del cambio de hora); D3.
- [EXCLUDE requiere `btree_gist`] → Mitigación: habilitar extensión en
  migración 003 y en seed de test; documentado en tasks.
- [Reprogramar como par original+nuevo deja hueco inconsistente si falla a
  medias] → Mitigación: transacción atómica + test.
- [UI fuera del change] → el contrato API congela `409`+alternativas para que
  la agenda futura no redefina comportamiento.

## Migration Plan

1. Migración 003 (versionada Prisma/SQL): extensión `btree_gist`, tabla
   `turnos`, 2 EXCLUDE parciales, 3 índices, RLS + `SET app.tenant_id`.
2. Seed ficticio mínimo de test (1 tenant, 1 profesional, 1 sillón,
   prestación 30 min) — datos ficticios, sin PHI.
3. Despliegue sin rollback de datos (tabla nueva); rollback = revert de
   migración + dropear tabla (sin dependientes aún salvo C-06+).
4. UI agenda como change follow-up separado (referencia este spec).

## Open Questions

Ninguna que cambie specs, enfoque o tasks. (Anticipación exacta y alcance de
seña son PO abiertas de otros changes; acá van parametrizadas con default.)
