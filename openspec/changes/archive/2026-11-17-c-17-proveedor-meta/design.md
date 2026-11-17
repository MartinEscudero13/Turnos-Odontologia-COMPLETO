# Design — C-17 Meta WhatsApp Cloud API

## Decisions

**D1 — Mismo puerto, otro adaptador.**
`PasarelaMeta` implementa `PasarelaWhatsAppPort`. La selección es `meta_desde_env()` →
`twilio_desde_env()` → `PasarelaWhatsAppFake`, así el dominio no conoce al proveedor.

**D2 — Webhook normalizado.**
`eventos_meta(payload)` aplana `entry[].changes[].value.statuses[]` y `messages[]` al contrato interno
(`MessageSid`, `Body`, `MessageStatus`). El servicio existente no cambia su lógica de negocio.

**D3 — Respuestas sin id del mensaje citado.**
Meta manda `context.id` sólo si el usuario cita el mensaje. Si falta, `ServicioWhatsApp` resuelve el
paciente por teléfono (`paciente_por_telefono`) y toma su último mensaje (`ultimo_por_paciente`). La
misma mejora aplica al webhook de Twilio, que tampoco garantiza `OriginalRepliedMessageSid`.

**D4 — Firma fail-closed.**
El POST exige `META_APP_SECRET` y valida `X-Hub-Signature-256` (HMAC-SHA256 sobre el cuerpo crudo). Sin
secreto responde `503`; firma inválida `401`. La verificación GET exige `META_VERIFY_TOKEN`.

**D5 — Versión configurable.**
`META_API_VERSION` por defecto `v23.0`; se puede cambiar sin tocar código si Meta publica una versión
nueva o retira la actual.

## Risks / Trade-offs

- El token temporal dura 24 h: suficiente para la demo, no para producción.
- El número de prueba sólo envía a destinatarios agregados en la app de Meta (hasta 5).
- La resolución por teléfono asume un último recordatorio; con varios turnos activos conviene citar el
  mensaje (`context.id`).
- El webhook necesita una URL HTTPS pública (ngrok/Cloudflare Tunnel).

## Verification

- `tests/test_whatsapp_meta.py` (adaptador, eventos, firma).
- `tests/test_demo_api_whatsapp.py` (verificación GET, respuestas SI/NO, estados y firma).
- `tests/test_whatsapp.py` (resolución por teléfono y config compartida).
- Suite completa local y con PostgreSQL; `ruff`, `mypy`, frontend y OpenSpec.
