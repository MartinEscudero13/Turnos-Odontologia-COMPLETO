# Decisiones PO-01, PO-03, PO-06, C-10 y C-11 — producto (señas, WhatsApp, paciente, caja y cobro online)

> Fecha: 2026-11-06 (PO-01, PO-03) · 2026-11-12 (PO-06, C-10) · 2026-11-13 (C-11) · Registro de decisiones y preguntas abiertas de `knowledge-base/10_preguntas_abiertas.md`.
> Dueño de producto: Martin Escudero · Registradas por el orquestador a pedido del dueño.
> Clasificación: **Resuelta** (decisión cerrada) · **Provisional** (default del equipo, confirmar con el dueño) · **Diferida** (no se decide todavía) · **Abierta** (documentada, sin decisión).

## Resumen

| PO | Decisión | Clasificación | Impacta |
|---|---|---|---|
| PO-01 | Seña: **default por tenant + override opcional por prestación** | Resuelta (estructura) | C-11, migración 009 |
| PO-03 | WhatsApp: **resuelta** con Twilio (C-13) y Meta Cloud API (C-17); demo con adaptador fake | Resuelta | Producción: número, plantillas y credenciales |
| PO-06 | Acceso/identidad del paciente: **sigue abierta**; C-09 v1 excluye al paciente como actor | Abierta | C-09, C-09-UI, C-11 |
| C-10-OQ-01…10 | Caja y cierre diario: las 10 preguntas abiertas del design quedan **resueltas** (v1) | Resuelta | C-10, C-11, C-12, C-15 |
| C-11-OQ-01…13 | Señas con Mercado Pago: las preguntas que tocan plata quedan **fijadas** (2026-11-13) | Resuelta / Provisional | C-11, C-11-UI, C-15 |

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

**Estado actual (2026-11-17): resuelta.** Se implementaron **Twilio** (C-13) y **Meta Cloud API** (C-17) detrás del mismo puerto `WA_PROVIDER`. La demo corre con `WA_PROVIDER=fake`; producción queda pendiente de número, plantillas y credenciales.

### Consecuencia inmediata

- **C-13 `whatsapp-recordatorios` quedó bloqueado en su momento y se desbloqueó después**: se cerró con Twilio Sandbox (2026-11-16) y C-17 agregó Meta Cloud API (2026-11-17).
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

## PO-06 — Acceso e identidad del paciente — **sigue abierta**

**Estado: abierta (2026-11-12).** Documentada, **no resuelta**: no hay decisión final sobre
si el paciente tendrá acceso propio (portal/login) en una etapa posterior.

### Decisión de alcance para C-09 v1

- En v1 **el paciente no accede al sistema**: sin login, sin JWT de paciente y sin link
  público (DD-06/DD-07).
- La aceptación del presupuesto la registran `RECEPCION` y `ADMIN` **en nombre del
  paciente**, con `canal=CONSULTORIO`; el `ODONTOLOGO` no acepta.
- Consecuencia: C-09 no tiene escenarios con el paciente como actor. El acceso del
  paciente queda como `C09-OQ-10` y no se testea en C-09.
- El desvío respecto de `knowledge-base/03_actores_y_roles.md:22-23` —que hoy le da al
  paciente lectura propia y "aceptar parcial/total"— queda **registrado en el design del
  change**; la KB no se modifica desde acá.

### Qué sigue abierto

- Si v1.1/post-v1 habilita portal o login de paciente, con qué identidad (teléfono + OTP,
  magic link, usuario/contraseña) y qué puede ver y aceptar.
- Relación con el link público de aceptación (token propio estilo C-06) y con C-11.

**No bloquea C-09 v1**: el alcance de arriba es suficiente para implementar y verificar el
change.

---

## C-10 — Caja y cierre diario: resolución de las 10 preguntas abiertas

**Estado: resueltas para v1 (2026-11-12, por el dueño).** Aplican al change
`c-10-caja-cierre-diario`. No modifican la KB: donde la KB no se pronuncia, la decisión
queda acá y el design del change la cita.

| OQ | Pregunta | Decisión v1 | Clasificación |
|---|---|---|---|
| C10-OQ-01 | ¿Se reabre un cierre? | **No.** Si en el futuro hace falta, se emite un **cierre de ajuste** que no borra ni edita el original. Ningún rol reabre en v1. | Resuelta |
| C10-OQ-02 | ¿La diferencia se mide solo contra efectivo? | **Sí.** `diferencia = efectivo_contado − total_efectivo`. Transferencia, MP y OS quedan informativos. | Resuelta |
| C10-OQ-03 | ¿Movimientos retro-fechados? | **Sí**, mientras el día destino no esté cerrado y sin límite de antigüedad. **No** se bloquea la carga porque un día anterior quedó abierto. | Resuelta |
| C10-OQ-04 | ¿Un día sin movimientos se cierra? | **Sí**, cierre en cero. | Resuelta |
| C10-OQ-05 | ¿El paciente puede pagar su copago con medio `OS`? | **No**: `422 MEDIO_OS_RESERVADO`. `OS` es exclusivamente el medio del tramo de cobertura, no un medio de pago del paciente. | Resuelta |
| C10-OQ-06 | ¿La seña de C-11 entra como movimiento `MP`? | **Sí, pero la crea C-11** al aplicar la seña, usando el alta de movimientos de C-10. C-10 no modela señas ni conoce Mercado Pago. | Resuelta |
| C10-OQ-07 | ¿Un cobro pendiente se puede cancelar sin movimiento? | **No en v1.** Queda visible como impago; no se borra ni se anula sin el movimiento correspondiente. | Resuelta |
| C10-OQ-08 | ¿Timezone configurable por tenant? | **No en v1**: offset fijo `-03:00`. Configurable por tenant queda para post-v1. | Provisional |
| C10-OQ-09 | ¿Recepción puede anular movimientos? | **No: solo `ADMIN`.** Lectura literal de la matriz de `03_actores_y_roles.md`; si el piloto pide otra cosa, se amplía el rol sin cambiar el modelo. | Provisional |
| C10-OQ-10 | ¿El tramo OS del cierre es cuenta por cobrar o informativo? | **Informativo.** El cobro real a la obra social es C-12 (liquidaciones); C-10 no lleva cuenta corriente de OS. | Resuelta |

### Consecuencias

- **C-10** implementa el adaptador real del puerto `imputar_caja` que dejó C-09, con
  `medio` opcional: `NULL` no rompe la aceptación, cae en `cobros_pendientes`.
- **C-11** no necesita cambios de contrato: crea el movimiento `MP` al aplicar la seña.
- **C-12** es dueño de la cuenta corriente de obras sociales; C-10 solo informa el tramo.
- **C-15** es dueño de los reportes de ocupación, ausentismo y facturación por profesional
  (el `CHANGES.md` los ubica ahí, no en C-10).

---

## C-11 — Señas con Mercado Pago: decisiones del dueño (2026-11-13)

**Estado: fijadas las que tocan plata; una provisional y una diferida fuera de v1.** Aplican al
change `c-11-senas-mercadopago` y no modifican la KB: donde la KB no se pronuncia, la decisión queda
acá y el design del change la cita como `C11-OQ-N`.

| OQ | Pregunta | Decisión v1 | Clasificación |
|---|---|---|---|
| C11-OQ-01 | ¿Cómo se redondea el porcentaje de la seña? | **Truncar hacia abajo al centavo** (`precio_base * pct // 100`); nunca redondear para arriba. | Fijada 2026-11-13 |
| C11-OQ-02 | Anticipación mínima de cancelación para devolver la seña | **24 h**, tomadas de `CANCEL_ANTICIPACION_H`, con snapshot en la seña. Se revisa con el piloto. | **Provisional** |
| C11-OQ-03 | ¿Qué pasa con la seña acreditada si cancelan por debajo del umbral? | La seña queda **`ACREDITADA`** y **decide un humano `ADMIN`**: `DEVUELTA` con motivo o `APLICADA` como cancelación tardía (`concepto=CANCELACION_TARDIA`). Sin automatismo. | Fijada 2026-11-13 |
| C11-OQ-04 | Al reprogramar, ¿la seña se transfiere o se pide una nueva? | **Se transfiere** al turno nuevo con `expira_at` recalculado (`min(ahora + TTL, nuevo.inicio)`). **Mismo token si no venció**; si venció o se liberó, se reemite uno nuevo. | Fijada 2026-11-13 |
| C11-OQ-09 | ¿La devolución se ejecuta por API de MP o a mano? | **Manual**: sin API de reembolsos. El sistema registra la obligación y el reintegro se ejecuta en el panel de Mercado Pago. | Fijada 2026-11-13 |
| C11-OQ-10 | ¿La seña visible en agenda cambia el payload de turnos o usa endpoint propio? | **Endpoint propio** `GET /api/senas?desde=&hasta=`, filtrando por **`turno.inicio`**. `GET /api/turnos` no cambia. | Fijada 2026-11-13 |
| C11-OQ-13 | ¿Se descuenta la seña contra un presupuesto aceptado (C-09)? | **Fuera de v1.** Mientras no exista el descuento automático, aplicar una seña con presupuesto aceptado vigente responde **`409 PRESUPUESTO_CON_SENA`**. | Diferida fuera de v1 (abierta, no bloqueante) |

### Consecuencias

- El reembolso es **manual** y **requiere un responsable operativo asignado**: sin una persona que
  opere el panel de MP y ejecute los reintegros, `DEVUELTA`, `MONTO_DISTINTO` y `PAGO_EXCEDENTE` son
  obligaciones sin dueño. Es condición de avance del governance CRÍTICO de C-11.
- La anticipación de **24 h** y el **backoff** del reintento de preferencia
  (`min(2**intentos, 15)` minutos, `C11-OQ-05`) son **provisionales**: son defaults del equipo y se
  confirman con el piloto, no son un número cerrado del producto.
- Las preguntas **no bloqueantes** que siguen abiertas son `C11-OQ-05`, `06`, `07`, `08`, `11`, `12`
  y `13`; ninguna impide implementar v1.
- `C11-OQ-12` (sólo `ARS`, sin tope de porcentaje) sigue abierta y **no** tiene relación con el
  descuento contra presupuesto: ese es `C11-OQ-13`.

---

## Referencias

- `knowledge-base/10_preguntas_abiertas.md` — PO-01, PO-03 y PO-06 (PO-06 sigue
  abierta; DD-06 asume paciente sin login).
- `knowledge-base/11_integraciones.md` §WhatsApp — alcance v1 y guion de demo.
- `CHANGES.md` — C-10 (caja), C-11 (señas) y C-13 (WhatsApp).
- `openspec/changes/archive/2026-11-13-c-10-caja-cierre-diario/design.md` — estas 10 decisiones se citan
  como `C10-OQ-N` en el diseño y en los escenarios.
- `openspec/changes/archive/2026-11-13-c-11-senas-mercadopago/design.md` §Open Questions — las OQ de C-11 se citan
  como `C11-OQ-N` en el diseño, las delta specs y las tareas.
