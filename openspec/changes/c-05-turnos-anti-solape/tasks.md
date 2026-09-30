# Tasks — C-05 `turnos-anti-solape`

> Fase Propose: todo queda en `[ ]`. No implementar nada en esta fase.

## 1. Dominio standalone (testeable con Node 24)

- [ ] 1.1 Implementar `overlap()` half-open `[inicio, fin)` con tests: solape
  parcial/total/contenido falla y adyacencia exacta (`fin_A == inicio_B`)
  pasa; verificar con `node --test` o `vitest` en verde
- [ ] 1.2 Implementar cálculo `fin = inicio + prestacion.duracion_min`
  (ignora/contrasta `fin` del cliente) con tests para duraciones 30/45/60
  min; verificar que un `fin` cliente distinto es rechazado
- [ ] 1.3 Implementar selector de 3 alternativas ante `409` (siguiente hueco
  real por profesional × sillón × duración, menos bloqueos) con tests de
  orden y cantidad; verificar que siempre devuelve ≤3 huecos válidos
- [ ] 1.4 Implementar máquina de estados
  (`PENDIENTE→CONFIRMADO→PRESENTE/AUSENTE`, `→CANCELADO`,
  `→REPROGRAMADO` + nuevo turno) con tests de transiciones legales/ilegales;
  verificar que `CANCELADO`/`REPROGRAMADO` liberan el hueco

## 2. Persistencia (migración 003 + RLS)

- [ ] 2.1 Escribir migración 003: extensión `btree_gist`, tabla `turnos`
  (`timestamptz`, `sobreturno default false`, `origen`, `token_publico?`)
  con `tenant_id NOT NULL`; verificar `prisma migrate diff` sin errores
- [ ] 2.2 Agregar los 2 EXCLUDE parciales (`(tenant, profesional)` y
  `(tenant, sillón)` sobre `tstzrange(inicio, fin)`,
  `WHERE` excluye `CANCELADO`/`REPROGRAMADO` y `sobreturno=true`); verificar
  con test SQL que el solape inserta error y la adyacencia exacta inserta OK
- [ ] 2.3 Crear índices `(tenant, profesional, inicio)`,
  `(tenant, sillón, inicio)`, `(tenant, estado)` y política RLS
  (`tenant_id = current_setting('app.tenant_id')`); verificar con
  `EXPLAIN` que la búsqueda de hueco usa índice y con test que un tenant no
  ve turnos ajenos
- [ ] 2.4 Seed ficticio de test (1 tenant, profesional, sillón, prestación
  30 min, sin PHI); verificar seed idempotente y reutilizable en tests

## 3. API de turnos (zod en borde, tipado estricto)

- [ ] 3.1 Implementar `CRUD /api/turnos` (crear valida hueco real y calcula
  `fin`; leer filtra por `tenant_id`; actualizar solo campos permitidos;
  sin `any`); verificar con tests de contrato por rol (RBAC C-03)
- [ ] 3.2 Implementar `POST /api/turnos/:id/sobreturno` (motivo obligatorio
  no vacío → `422` si falta; escribe auditoría append-only con actor,
  motivo, antes/después); verificar con test que sin motivo no persiste y
  con motivo audita
- [ ] 3.3 Implementar `POST /api/turnos/:id/cancelar|reprogramar`
  (anticipación mínima configurable, default 24 h; debajo del umbral solo
  recepción + auditoría; reprogramar revalida solape en transacción);
  verificar con tests de anticipación, `409` en destino ocupado y
  atomicidad (original intacto si falla)
- [ ] 3.4 Devolver `409 + 3 alternativas` en todo rechazo por solape
  (crear/reprogramar/sobreturno-accidental); verificar con test que el body
  trae exactamente el formato de alternativas de 1.3

## 4. Regresión y auditoría (condición de merge)

- [ ] 4.1 Test de regresión agenda: solape profesional falla, solape sillón
  falla, adyacencia pasa, cancelado/reprogramado no bloquea, sobreturno sin
  motivo falla; verificar suite completa en verde
- [ ] 4.2 Test de concurrencia doble-reserva (dos inserciones simultáneas al
  mismo hueco): solo una confirma, la otra recibe `409`; verificar sin
  flakiness (repetir N veces)
- [ ] 4.3 Test de auditoría: sobreturno, cancelación y reprogramación dejan
  rastro append-only consultable con antes/después; verificar que no hay PHI
  en logs
- [ ] 4.4 `openspec validate --change c-05-turnos-anti-solape --strict` en
  verde y documentar el follow-up UI `(app)/agenda` como change separado;
  verificar que ningún task de UI quedó en este change
