# Contrato público — Reserva online sin login (C-06 + catálogo F-02)

> Superficie expuesta por el link público `/r/:tokenTenant`. Todo request se
> resuelve primero a un `tenant_id` desde el segmento `{tokenTenant}` de la ruta;
> los headers de actor (`X-Tenant-Id`, `X-Rol`, …) se ignoran en las rutas
> públicas. Errores de dominio → `{ "detalle": str, "alternativas": [...] }`;
> rate-limit → `429` con `Retry-After`. Las respuestas y los logs nunca exponen
> nombre, teléfono ni dato clínico de terceros (RN-CL-04).

## Endpoints

| Método | Ruta | Éxito | Payload / params |
|---|---|---|---|
| GET | `/api/publico/{tokenTenant}/catalogo` | `200` prestaciones + profesionales activos (F-02 / OQ-F1) | — |
| GET | `/api/publico/{tokenTenant}/disponibilidad` | `200` lista de huecos | query `prestacion` (obligatorio), `profesional` (opcional), `desde` (obligatorio, datetime aware) |
| POST | `/api/publico/{tokenTenant}/verificacion` | `201` | body `{ "accion": "reservar" | "cancelar" | "reprogramar" }` |
| POST | `/api/publico/{tokenTenant}/reservas` | `201` | body `{ prestacion, profesional, inicio, nombre, telefono, verificacion_id }` (strict) |
| GET | `/api/publico/{tokenTenant}/reservas/{token}` | `200` | — |
| POST | `/api/publico/{tokenTenant}/reservas/{token}/cancelacion` | `200` | body `{ "verificacion_id": str }` (strict) |
| POST | `/api/publico/{tokenTenant}/reservas/{token}/reprogramacion` | `200` | body `{ "nuevo_inicio": datetime, "verificacion_id": str }` (strict) |

## Formas de respuesta (allow-list, sin `TurnoOut`)

- **Catálogo** (`200`): `prestaciones: [{ id, nombre, duracion_min }]` (todas
  las del tenant; en v1 la prestación no tiene flag `activo`) y
  `profesionales: [{ id, nombre }]` (solo activos). Sin `tenant_id`, precios,
  horarios ni PHI. Tenant activo sin datos ⇒ listas vacías.
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

## Config resuelta (OQ-1..OQ-5; detalle en `docs/decisiones-oq.md`)

`RESERVA_TTL_H=48`, `CANCEL_ANTICIPACION_H=24`, `PUBLIC_RATE_LIMIT_MAX=10`,
`PUBLIC_RATE_LIMIT_VENTANA_S=900`, `PUBLIC_VERIFICACION_TTL_MIN=10`,
`PUBLIC_DISPONIBILIDAD_HORIZONTE_D=30`, `PUBLIC_ANTISPAM_MODO=captcha`.
Ver `.env.example`.
