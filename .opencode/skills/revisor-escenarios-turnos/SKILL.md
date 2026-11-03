---
name: revisor-escenarios-turnos
description: Audita una delta spec de OpenSpec de Turnos-Odontologia contra las reglas RN-XX de la knowledge base antes de implementarla. Detecta escenarios faltantes (feliz, error de negocio, borde), reglas ambiguas o sin cobertura, huecos de aislamiento multi-tenant y valores de dominio inventados. Usala al preparar o revisar un change (opsx propose, opsx verify) y cuando el pedido sea "revisá los escenarios", "¿falta algún caso borde?", "¿esta spec es verificable?", "auditá el spec antes de implementar". Si hay un spec.md de turnos por implementar en la carpeta de la capability, cargala aunque no nombren la skill.
---

# Revisor de escenarios de turnos

Audita una delta spec de OpenSpec contra las RN-XX de la knowledge base antes de que se implemente. El objetivo es que el código nazca de escenarios verificables y de valores que la KB ya decidió, no de valores que el agente completa porque suenan razonables.

## Cuándo usarme

- Al preparar un change de turnos (`propose`) o al verificarlo antes de archivar (`verify`).
- Cuando el pedido es "revisá los escenarios", "¿falta algún caso borde?", "¿esta spec es verificable?", "auditá el spec antes de implementar".
- Cuando hay un `specs/<capability>/spec.md` de turnos por implementar, aunque nadie nombre esta skill.

No la uses para escribir la spec desde cero (eso es `openspec-propose`) ni para implementar.

**Solo lee y reporta.** No edites la spec, las tasks ni el código: si encontrás un hueco lo describís con su
cita, y la corrección la decide el equipo. Un revisor que reescribe pierde la trazabilidad de qué estaba mal.

## Contexto del proyecto

- Reglas de negocio: `knowledge-base/05_reglas_de_negocio.md` (códigos `RN-{DOMINIO}-{NN}`).
- Modelo y funcionalidades: `knowledge-base/04_modelo_de_datos.md` y `06_funcionalidades.md` cuando el escenario toca entidades o historias.
- Actores, RBAC y rutas públicas: `knowledge-base/03_actores_y_roles.md`.
- Flujos E2E: `knowledge-base/07_flujos_principales.md`.
- Valores abiertos: `knowledge-base/10_preguntas_abiertas.md`.
- Scope por change: la sección "Leer antes" de `CHANGES.md`.
- Changes: `openspec/changes/<name>/`; specs vivas en `openspec/specs/<capability>/spec.md`; archivadas en `openspec/changes/archive/`.

## Prefijos del dominio

| Prefijo | Qué cubre | RN críticas |
|---|---|---|
| `RN-AG` | Agenda: duración derivada, anti-solape por profesional/sillón en DB, sobreturno auditado, bloqueos, aislamiento por tenant, intersección de horarios | RN-AG-01, RN-AG-02, RN-AG-03, RN-AG-05 |
| `RN-RE` | Reserva online: slots reales servidor-side, token anti-spam, anticipación mínima configurable, lista de espera con auto-oferta, identificación liviana | RN-RE-01, RN-RE-03, RN-RE-04 |
| `RN-SE` | Señas y Mercado Pago: liberación por `expira_at`, estados, webhook idempotente, política visible, monto por tenant | RN-SE-01, RN-SE-03, RN-SE-05 |
| `RN-CL` | Clínica: odontograma FDI, presupuesto con aceptación parcial, evoluciones inmutables, PHI fuera de logs | RN-CL-02, RN-CL-03, RN-CL-04 |
| `RN-OS` | Obras sociales: cobertura configurable (no validada en vivo), liquidación, 3–5 OS iniciales | RN-OS-01, RN-OS-02 |
| `RN-CJ` | Caja: multi-medio, cierre diario con diferencia 0 o motivo, anulación trazable | RN-CJ-01, RN-CJ-02, RN-CJ-03 |
| `RN-AU` | Auth/RBAC por `(tenant_id, rol)`, auditoría append-only, consentimiento previo, exportación, 2FA | RN-AU-01, RN-AU-02, RN-AU-03 |
| `RN-IN` | Integraciones: WhatsApp oficial, Google Calendar bidireccional, degradación con gracia | RN-IN-01, RN-IN-02, RN-IN-03 |
| `RN-GL` | Globales: ninguna conveniencia viola anti-solape ni auditoría; gana la disponibilidad real; datos de ejemplo ficticios | RN-GL-01, RN-GL-02, RN-GL-03 |

## Entradas

1. Ruta del change (`openspec/changes/<name>/`).
2. Capability afectada (carpeta bajo `specs/`).
3. Lista de RN del scope, tomada de "Leer antes" en `CHANGES.md`.
4. Archivos de `knowledge-base/` que correspondan a esas RN.

Si falta cualquiera, pedila. No completes el scope con RN que la KB no asigne al change.

## Procedimiento

1. **Extraer la spec.** Leé `specs/<capability>/spec.md` y listá cada `### Requirement:` con sus `#### Scenario:`. El formato del repo es DADO / CUANDO / ENTONCES en viñetas.
2. **Extraer las RN del scope.** Tomá los códigos de "Leer antes" en `CHANGES.md` y leé su texto literal en `05_reglas_de_negocio.md`; sumá `04_modelo_de_datos.md`, `06_funcionalidades.md` o `07_flujos_principales.md` si el requirement toca entidades, historias o flujos.
3. **Armar la matriz de cobertura.** Una fila por RN del scope, una columna por tipo: feliz, error de negocio, borde, concurrencia/idempotencia. Marcá cada celda con el escenario que la cubre o con `HUECO`. Una RN sin escenario es un hallazgo, no una omisión aceptable.
4. **Validar la forma de cada escenario.** Debe tener DADO/CUANDO/ENTONCES completo, valores literales (fechas con zona, estados, códigos HTTP), un resultado observable, y en los errores de negocio la constancia de que NO se muta estado. Si dice "funciona correctamente" o "responde error", no es verificable.
5. **Detectar valores de dominio inventados.** Compará números, montos, topes, plazos y estados contra `10_preguntas_abiertas.md`. Siguen abiertos: `PO-01` (seña siempre/por prestación, monto fijo o %, anticipación mínima exacta), `PO-03` (profundidad WA/MP/GCal), `PO-05` (uno o varios profesionales en el piloto), `PO-06` (login de paciente vs. nombre + teléfono), y `PO-02`/`PO-04`/`PO-07`/`PO-08`/`PO-10`/`PO-11` en su alcance (precios, validación OS realtime/aranceles, ARCA, cumplimiento legal, material de competidores). Si la spec los fija, es BLOQUEANTE.
6. **Revisar bordes propios del dominio.** Temporales: reloj del servidor vs. cliente, igualdad exacta del umbral de anticipación (`RN-RE-03`, default declarado en la KB), fecha real cuando debería estar congelada. Multi-tenant: toda query con `tenant_id` + RLS, y un token del tenant A no puede leer ni operar recursos del B. Privacidad: PHI fuera de logs y mensajes (`RN-CL-04`). Auto-oferta: expiración y reclamo único del hueco (`RN-RE-04`). Idempotencia: webhooks de pago (`RN-SE-03`) y recordatorios/confirmaciones WA (`RN-IN-01`, `RN-IN-03`). Dinero y clínica: caja y medios de pago (`RN-CJ-01/02/03`), obras sociales (`RN-OS-01`), consentimiento previo a lo clínico (`RN-AU-03`).
7. **Verificar `tasks.md`.** Cada escenario debe tener una tarea que diga cómo se verifica al implementarlo. Si la tarea no existe o no nombra el test, el escenario no se va a cumplir.

## Salida

Informe markdown con estas secciones, en este orden:

1. **Tabla de cobertura**: `RN | Requirement | Feliz | Error de negocio | Borde | Concurrencia/idempotencia`, con `HUECO` donde falte.
2. **Hallazgos**: tabla `Severidad | Hallazgo | Cita (archivo:línea) | RN`. Usá `BLOQUEANTE`, `MAYOR` o `MENOR`.
3. **Preguntas abiertas detectadas**: las de `10_preguntas_abiertas.md` que la spec tocó y resolvió por su cuenta.
4. **No verificado**: lo que no pudiste comprobar y por qué.

## Severidad

- **BLOQUEANTE**: valor abierto inventado, RN crítica sin escenario, fuga cross-tenant, PHI en logs o mensajes, error de negocio que muta estado, o violación de las reglas duras de `AGENTS.md` (anti-solape solo en aplicación, falta de test de regresión en agenda/caja/señas).
- **MAYOR**: escenario no verificable, falta un borde relevante o el `tasks.md` no dice cómo verificarlo.
- **MENOR**: redacción ambigua que no cambia el comportamiento.

## Criterios de revisión del informe

- Ningún hallazgo sin cita a una RN o a un archivo de la KB con línea.
- Ningún valor numérico propuesto que la KB no respalde.
- Mínimo 3 escenarios por requirement crítico (anti-solape, anticipación, estados, idempotencia de pago, auto-oferta).
- Prohibido proponer tests tautológicos: el valor esperado sale de la RN o de un ejemplo trabajado, no de recalcular lo que hace el código.

## Ejemplo de hallazgo

`BLOQUEANTE | La spec fija la seña en un monto cerrado cuando PO-01 la declara abierta | specs/<capability>/spec.md:23 | RN-SE-05`

## Reglas duras de este repo (AGENTS.md §Reglas Duras)

- NUNCA usar `any` en el frontend → tipado estricto TypeScript en todo el código TS (borde API validado con schemas compartidos/Pydantic en backend).
- NUNCA código Python sin type hints ni queries crudas → todo type-hinteado y acceso a datos solo vía SQLAlchemy (SQL crudo únicamente dentro de migraciones Alembic).
- NUNCA hacer una query sin tenant → toda tabla de negocio filtra por `tenant_id` y tiene RLS (`tenant_id = current_setting('app.tenant_id')`).
- NUNCA violar RN-AG-02/RN-AU-02 por conveniencia → anti-solape y aislamiento por tenant se cumplen siempre, sin atajos.
- NUNCA usar datos reales de pacientes → solo datos ficticios en desarrollo, tests y demos.
- NUNCA poner secretos en el repo → env vars (`.env.example` como referencia); sin PHI en logs ni en mensajes.
- NUNCA hacer commit/push sin pedido → conventional commits, sin co-autoría IA.
- NUNCA mergear agenda/caja/señas sin test de regresión → la regresión en verde es condición de merge.
