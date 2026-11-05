# Contrato público — Reserva online sin login (C-06)

> Superficie expuesta por el link público `/r/:tokenTenant`. Todo request se
> resuelve primero a un `tenant_id` desde el segmento `{tokenTenant}` de la ruta;
> los headers de actor (`X-Tenant-Id`, `X-Rol`, …) se ignoran en las rutas
> públicas. Errores de dominio → `{ "detalle": str, "alternativas": [...] }`;
> rate-limit → `429` con `Retry-After`. Las respuestas y los logs nunca exponen
> nombre, teléfono ni dato clínico de terceros (RN-CL-04).

## Endpoints

| Método | Ruta | Éxito | Payload / params |
|---|---|---|---|
| GET | `/api/publico/{tokenTenant}/disponibilidad` | `200` lista de huecos | query `prestacion` (obligatorio), `profesional` (opcional), `desde` (obligatorio, datetime aware) |
| POST | `/api/publico/{tokenTenant}/verificacion` | `201` | body `{ "accion": "reservar" | "cancelar" | "reprogramar" }` |
| POST | `/api/publico/{tokenTenant}/reservas` | `201` | body `{ prestacion, profesional, inicio, nombre, telefono, verificacion_id }` (strict) |
| GET | `/api/publico/{tokenTenant}/reservas/{token}` | `200` | — |
| POST | `/api/publico/{tokenTenant}/reservas/{token}/cancelacion` | `200` | body `{ "verificacion_id": str }` (strict) |
| POST | `/api/publico/{tokenTenant}/reservas/{token}/reprogramacion` | `200` | body `{ "nuevo_inicio": datetime, "verificacion_id": str }` (strict) |

## Formas de respuesta (allow-list, sin `TurnoOut`)

- **Disponibilidad** (por hueco): `inicio`, `fin`, `profesional_id`, `sillon_id`.
- **Reserva creada** (`201`): `turno_id`, `estado`, `inicio`, `fin`, `origen`,
  `prestacion`, `sillon_id`, `token_publico`.
- **Consulta del turno propio** (`200`): `turno_id`, `estado`, `inicio`, `fin`,
  `prestacion`, `token_publico`.

## Códigos de error

| Código | Causa |
|---|---|
| `403` | verificación liviana inválida/vencida/reusada, o acción bajo `CANCEL_ANTICIPACION_H` |
| `404` | `tokenTenant` inexistente/inactivo, o `token` inexistente/ajeno (cuerpo uniforme) |
| `409` | hueco/sillón ocupado, o `inicio` fuera de la grilla o bloqueado → hasta 3 alternativas |
| `422` | payload con campos fuera del allow-list (incluye `fin`, `sobreturno`, `tenant_id`) |
| `429` | rate-limit por `(tenant, IP)` o `(tenant, acción)` excedido → `Retry-After` |

## Reglas de dominio

- El `fin` siempre lo calcula el servidor (`fin = inicio + duracion_min`); el
  cliente no lo envía.
- El sillón lo elige el servidor entre los activos libres.
- Anticipación exacta (`CANCEL_ANTICIPACION_H`, default 24 h) **acepta** en el
  umbral; un minuto menos rechaza `403` sin mutar y deja entrada auditada de
  rechazo (`BAJO_ANTICIPACION`).
- `token_publico` UUID v4, uno por turno, transferido al reprogramar; deja de
  servir cuando el turno pasa a `CANCELADO`/`REPROGRAMADO`/`PRESENTE`/`AUSENTE` o
  su `fin` ya pasó.

## Config (nombres, sin valores fijados — OQ-1..OQ-5)

`RESERVA_TTL_H`, `CANCEL_ANTICIPACION_H`, `PUBLIC_RATE_LIMIT_MAX`,
`PUBLIC_RATE_LIMIT_VENTANA_S`, `PUBLIC_VERIFICACION_TTL_MIN`,
`PUBLIC_DISPONIBILIDAD_HORIZONTE_D`, `PUBLIC_ANTISPAM_MODO`.
Ver `.env.example` para los nombres reservados.
