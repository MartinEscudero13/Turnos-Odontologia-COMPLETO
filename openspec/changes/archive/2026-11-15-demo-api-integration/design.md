# Design

## Context

C-05/C-06 use service objects with injectable ports. Their routers already exist; only the composition root is missing. Auth and catálogos use SQL; the rest of the domain has in-memory adapters for tests and demos. See `proposal.md`.

## Goals / Non-Goals

**Goals:** mount C-05/C-06 routes, seed a demo tenant, smoke-test the public booking flow, keep existing tests green.

**Non-Goals:** wire C-07…C-11, build full SQL persistence for turnos/reservas, change domain contracts, implement Mercado Pago/C-11 in the demo, or create frontend pages beyond F-02.

## Decisions

**D1 — Composition root `backend/app/demo.py`.**
Creates one `ServicioTurnos`, one `CatalogoMemoria`, `PacienteMemoria`, `TenantMemoria`, `TokenRepositorioEnMemoria`, `ContadorMemoria`, `VerificadorMemoria`, `AuditoriaMemoria` and `ServicioReservasPublicas`. The catalog is seeded with fictitious IDs and weekly hours.

**D2 — Mount routers, not apps.**
Use `crear_router(turnos)` and `crear_router_publico(reservas)` inside `create_app`; do not nest the per-change app factories, to keep one OpenAPI root and one exception/middleware stack.

**D3 — Demo tenant is explicit.**
Slug `demo` maps to `DEMO_TENANT_ID`. Public routes only resolve that tenant; unknown slugs return 404. C-05 internal routes continue using their provisional actor headers.

**D4 — Auth/catalog remain SQL.**
They already use `session_factory` and real repositories. C-05/C-06 demo state is in memory and resets on restart. This is a deliberate demo slice, not a claim of production persistence.

**D5 — No new migration.**
C-05/C-06 tables/repositories are not being rewired here. The change adds no DDL.

## Risks / Trade-offs

- Demo reservations disappear on restart → documented; SQL wiring remains a follow-up.
- Two sources of catalog (C-04 SQL and demo in-memory) can diverge → the demo seed mirrors the demo values, and the public route is explicitly the in-memory demo path.
- C-07…C-11 remain unmounted → reported as a remaining integration debt, not hidden.

## Verification

- HTTP tests for `/api/health`, `/api/turnos`, `/api/publico/demo/catalogo`, availability and reservation.
- Full pytest, ruff, mypy, OpenSpec strict.
- Manual smoke with `uvicorn`/Docker if possible.
