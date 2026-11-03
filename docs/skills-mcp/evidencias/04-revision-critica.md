# Evidencia 04 — Revisión crítica antes/después: C-06 con la skill

**Fecha**: 2026-11-03 · **Cambio**: `openspec/changes/c-06-reserva-online-publica/`

## Antes

La propuesta de C-06 pasó por `openspec validate --strict` **antes** de la auditoría: `is valid`. Un change
"válido" para el CLI no es una spec verificable por humanos. Auditoría con la skill
(`docs/skills-mcp/evidencias/02-descubrimiento-skill.md`) — salida completa condensada en
`openspec/changes/c-06-reserva-online-publica/revision.md`:

**4 BLOQUEANTES**

1. **Tenant ausente en las rutas API** — los escenarios de aislamiento no se podían ni escribir (la spec pedía
   resolver el tenant desde `/r/:tokenTenant` pero sus endpoints eran `/api/disponibilidad` y
   `/api/reservas/publicas`, sin ese segmento).
2. **Verificación liviana sin emisor** — cada acción pública la exige, pero ningún endpoint la emite: el `201` sólo
   era ejercitable inyectando un mock, no como HTTP real.
3. **Escenarios de anticipación caducos** — fijados al `2026-10-10`; con el reloj real (2026-11-03) el delta es
   negativo ⇒ `403` donde el escenario esperaba `200`. La suite de C-05 siempre pasa `ahora=`; `tasks.md` no lo exigía.
4. **RN-RE-03 "queda auditado" sin escenario ni tarea** — el rechazo bajo umbral no dejaba rastro verificable.

**10 MAYORES**, entre ellos: fin no derivable (el `422` dependía de `fin` sin `inicio`), falta el happy path de
reprogramación, reprogramar bajo umbral sin borde, TTL/reuso concurrente de la verificación sin escenario,
rate-limit por tenant no probado, deduplicación de paciente por teléfono sin concurrencia, fixture `+540000000000`
**no es E.164 y la KB no fija un prefijo por defecto** (valor inventado en `tasks.md`), y "exactamente 3
alternativas" en lugar de "las que existan".

Snapshot intacto: `docs/skills-mcp/evidencias/c-06-spec-antes-de-revision.md` (306 líneas).

## Después

- Superficie pública coherente: `/api/publico/{tokenTenant}/...` (el segmento lo fijan la landing `/r/:tokenTenant`
  y la API), con `TenantPort` y `activo=false` ⇒ `404`.
- Contrato del emisor `POST /api/publico/{tokenTenant}/verificacion` y sus escenarios (emisión `201`, vencida,
  un solo uso, reuso concurrente).
- Todos los escenarios temporales redactados **relativos a un reloj congelado explícito**; `tasks.md` exige
  `ahora=` en cada test.
- Entrada append-only de rechazo (`CANCELACION_RECHAZADA` / `REPROGRAMACION_RECHAZADA`, motivo `BAJO_ANTICIPACION`).
- `"exactamente 3"` → "hasta 3 alternativas (las que existan)". Fixture inválido reemplazado por `+5491130551234`.
- Escenarios agregados: reprogramación exitosa, reprogramar bajo umbral, inicio fuera de grilla, `GET
  /api/publico/{tokenTenant}/reservas/{token}`.

**Formato tras corregir**: 10 requirements · **48 escenarios** · **50 tareas** · `openspec validate --strict`
⇒ `is valid`, exit 0, **sin warnings** · suite C-05 intacta (**104 passed**).

## Qué se aprendió

- El CLI valida sintaxis de deltas; **no** valida verificabilidad, cobertura por RN ni que los escenarios sean
  ejecutables. La skill ordena ese hueco.
- El error más peligroso no era el obvio (rutas) ni el de estilo: fueron los escenarios "que pasaban" por accidente
  de reloj real. Un test de suite verde no prueba nada sobre la anticipación.

## Estado honesto

El change sigue sin implementar: este es el valor del TP — poder **ver el error antes** de escribir código.
