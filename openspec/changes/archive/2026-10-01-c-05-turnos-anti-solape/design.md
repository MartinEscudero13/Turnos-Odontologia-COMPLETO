# Design — C-05 `turnos-anti-solape` (reimplementación Python, 2026-10-02)

> Reescritura del diseño original TS (2026-10-01) al stack obligatorio del
> proyecto: Python + FastAPI + SQLAlchemy + PostgreSQL + Redis + JWT
> (`AGENTS.md`). El spec NO cambió (dado/cuando/entonces agnósticos al
> stack); el diseño TS queda en la historia git. Ver
> `reimplementacion-python.md` (motivo, qué se reutilizó, qué cambió).

## Context

Ver `proposal.md` (Why + Addendum 2026-10-02). Estado actual: repo con la
implementación TS archivada (eliminada del árbol en esta reimplementación,
conservada en historia git) y sin scaffolding general (eso es C-01; acá solo
el mínimo para correr la suite, anotado como adelanto parcial). C-03 aporta
RBAC + auditoría append-only y C-04 las entidades referenciadas
(Profesional, Sillón, Paciente, Prestación, Bloqueos). Reglas duras
aplicables (`AGENTS.md`): type hints Python obligatorios, SQLAlchemy sin
queries crudas salvo migración, toda query con `tenant_id` + RLS,
anti-solape y auditoría no negociables, datos ficticios, regresión en verde
para agenda.

## Goals / Non-Goals

**Goals:** anti-solapamiento real garantizado por DB; sobreturno explícito
auditado; cancelar/reprogramar con revalidación servidor-side; 409 con 3
alternativas; dominio + API testeables con `py -m pytest` (Python 3.14).

**Non-Goals:** UI agenda (follow-up explícito); reserva pública (C-06);
lista de espera auto-oferta (C-07, solo se deja el hook: hueco liberado);
cobros/señas (C-10/C-11); sync GCal (C-14); scaffolding completo C-01
(compose, JWT real — el router usa headers como sostén provisorio).

## Decisions

- **D1 — EXCLUDE en DB como fuente de verdad (no solo app).**
  Dos constraints `EXCLUDE USING gist` sobre `tstzrange(inicio, fin)`:
  `(tenant_id, profesional_id)` y `(tenant_id, sillon_id)`, parciales
  (`WHERE estado NOT IN ('CANCELADO','REPROGRAMADO') AND sobreturno = false`).
  Alternativa descartada: chequeo solo en aplicación → pierde ante
  concurrencia. Requiere extensión `btree_gist`. El servicio replica el
  predicado en memoria (paridad) bajo `threading.Lock`.
- **D2 — RLS + `tenant_id` en la llave del constraint.**
  RLS `tenant_id = current_setting('app.tenant_id')` en `turnos` y
  `tenant_id` dentro del EXCLUDE. Todo `listar`/`obtener` filtra por tenant.
- **D3 — `timestamptz`, `fin` calculado, rango `[inicio, fin)`.**
  `DateTime(timezone=True)` (nunca naive: el servicio rechaza datetimes sin
  tz con 422); `fin = inicio + prestacion.duracion_min` servidor-side; el
  `fin` del cliente solo vale si coincide exacto. Half-open ⇒ adyacencia
  exacta permitida por construcción.
- **D4 — Índices + concurrencia.**
  `(tenant_id, profesional_id, inicio)`, `(tenant_id, sillon_id, inicio)`,
  `(tenant_id, estado)` (revisión Alembic 003). Escrituras bajo lock en el
  standalone; ante carrera, el último pierde (`409` + 3 alternativas
  servidor-side, RN-GL-02).
- **D5 — Sobreturno = flag + auditoría, jamás solape silencioso.**
  `sobreturno bool default false`; crearlo exige motivo no vacío (strip) y
  escribe entrada append-only (actor, motivo, antes/después). Sin motivo →
  `422`. Errores de dominio como excepciones con `codigo` HTTP que el router
  mapea (más pitónico que el `Resultado<T>` del TS).
- **D6 — Cancelar/reprogramar como transiciones auditadas.**
  Cancelar → `CANCELADO`; reprogramar → original `REPROGRAMADO` + nuevo turno
  (revalida EXCLUDE ANTES de mutar: 409 deja el original intacto).
  Anticipación mínima configurable (default 24 h); debajo del umbral solo
  recepción/admin + auditoría. Estados finales no bloquean (predicado D1).
- **D7 — Standalone testeable sin Postgres + borde FastAPI/Pydantic.**
  Dominio puro (`backend/app/turnos/`: overlap, fin, estados, alternativas,
  servicio) sin I/O; schemas Pydantic v2 en borde (strict donde el contrato
  TS era strict); modelos SQLAlchemy (`tenant_id` everywhere, sin SQL crudo);
  router FastAPI con `crear_app()` inyectable para TestClient. La DDL del
  EXCLUDE vive en la revisión Alembic 003 (`backend/alembic/versions/`).

## Risks / Trade-offs

- [Carrera doble-reserva bajo carga] → Mitigación: EXCLUDE en DB + lock
  app-level + 409 con alternativas; test de concurrencia con threads (×5).
- [Zona horaria AR vs UTC] → Mitigación: aware-obligatorio + 422 a naive;
  test de cruce de medianoche.
- [EXCLUDE requiere `btree_gist`] → Mitigación: extensión en la revisión 003.
- [Reprogramar deja hueco inconsistente si falla a medias] → Mitigación:
  revalidación pre-mutación + test de original intacto.
- [SQLAlchemy 2.0.35 + Python 3.14] → `Mapped[X | None]` rompe el mapper
  (`Union.__getitem__` más estricto en 3.14); se usa `Mapped[str]` +
  `nullable=True` explícito. Documentado, no oculto.
- [UI fuera del change] → el contrato API congela `409`+alternativas.

## Migration Plan

1. Revisión Alembic 003 (`backend/alembic/versions/003_turnos_anti_solape.py`):
   extensiones, tabla `turnos`, 2 EXCLUDE parciales, 3 índices + token único
   parcial, RLS + `SET app.tenant_id`. `downgrade()` revierte (DROP POLICY +
   DROP TABLE).
2. Seed ficticio (`backend/seed_test.py` + `seed_sql()` para PG real).
3. Despliegue sin rollback de datos (tabla nueva); rollback = downgrade.
4. UI agenda como change follow-up separado.

## Open Questions

Ninguna que cambie specs, enfoque o tasks. (Anticipación exacta y alcance de
seña son PO abiertas de otros changes; acá van parametrizadas con default.)
