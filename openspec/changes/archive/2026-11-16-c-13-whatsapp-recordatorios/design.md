# Design — C-13 WhatsApp con Twilio

## Context

Twilio WhatsApp Sandbox permite enviar mensajes a números que se unieron con un código, sin app de
Meta ni verificación de negocio. La API es REST y el webhook llega como `application/x-www-form-urlencoded`.
Ver `proposal.md`.

## Decisions

**D1 — Twilio detrás de un puerto.**
`PasarelaWhatsAppPort` abstrae el proveedor. `PasarelaTwilio` usa `urllib` (sin SDK) y
`PasarelaWhatsAppFake` permite tests y demo sin credenciales. `WA_PROVIDER=twilio|fake`; si faltan
credenciales, se usa fake y se declara.

**D2 — Mensaje como registro persistente.**
`mensajes_wa` guarda tenant, paciente, turno, plantilla (`RECORDATORIO`, `CONFIRMACION`, `CANCELACION`,
`RECALL`), canal (`WA`, `EMAIL`), estado (`PENDIENTE`, `ENVIADO`, `ENTREGADO`, `LEIDO`, `FALLIDO`),
`provider_message_id` único, intentos, próximo intento, cuerpo y respuesta.

**D3 — Idempotencia.**
Un recordatorio se crea una sola vez por `(tenant, turno, plantilla)` en estado no fallido. Un segundo
pedido devuelve el existente. El webhook resuelve por `provider_message_id`.

**D4 — Respuestas y agenda.**
`Body` normalizado:
- `SI`/`SÍ`/`CONFIRMO` → `TurnoPort.confirmar` (PENDIENTE → CONFIRMADO).
- `NO`/`CANCELO` → `TurnoPort.cancelar` + `HuecoLiberadoPort.emitir` (C-07).
- Cualquier otro texto → respuesta ambigua, se devuelve `link_confirmacion`.
La cancelación por WhatsApp respeta la anticipación mínima de C-05; si el turno ya no es cancelable,
se registra `NO_APLICADO` y no se toca la agenda.

**D5 — Degradación.**
Si Twilio falla, el mensaje queda `FALLIDO` y se encola un reintento; además se crea un mensaje `EMAIL`
por el fallback (adaptador de log en v1). La agenda sigue operando.

**D6 — Firma Twilio.**
El webhook valida `X-Twilio-Signature` con HMAC-SHA1 sobre la URL pública + parámetros ordenados y el
`TWILIO_AUTH_TOKEN`. Sin token configurado, el endpoint responde `503` fail-closed (igual que MP).

**D7 — Recall separado.**
`RECALL` exige motivo clínico y fecha objetivo; no comparte plantillas ni campañas de marketing.

**D8 — Migración 012.**
C-14 usó 011; C-13 toma 012. `mensajes_wa` con RLS, UNIQUE parcial de `provider_message_id` y grants
por columna.

## Risks / Trade-offs

- El sandbox sólo envía a números unidos y la sesión dura 24 h: sirve para demo, no producción.
- Las plantillas de producción requieren aprobación de Meta; se declara.
- El email fallback es un log hasta configurar SMTP.
- La confirmación por WhatsApp es una transición nueva de C-05; se cubre con regresión.

## Verification

- Dominio: recordatorio idempotente, fallback, reintentos, webhook SI/NO/ambiguo, recall, RBAC.
- HTTP demo: programar, listar, webhook firmado, rechazo de firma, cancelación con hueco.
- PostgreSQL: RLS, UNIQUE de `provider_message_id`, roundtrip.
- Frontend: página WhatsApp con programar, mensajes y recall.
- Suite completa, `ruff`, `mypy`, OpenSpec strict.
