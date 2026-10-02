# Tasks — C-05 `turnos-anti-solape` (reimplementación Python, 2026-10-02)

> Re-corrida completa en Python: 16/16 en `[x]`, suite **104 tests en verde**
> (`py -m pytest tests/ -q`). El spec no se tocó (12 escenarios intactos).
> TDD por task con RED observado en pytest salvo 4.1–4.3 (cobertura de
> aceptación green-first, declarado abajo — mismo criterio de honestidad que
> la corrida TS, que documentó sus propios desvíos).

## 1. Dominio standalone (testeable con Python 3.14)

- [x] 1.1 `intervalos_solapan()` half-open `[inicio, fin)` (`backend/app/turnos/overlap.py`,
  `tests/test_overlap.py` 8 tests): solape parcial/total/contenido falla y adyacencia
  exacta pasa. RED: `ModuleNotFoundError` en colección → GREEN → TRIANGULATE (rango
  vacío, simetría, solape de 1 min).
- [x] 1.2 `calcular_fin()` + `fin_cliente_valido()` (`fin.py`, `test_fin.py` 8 tests):
  duraciones 30/45/60; `fin` cliente distinto → rechazado. RED → GREEN → TRIANGULATE
  (bool no es duración, cruce de medianoche).
- [x] 1.3 `buscar_alternativas()` (`alternativas.py`, `test_alternativas.py` 8 tests):
  grilla 15 min, primer candidato = `desde`, orden cronológico, ≤3. RED → GREEN →
  TRIANGULATE (REPROGRAMADO no bloquea, agenda saturada → `[]`).
- [x] 1.4 Máquina de estados (`estados.py`, `test_estados.py` 9 tests): transiciones
  legales/ilegales; `CANCELADO`/`REPROGRAMADO` liberan hueco. RED → GREEN →
  TRIANGULATE (AUSENTE final, reprogramar solo desde activos).

## 2. Persistencia (revisión Alembic 003 + RLS)

- [x] 2.1 Revisión `backend/alembic/versions/003_turnos_anti_solape.py`: extensiones
  `pgcrypto`+`btree_gist`, tabla `turnos` (timestamptz, `sobreturno default false`,
  `origen`, `token_publico?`) con `tenant_id NOT NULL`; `upgrade()` + `downgrade()`.
  Verificado por `tests/test_migracion_003.py` (estructural, 4 tests).
- [x] 2.2 Los 2 EXCLUDE parciales (`(tenant, profesional)` y `(tenant, sillón)` sobre
  `tstzrange(inicio, fin)`, `WHERE` excluye `CANCELADO`/`REPROGRAMADO` y
  `sobreturno=true`); el predicado se replica en `ServicioTurnos._hay_solape` y se
  verifica por paridad en los tests de solape + regresión 03/04/06/07.
- [x] 2.3 Índices `(tenant, profesional, inicio)`, `(tenant, sillón, inicio)`,
  `(tenant, estado)` + token único parcial y política RLS
  (`tenant_id = current_setting('app.tenant_id')`); modelos SQLAlchemy en
  `backend/app/models/turno.py` (`tenant_id` NOT NULL, `DateTime(timezone=True)`,
  CHECKs) verificados por `tests/test_modelos.py` (5 tests). Gotcha: `Mapped[X | None]`
  incompatible con SQLAlchemy 2.0.35 en Python 3.14 → `Mapped[str]` + `nullable=True`.
- [x] 2.4 Seed ficticio (`backend/seed_test.py` + `seed_sql()` para PG real, sin PHI);
  `tests/test_seed.py` (2 tests): idempotente (2 corridas → 1 turno) y SQL con
  `ON CONFLICT DO NOTHING` + `set_config('app.tenant_id')`.

## 3. API de turnos (Pydantic en borde, type hints estrictos)

- [x] 3.1 `CRUD /api/turnos` (`backend/app/routers/turnos.py`, schemas en
  `backend/app/schemas/turno.py`, `tests/test_servicio_crud.py` 15 tests + borde en
  `test_api_turnos.py`): crear valida hueco y calcula `fin`; leer filtra por
  `tenant_id`; actualizar solo `pacienteId` (strict → 422 a extras); RBAC mínimo
  (paciente/odontólogo acotados). RED (módulo inexistente) → GREEN → TRIANGULATE
  (solape por sillón, sobreturno con/sin motivo en crear).
- [x] 3.2 `POST /api/turnos/:id/sobreturno` (`tests/test_sobreturno.py` 7 tests):
  motivo obligatorio no vacío → `422` si falta (y no marca); con motivo marca y
  audita (actor, motivo, antes/después). RED (`AttributeError`) → GREEN →
  TRIANGULATE (marcado no bloquea hueco, motivo preservado).
- [x] 3.3 `POST /api/turnos/:id/cancelar|reprogramar`
  (`tests/test_cancelar_reprogramar.py` 8 tests): anticipación mínima 24 h (debajo
  del umbral solo recepción/admin + auditoría); reprogramar revalida solape ANTES
  de mutar (409 deja original intacto). RED (4 fallos: método inexistente +
  anticipación ausente) → GREEN → TRIANGULATE (final → 422, duración explícita).
- [x] 3.4 `409 + 3 alternativas` en todo rechazo por solape
  (`tests/test_conflicto_409.py` 3 tests + borde API): crear y reprogramar devuelven
  exactamente 3 huecos libres ordenados. RED (stub `[]`) → GREEN (integración
  `buscar_alternativas`) → TRIANGULATE (primera alternativa directamente reservable).

## 4. Regresión y auditoría (condición de merge)

- [x] 4.1 Regresión agenda (`tests/test_regresion_agenda.py`, 12 tests 1:1 con el spec):
  solape profesional/sillón → 409 sin persistir; adyacencia pasa; tenant aísla;
  cancelado/reprogramado no bloquea; sobreturno con motivo audita / sin motivo 422;
  cancelar/reprogramar con anticipación y revalidación. Green-first de aceptación;
  **un test falló de verdad en la corrida** (faltaba auditar crear-con-flag en
  `ServicioTurnos.crear`; se implementó y pasó a verde).
- [x] 4.2 Concurrencia (`tests/test_concurrencia.py`, 2 tests): 8 hilos al mismo hueco
  ×5 repeticiones → exactamente 1 confirma y 7 reciben `409` con 3 alternativas;
  huecos distintos en paralelo no chocan. Green-first (lock desde el diseño).
- [x] 4.3 Auditoría (`tests/test_auditoria.py`, 3 tests): sobreturno/cancelación/
  reprogramación con antes/después; paciente sin acceso; odontólogo solo su agenda;
  entradas sin PHI (claves exactas) y sin métodos de borrado. Green-first.
- [x] 4.4 Sin UI en el change (follow-up `(app)/agenda` intacto); spec del archive y
  vigente sin tocar; `openspec` CLI no disponible en este entorno para revalidar
  (desvío menor: validación por suite + revisión manual del spec).

### Evidencia TDD por task

| Task | Test | RED | GREEN | TRIANGULATE (≥2) | REFACTOR |
|------|------|-----|-------|-------------------|----------|
| 1.1 overlap | `test_overlap.py` (8) | ✅ colección | ✅ | ✅ vacío/simetría/1-min | ✅ imports |
| 1.2 fin | `test_fin.py` (8) | ✅ colección | ✅ | ✅ bool/medianoche | ✅ imports |
| 1.3 alternativas | `test_alternativas.py` (8) | ✅ colección | ✅ | ✅ reprog/saturada | ✅ imports |
| 1.4 estados | `test_estados.py` (9) | ✅ colección | ✅ | ✅ ausente/reprog-activos | ✅ — |
| 2.1–2.4 persistencia | `test_migracion_003.py` (4) + `test_modelos.py` (5) + `test_seed.py` (2) | ✅ colección/archivo ausente | ✅ | ✅ defaults/token/expand-contract | ✅ CHECK assert |
| 3.1 CRUD | `test_servicio_crud.py` (15) | ✅ colección | ✅ | ✅ sillón/sobre±motivo | ✅ imports |
| 3.2 sobreturno | `test_sobreturno.py` (7) | ✅ AttributeError | ✅ | ✅ no-bloquea/preserva | ✅ — |
| 3.3 cancelar/reprog | `test_cancelar_reprogramar.py` (8) | ✅ 4 fallos | ✅ | ✅ final-422/duración | ✅ — |
| 3.4 409+3 | `test_conflicto_409.py` (3) | ✅ stub [] | ✅ | ✅ alternativa usable | ✅ — |
| 3.x borde API | `test_api_turnos.py` (10) | ✅ ModuleNotFound | ✅ | ✅ rol-422/strict | ✅ (Z-doc) |
| 4.1 regresión | `test_regresion_agenda.py` (12) | ➖ aceptación (1 fallo real, fixeado) | ✅ | n/a | ✅ helper |
| 4.2 concurrencia | `test_concurrencia.py` (2) | ➖ green-first c/lock | ✅ | n/a | ✅ — |
| 4.3 auditoría | `test_auditoria.py` (3) | ➖ green-first | ✅ | n/a | ✅ — |

Comando: `py -m pytest tests/ -q` → **104 passed**.
