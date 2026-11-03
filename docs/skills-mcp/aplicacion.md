# Informe de aplicación — skill propia + MCP (TP2)

**Proyecto**: Turnos-Odontologia (`C:\Users\tinch\Desktop\Turnos-Odontologia`) · **Fecha**: 2026-11-03 · **Método**: equipo Naranjo–Escudero

## Resumen ejecutivo

Se incorporó al ciclo SDD del proyecto una **skill propia** (`revisor-escenarios-turnos`) y la integración
documentada del **MCP Context7**. La skill auditó un change pendiente (`C-06 reserva-online-publica`) y detectó
**4 bloqueantes antes de escribir una línea de código**; todos fueron corregidos. El change permanece en estado
**preparado, no implementado**.

## Por qué esta skill

El riesgo estructural del proyecto no es escribir código, es escribirlo sobre una spec que parece completa y no lo
es: valores de dominio abierto (`CANCEL_ANTICIPACION_H`, `RESERVA_TTL_H`), escenarios que sólo pasan con el reloj
real o sólo inyectando mocks, y aislamiento multi-tenant sin ruta. Una revisión humana agotada por volumen no
divide ese trabajo en una matriz auditable.

La skill implementa exactamente eso: matriz **RN × (feliz / error de negocio / borde / concurrencia)**, hallazgos con
severidad (`BLOQUEANTE|MAYOR|MENOR`) y cita `archivo:línea`, preguntas abiertas detectadas, y sección **No verificado**.

## Adaptación al dominio

- Vocabulario RN: `RN-AG`, `RN-AU`, `RN-CJ`, `RN-CL`, `RN-GL`, `RN-IN`, `RN-OS`, `RN-RE`, `RN-SE` (este repo),
  reemplazando los códigos del proyecto hermano que **no existen acá**.
- Reglas duras citadas textualmente del `AGENTS.md` (tenant_id + RLS, anti-solape en DB, datos ficticios, sin
  secretos, PHI fuera de logs, anti-solape sin atajos).
- Huecos propios: aislamiento multi-tenant (`tenant_id` + RLS), consentimiento clínico, caja y obras sociales en
  la RLS, idempotencia de webhooks y auto-oferta con vencimiento.
- Valores abiertos cruzados con `10_preguntas_abiertas.md` (PO-01, PO-06, OQ-1..OQ-9).

## Resultado de la auditoría: antes / después

| Antes | Después |
|---|---|
| `validate --strict` "válido", spec inverificable | 10 requirements · **48 escenarios** · **50 tareas** |
| tenant inexistente en las rutas | `/api/publico/{tokenTenant}/...` resuelto una vez/req |
| sin contrato para la verificación liviana | `POST .../verificacion` (`201`, `verificacion_id`, `expira_at`) |
| escenarios que caducan con el reloj real | todos relativos a reloj congelado; tasks exigen `ahora=` |
| rechazo bajo umbral sin auditoría | `CANCELACION_RECHAZADA` (append-only, sin PHI) |

Detalle completo: `evidencias/04-revision-critica.md` y
`openspec/changes/c-06-reserva-online-publica/revision.md`
(snapshot del "antes" preservado en `evidencias/c-06-spec-antes-de-revision.md`).

## MCP Context7

Conexión verificada en esta máquina; llamada real (`resolve-library-id` + `query-docs`) documentada en
`evidencias/03-mcp-context7.md`. Es una **integración**, no una skill: no se registra en `.atl/skill-registry.md`.
El repo versiona sólo `docs/skills-mcp/mcp.json.example`; la configuración viva del cliente queda fuera (proyecto >
global). `opencode mcp debug` **no existe** en la versión instalada — se documenta la verificación correcta
(`opencode mcp list`) para no dejar instrucciones falsas.

## Archivos creados / modificados

```
.opencode/skills/revisor-escenarios-turnos/SKILL.md     (nuevo, 99 líneas)
.atl/skill-registry.md                                (Project Skills)
AGENTS.md / CLAUDE.md                                (idénticos; skill + §MCP + paso 4 del flujo)
README.md                                             (§MCP)
docs/skills-mcp/                                      (investigacion, aplicacion, mcp.json.example,
                                                       README, vendor/skill-creator, evidencias/)
openspec/changes/c-06-reserva-online-publica/         (change preparado + revision.md)
```

## Límites y honestidad

- Una sola spec auditada y una sola pasada de la skill: suficiente para el TP, no para generalizar a todo el
  roadmap.
- El change **no se implementó**: la evidencia mide capacidad de detección, no "tiempo ganado implementando".
- `quick_validate.py` verifica estructura, no semántica; la cobertura semántica es trabajo humano.
- La verificación de descubrimiento (evidencia 02) es una sola prueba, en este cliente.

## Qué falta para darlo por cerrado

1. Commits de todo lo anterior (pendientes de pedido explícito del dueño; no se commitea sin que lo pida).
2. Video del TP (≤5 min), fuera del repo.
3. Antes de `/opsx:apply c-06-reserva-online-publica`, re-auditar con la skill si el PO cierra OQ-1..OQ-9.
