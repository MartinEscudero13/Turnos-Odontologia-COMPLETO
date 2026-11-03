# Skill Registry

**Delegator use only.** Any agent that launches sub-agents reads this registry to resolve compact rules, then injects them directly into sub-agent prompts. Sub-agents do NOT read this registry or individual SKILL.md files.

See `_shared/skill-resolver.md` for the full resolution protocol.

## User Skills

| Trigger | Skill | Path |
|---------|-------|------|
| Writing, reviewing, or refactoring React/Next.js code; React components, Next.js pages, data fetching, bundle optimization, performance improvements | vercel-react-best-practices | C:\Users\tinch\.agents\skills\vercel-react-best-practices\SKILL.md |
| Building new UI or reshaping an existing one; aesthetic direction, typography, distinctive visual design | frontend-design | C:\Users\tinch\.agents\skills\frontend-design\SKILL.md |
| "review my UI", "check accessibility", "audit design", "review UX", "check my site against best practices" | web-design-guidelines | C:\Users\tinch\.agents\skills\web-design-guidelines\SKILL.md |
| BEFORE writing or changing anything in Postgres: tables/columns, schema design, migrations, RLS policies, indexes, triggers, functions, pg_cron/pgmq, pgvector, pg_restore; or diagnosing slow queries, EXPLAIN, connections, locking, bloat, wrong-tenant rows | supabase-postgres-best-practices | C:\Users\tinch\.agents\skills\supabase-postgres-best-practices\SKILL.md |
| Only when a user or existing integration explicitly invokes prisma-postgres (deprecated compat name) | prisma-postgres | C:\Users\tinch\.agents\skills\prisma-postgres\SKILL.md |
| Working with shadcn/ui, component registries, presets, --preset codes, or any project with components.json; "shadcn init", "create an app with --preset", "switch to --preset" | shadcn | C:\Users\tinch\.agents\skills\shadcn\SKILL.md |
| Encountering any bug, test failure, or unexpected behavior — before proposing fixes | systematic-debugging | C:\Users\tinch\.agents\skills\systematic-debugging\SKILL.md |
| User says "diagnose"/"debug this", or reports something broken/throwing/failing/slow; hard bugs and performance regressions | diagnosing-bugs | C:\Users\tinch\.agents\skills\diagnosing-bugs\SKILL.md |

## Project Skills

Versioned in this repo (not in the user skills folder).

| Trigger | Skill | Path |
|---------|-------|------|
| Preparing or reviewing an OpenSpec change of turnos (propose/verify); "revisá los escenarios", "¿falta algún caso borde?", "¿esta spec es verificable?", "auditá el spec antes de implementar"; any `specs/<capability>/spec.md` of turnos about to be implemented | revisor-escenarios-turnos | .opencode/skills/revisor-escenarios-turnos/SKILL.md |

## Compact Rules

Pre-digested rules per skill. Delegators copy matching blocks into sub-agent prompts as `## Project Standards (auto-resolved)`.

### vercel-react-best-practices
- Eliminate waterfalls: parallelize independent fetches with Promise.all, start promises early / await late, defer await into branches, stream with Suspense boundaries
- Bundle: import directly (no barrel files), prefer statically analyzable paths, next/dynamic for heavy components, load third-party/analytics after hydration, preload on hover/focus
- Server (RSC): React.cache() per-request dedup + LRU cross-request, hoist static I/O to module level, never share mutable request state at module level, minimize client-serialized props, use after() for non-blocking work
- Client: SWR for dedup, deduplicate global listeners, passive scroll listeners, versioned/minimal localStorage schema
- Re-render: split independent hooks, primitive effect deps, derive state during render (not effects), functional setState, startTransition/useDeferredValue for non-urgent work, never define components inside components
- Rendering/JS: ternary (not &&) for conditionals, content-visibility for long lists, hoist static JSX/RegExp, batch DOM writes via classes, Set/Map for O(1) lookups, combine filter/map passes

### frontend-design
- Ground every design in the brief's subject matter (odontología, mobile-first paciente): palette, type and layout must come from that world, never generic defaults
- Plan first as tokens (4-6 named hex colors, 1-2 typefaces with roles, layout concept + ASCII wireframe, uniqueness principles), review against brief for generic tells, then build
- Reject generic defaults unless the brief asks: cream #F4F1EA + terracotta #D97757 serif hero, black + acid-green accent, hairline broadsheet, identical SaaS cards with rgba(0,0,0,.1) shadows, ALL-CAPS eyebrows, "A · B · C" meta strings, trailing "→"
- Typography: 1-2 families max, clear scale, <80 chars line length, never accent a single headline word / all-caps labels / gratuitous eyebrow labels
- Motion answers user action (open/expand/confirm); one orchestrated load moment max — no per-section fade-slide-up or hover-everywhere
- Copy is UX: user vocabulary ("mis turnos", not "gestión de slots"), active voice, CTA names the outcome ("Reservar turno"), errors explain how to fix without apologizing, empty states invite action

### web-design-guidelines
- Always fetch fresh rules first via WebFetch: https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md — never review from memory
- Scope: read the exact files/pattern given (ask user if missing), check every fetched rule, no sampling
- Output findings only in the fetched guidelines' terse `file:line` format — no prose summaries, no rewritten code unless the format requires it
- One finding per violation with precise line; group by file, highest severity first
- If guidelines URL is unreachable, stop and report — do not fall back to cached rules

### supabase-postgres-best-practices
- Load BEFORE any Postgres change, even one column or one query — schema, migration, RLS, index and SQL authoring all need these rules
- Query: EXPLAIN before optimizing, index foreign keys and WHERE/ORDER BY columns, prefer partial indexes for filtered queries, never SELECT * on hot paths, paginate with keyset (not large OFFSET)
- Connections: always use a pooler (Supavisor/PgBouncer transaction mode), never per-request new connections, cap pool size, set statement_timeout
- Security/RLS: enable RLS on every tenant table, force `tenant_id = auth.jwt()` policies, test policies with a dedicated test per role (anon/authenticated/wrong-tenant must be denied), never bypass RLS with service_role from client-reachable code
- Schema/concurrency: use timestamptz (never timestamp), UUIDv7 or bigint identity PKs, add NOT NULL + CHECK constraints at DB level (anti-solape: EXCLUDE/range constraint, not app-only), expand-contract for zero-downtime renames, CREATE INDEX CONCURRENTLY, batched backfills
- Anti-solape agenda: exclusion constraint on (profesional/sillón, rango horario) + deterministic timezone handling; sobreturno only via explicit audited flag

### prisma-postgres
- DEPRECATED compat shim — contains no setup recipes; do not apply its rules directly
- If invoked, load `prisma-postgres-setup` (install from prisma/skills if missing) and follow that skill instead
- Keep this entry until all consumers migrate; never build new workflows on the `prisma-postgres` name
- Turnos-Odontologia data modeling (turnos, pacientes, ficha, OS, caja multi-tenant): schema, migrations and queries follow `prisma-postgres-setup` + `supabase-postgres-best-practices` (RLS/índices anti-solape)

### shadcn
- Run CLI with the project's package runner only: npx/pnpm dlx/bunx `shadcn@latest`; never hand-fetch registry files from GitHub
- Use existing components first (`search`), compose (Tabs+Card+form, Sidebar+Card+Chart+Table), prefer built-in variants and semantic colors (bg-primary, text-muted-foreground — never bg-blue-500)
- Styling: className for layout only, flex+gap (never space-x/y), size-* for square, truncate shorthand, cn() for conditionals, no manual dark: overrides or z-index on overlays
- Forms: FieldGroup+Field layout, InputGroupInput/Textarea inside InputGroup, ToggleGroup for 2-7 option sets, FieldSet+FieldLegend for checkbox/radio groups, data-invalid on Field + aria-invalid on control
- Structure: items inside Groups (SelectItem→SelectGroup), asChild (radix) / render (base) for triggers, Dialog/Sheet/Drawer always need Title, full Card composition, Button loading = Spinner+disabled (no isPending), Avatar always needs Fallback
- Workflow: check installed components before add, `docs <component>` + fetch URLs before using/fixing, --dry-run/--diff before overwriting (never --overwrite without approval), ask which registry when unspecified, respect aliases/isRSC/tailwindVersion/base/iconLibrary from project context

### systematic-debugging
- IRON LAW: no fixes without Phase 1 root-cause investigation — symptom fixes are failure
- Phase 1: read full error/stack, reproduce reliably, check recent changes (git diff), instrument every component boundary (log in/out + env/config) and trace data flow backward to the source; fix at source
- Phase 2: find working examples in the same codebase, read reference implementations completely, list every difference — never assume "that can't matter"
- Phase 3: one falsifiable hypothesis at a time ("I think X because Y"), smallest single-variable test, verify before continuing; if you don't know, say so
- Phase 4: failing test first, single fix (no drive-by refactors), verify (test passes, nothing else broke, symptom gone); <3 failures → re-analyze, ≥3 failures → stop and question the architecture with the human
- Red flags that force return to Phase 1: "quick fix for now", "try X and see", multiple changes at once, skipping tests, "probably X", "one more attempt" after 2+ failures

### diagnosing-bugs
- Phase 1 is the skill: build a tight red-capable feedback loop first (failing test → curl script → CLI fixture diff → headless browser → trace replay → throwaway harness → fuzz → bisect → differential; HITL script last resort); no theorizing before one command exists that goes red on THIS bug
- Tighten the loop: seconds not minutes, deterministic (pin time/seed/FS/network; raise flake rate to ~50% via stress before debugging), sharp symptom assertion, agent-runnable unattended
- Phase 2: reproduce the USER's exact failure (not a nearby one) across runs, capture the symptom, then minimize by cutting one element at a time until every remainder is load-bearing — the minimized repro becomes the regression test
- Phase 3-4: rank 3-5 falsifiable hypotheses ("If X then changing Y removes it"), show the list to the user before testing, probe one variable at a time with tagged [DEBUG-xxxx] logs (debugger preferred; perf bugs need baseline measurement + bisection, not logs)
- Phase 5-6: regression test only at a seam that exercises the real bug pattern (no seam = architectural finding, flag it); test-fails → fix → test-passes → re-run original loop; cleanup before done (repro green, tagged logs grepped out, throwaways deleted, winning hypothesis in commit message)
- Redact every secret as <REDACTED>; loops read credentials from env, artifacts quote only signal lines; if redacted output is insufficient, stop and ask

### revisor-escenarios-turnos
- Read-only audit of a delta spec (`openspec/changes/<name>/specs/<capability>/spec.md` and/or `openspec/specs/<capability>/spec.md`); never rewrite the spec, tasks or code — report only, the team applies the fix
- Inputs required: change path, capability, and the RN list from "Leer antes" in CHANGES.md; if one is missing ask for it, never invent scope
- Scope RNs by real prefix: RN-AG agenda/anti-solape, RN-RE reserva/anticipación/lista de espera, RN-SE señas/MP, RN-CL clínica/PHI, RN-OS obras sociales, RN-CJ caja, RN-AU RBAC/auditoría/consentimiento, RN-IN integraciones, RN-GL globales
- Coverage matrix per RN × feliz / error de negocio / borde / concurrencia-idempotencia; mark `HUECO`; any error scenario that mutates state is BLOQUEANTE
- Open values that must never be fixed by a spec: PO-01 (seña y anticipación exacta), PO-03 (profundidad WA/MP/GCal), PO-05 (cantidad de profesionales), PO-06 (login de paciente vs nombre+teléfono), PO-02/PO-04/PO-07/PO-08/PO-10/PO-11
- Domain edges to demand: tenant_id + RLS on every query and token of tenant A never touching tenant B, PHI out of logs/messages, exact anticipación threshold, auto-oferta expiration + single claim, idempotent MP webhooks and WA reminders, caja/OS/consentimiento rules
- Output: coverage table, findings table (`BLOQUEANTE`/`MAYOR`/`MENOR` + `archivo:línea` + RN), open questions the spec resolved on its own, and "no verificado"; no finding without a KB citation

## Project Conventions

| File | Path | Notes |
|------|------|-------|
| AGENTS.md / CLAUDE.md | `AGENTS.md`, `CLAUDE.md` | Identical byte-for-byte; stack, KB index, skills per role, CHANGES summary and hard rules |
| Knowledge base | `knowledge-base/` | 12 files: vision, stack, actores, datos, reglas RN-XX, funcionalidades US-NNN, flujos, arquitectura, decisiones, preguntas abiertas, integraciones |
| Change index | `CHANGES.md` | Dependency tree, gates, critical path, per-change scope and "Leer antes" |
