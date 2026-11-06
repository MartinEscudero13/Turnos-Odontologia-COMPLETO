# Decisiones PO-01 y PO-03 — producto (señas y WhatsApp)

> Fecha: 2026-11-06 · Resolución de dos preguntas abiertas de `knowledge-base/10_preguntas_abiertas.md`.
> Dueño de producto: Martin Escudero · Registradas por el orquestador a pedido del dueño.
> Clasificación: **Resuelta** (decisión cerrada) · **Provisional** (default del equipo, confirmar con el dueño) · **Diferida** (no se decide todavía).

## Resumen

| PO | Decisión | Clasificación | Impacta |
|---|---|---|---|
| PO-01 | Seña: **default por tenant + override opcional por prestación** | Resuelta (estructura) | C-11, migración 009 |
| PO-03 | WhatsApp: **diferida**, sin proveedor/BSP definido | Diferida | C-13 (bloqueado para implementar) |

---

## PO-01 — ¿Seña por tenant o por prestación?

**Decisión: modelo híbrido.** El consultorio define una regla por defecto y puede sobreescribirla en prestaciones puntuales.

```
valor efectivo = prestacion.<campo> ?? tenant_parametros.<campo>
```

### Por qué

El ausentismo no cuesta lo mismo en todos los turnos: una limpieza de 20 minutos perdida es barata; un implante de 3 horas con material preparado es caro. Un único valor global obliga a elegir entre dos males: pedir seña en todo (y espantar reservas de prestaciones baratas) o no pedir en nada (y comerse los faltazos caros). El override por prestación resuelve el caso real sin obligar a configurar 40 servicios.

### Forma en el modelo de datos (para C-11)

| Tabla | Campo | Tipo | Semántica |
|---|---|---|---|
| `tenant_parametros` | `sena_modo` | `TEXT` (`SIN_SENA` \| `PORCENTAJE` \| `MONTO_FIJO`) | Regla default del consultorio |
| `tenant_parametros` | `sena_valor` | `NUMERIC` (nulo si `SIN_SENA`) | `%` si `PORCENTAJE`, centavos si `MONTO_FIJO` |
| `prestaciones` | `sena_modo` | mismo enum, **nullable** | `NULL` = hereda del tenant |
| `prestaciones` | `sena_valor` | `NUMERIC`, **nullable** | `NULL` = hereda del tenant |

Reglas de resolución:

1. `prestaciones.sena_modo IS NOT NULL` → gana la prestación (aunque sea `SIN_SENA`, que es un override válido).
2. Si es `NULL` → gana `tenant_parametros`.
3. Si el tenant tampoco definió nada → `SIN_SENA` (fail-open a no cobrar, nunca a cobrar de más).

### Sub-decisiones que quedan abiertas (no bloquean C-09)

| Pregunta | Recomendación del equipo | Estado |
|---|---|---|
| ¿Monto fijo o porcentaje? | Soportar **ambos** en el enum; default del piloto = **porcentaje con tope opcional** | Provisional |
| Anticipación mínima de cancelación (RN-SE-05) | **24 h** (ya es `CANCEL_ANTICIPACION_H=24` y el default de C-05) | Provisional |

### Impacto

- **C-11 `senas-mercadopago`**: es el change que materializa esto. No requiere cambios en C-09.
- **Migración 009**: agrega las columnas a `tenant_parametros` y `prestaciones` (ya existen como tablas).
- **UI**: `/config` del tenant expone la regla default; el catálogo de prestaciones permite el override por servicio.

---

## PO-03 — ¿WhatsApp Business API oficial o QR? ¿Qué proveedor?

**Decisión: diferida.** El dueño decidió (2026-11-06) **no definir proveedor todavía**. No se elige BSP ni número en esta etapa.

### Consecuencia inmediata

- **C-13 `whatsapp-recordatorios` queda bloqueado para implementación**: sin proveedor no hay `WA_API_TOKEN`, ni plantillas aprobadas, ni webhook que probar.
- Lo ya construido no depende de esto:
  - C-06 usa **captcha** como verificación y la confirmación es la respuesta HTTP + token (OQ-2/OQ-9).
  - C-07 dispara la auto-oferta con un `NotificadorPort` no-op en tests.
- **C-11 no se ve afectado**: Mercado Pago es independiente del canal de mensajería.

### Opciones documentadas (para cuando se retome)

| Camino | Qué implica | Cuándo conviene |
|---|---|---|
| **BSP** (Twilio, 360dialog, Gupshup, Infobip) | Panel, sandbox y onboarding gestionado; costo por conversación con markup | Piloto, PyME, arrancar rápido |
| **Meta directo** (Cloud API) | Cuenta de Meta Business propia, número verificado, plantillas aprobadas; más barato por mensaje | Volumen alto, equipo con tiempo de gestión |
| **WhatsApp Web / QR** (Baileys y similares) | Gratis, pero **viola los términos de Meta**: riesgo de ban del número, sin plantillas ni estados | **Descartado** para v1 con pacientes reales |

### Criterio de desbloqueo de C-13

1. Elegir camino (BSP o Meta directo) y proveedor concreto.
2. Definir número (de prueba para demo, real para piloto) y quién paga las conversaciones.
3. Recién entonces: `openspec propose c-13-whatsapp-recordatorios`.

---

## Referencias

- `knowledge-base/10_preguntas_abiertas.md` — PO-01 y PO-03 (prioridad Alta).
- `knowledge-base/11_integraciones.md` §WhatsApp — alcance v1 y guion de demo.
- `CHANGES.md` — C-11 (señas) y C-13 (WhatsApp).
