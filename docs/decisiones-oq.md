# Decisiones OQ-1..OQ-9 — C-06 `reserva-online-publica`

> Fecha: 2026-11-05 · Resolución de las preguntas abiertas del design de C-06.
> Fuente original: `openspec/changes/archive/2026-11-05-c-06-reserva-online-publica/design.md` §"Preguntas abiertas".
> Clasificación: **Técnica** (default razonable, lo fija el equipo) · **Provisional** (recomendación, confirmar con el dueño) · **Diferida** (pertenece a otro change) · **Resuelta** (ya quedó fijada en la spec).
> Confirmación: las 3 provisionales (OQ-1/OQ-2/OQ-8) fueron **aprobadas por Lautaro** (dueño del change) el 2026-11-05; quedan como recomendación documentada para el dueño de producto (Martin) por si disiente.

## Resumen

| OQ | Decisión | Clasificación |
|---|---|---|
| OQ-1 | `RESERVA_TTL_H = 48` | Provisional (negocio) |
| OQ-2 | `PUBLIC_ANTISPAM_MODO = captcha` | Provisional (negocio) |
| OQ-3 | 10 req / 15 min por IP · 30 req / 15 min por tenant | Técnica |
| OQ-4 | `tokenTenant` = token aleatorio opaco (no slug) | Técnica (seguridad) |
| OQ-5 | `PUBLIC_DISPONIBILIDAD_HORIZONTE_D = 30` | Técnica |
| OQ-6 | Sin lead time (mismo día reservable) | Resuelta |
| OQ-7 | Sin seña en C-06 → se resuelve en C-11 | Diferida |
| OQ-8 | Vincula por teléfono sin pisar nombre; reserva para terceros fuera de v1 | Provisional (negocio) |
| OQ-9 | Confirmación = respuesta HTTP + token; canal real en C-13 | Diferida |

## Detalle

### OQ-1 — `RESERVA_TTL_H` (ventana de reserva pendiente)

**Decisión:** `48` horas.

**Por qué:** la KB (`08_arquitectura_propuesta.md:56`) muestra `48` como ejemplo de la columna; da 2 días de gracia al turno `PENDIENTE` antes de la liberación automática. El valor final queda atado al alcance de la seña (C-11, OQ-7): si C-11 introduce seña con vencimiento propio, `RESERVA_TTL_H` puede pasar a ser el techo sin-seña.

**Nota:** el placeholder de C-01 en `.env.example` decía `24`; se actualiza a `48` (respaldo KB). *Provisional — confirmar con el dueño.*

### OQ-2 — Verificación liviana: captcha u OTP

**Decisión:** **captcha** (modo `captcha`).

**Por qué:** RN-IN-01 descarta SMS sin proveedor real (`09_decisiones_y_supuestos.md:42`); OTP por WhatsApp exige BSP activo (C-13, que aún no existe). Un captcha liviano es independiente de proveedor de mensajería, más barato y suficiente contra bots en v1. El `VerificadorPort` ya abstrae el proveedor (task 4.4): migrar a OTP después no toca el dominio.

**Nota:** para el MVP se puede usar un captcha alojado (p. ej. Turnstile/hCaptcha) o un proof-of-work; el puerto no depende de cuál. *Provisional — confirmar con el dueño.*

### OQ-3 — Umbrales de rate-limit

**Decisión:** **10** requests / **15 min (900 s)** por IP, **30** requests / **15 min** por tenant (clave `(tenant, acción)`).

**Por qué:** la KB exige rate-limit sin dar umbrales (`03:35`, `09:45`). Estos topes son estándar anti-abuso y van en capas con la verificación single-use: el contador frena ráfagas, la verificación frena bots sin usuario real. Config en `PUBLIC_RATE_LIMIT_MAX` / `PUBLIC_RATE_LIMIT_VENTANA_S`; recalibrar en piloto si hay falsos positivos.

### OQ-4 — `tokenTenant`: slug público o token aleatorio

**Decisión:** **token aleatorio opaco** (no el `slug`).

**Por qué:** el segmento `{tokenTenant}` es una capability portadora: da acceso a disponibilidad + reserva pública del consultorio. Un `slug` legible es enumerable (un atacante descubre consultorios probando slugs). Un token de alta entropía por tenant evita la enumeración. `04_modelo_de_datos.md` sólo modela `slug` (para URLs internas); el link público usa un campo separado `token_publico` (se agrega al modelo cuando se haga el wiring real del `TenantPort`). El `TenantPort` ya abstrae la resolución (task 7.2).

### OQ-5 — Horizonte máximo de disponibilidad pública

**Decisión:** **30** días (`PUBLIC_DISPONIBILIDAD_HORIZONTE_D = 30`).

**Por qué:** la KB no lo fija; los 30 días de C-05 son el horizonte de búsqueda de alternativas (`backend/app/turnos/alternativas.py:17`). Reusar 30 evita queries no acotadas y coincide con la expectativa de agenda del consultorio.

### OQ-6 — Lead time mínimo para reservar

**Decisión:** **sin mínimo** (mismo día reservable).

**Por qué:** RN-RE-03 sólo regula cancelar/reprogramar (`05:18`); no hay regla de anticipación para reservar. La spec de C-06 ya declaró "mismo día reservable sin lead time" (OQ-6 resuelta por omisión en la revisión). Formalizado acá.

### OQ-7 — Seña antes de confirmar

**Decisión:** **diferida a C-11.** En C-06 el turno queda `PENDIENTE` sin seña; la preferencia MP y la expiración por pago son alcance de C-11 (`CHANGES.md:30`). No hay decisión que tomar en C-06.

### OQ-8 — Teléfono existente con otro nombre / reserva para terceros

**Decisión:** **se vincula por teléfono sin pisar el nombre** de la ficha existente; **reservar para un tercero queda fuera de v1** (se reserva con el propio nombre + teléfono).

**Por qué:** RN-RE-05 dice "se vincula al paciente existente" sin más (`05:20`). No sobrescribir el nombre evita corromper la historia clínica. El caso "parente reserva para hijo" abre un modelo de titular/responsable que no está en la KB; se deja como extensión post-v1. *Provisional — confirmar con el dueño.*

### OQ-9 — Canal de confirmación inmediata

**Decisión:** **diferida a C-13.** En C-06 la "confirmación inmediata" es la respuesta HTTP (`ReservaOut` con `token_publico`); el envío por WhatsApp (v1, `11_integraciones.md:9`) con fallback email es de C-13. El `NotificadorPort` ya deja el hook listo (evento, no-op en tests).

## Config resuelta (→ `.env.example`)

```ini
PUBLIC_RATE_LIMIT_MAX=10
PUBLIC_RATE_LIMIT_VENTANA_S=900
PUBLIC_VERIFICACION_TTL_MIN=10
PUBLIC_DISPONIBILIDAD_HORIZONTE_D=30
PUBLIC_ANTISPAM_MODO=captcha
RESERVA_TTL_H=48
CANCEL_ANTICIPACION_H=24
```

- `PUBLIC_VERIFICACION_TTL_MIN=10`: TTL de la verificación single-use (10 min es suficiente para completar el formulario, sin dejar ventana de reuso).
- `CANCEL_ANTICIPACION_H=24`: ya venía fijado (default de C-05 y RN-RE-03); se mantiene.
