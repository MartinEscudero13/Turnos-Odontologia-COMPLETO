# Decisiones y Supuestos

## Decisiones documentadas

### DD-01 — Stack: Next.js (TypeScript) + PostgreSQL multi-tenant
**Decisión**: monorepo Next.js TS (UI + API) con PostgreSQL, aislamiento por `tenant_id` + RLS, Prisma, deploy en contenedores.
**Contexto**: Q&A resolvió SaaS multi-tenant + prioridad escalabilidad/mantenibilidad + backend propio (WA/MP/GCal).
**Alternativas consideradas**: (a) app instalable/local-first por consultorio estilo Odontoly; (b) backend schemaless/documental sin constraints transaccionales.
**Justificación**: un solo deploy sirve N consultorios aislados; PG da constraints EXCLUDE (anti-solape real) y transacciones agenda↔caja; TS end-to-end reduce deuda. La (a) rompe reserva 24/7 central y multi-tenant; la (b) deja la regla crítica (solape/caja) en código aplicativo, frágil.
**Trade-offs aceptados**: arranque más lento que un turnero simple; se requiere disciplina DevOps (migraciones, RLS, webhooks) desde el día 1.

### DD-02 — Descartada: local-first instalable (estilo Odontoly)
**Decisión**: NO replicar el modelo PC-local + offline 30 días como base.
**Contexto**: es el moat de Odontoly (soberanía del dato, interior con mala conectividad).
**Alternativas consideradas**: SaaS puro (elegido) vs híbrido con modo degradado.
**Justificación**: choca con SaaS multi-tenant, reserva 24/7 central y lista de espera en tiempo real; costo USD/blue y lock 12 m de Odontoly muestran fricción comercial.
**Trade-offs aceptados**: consultorios con conectividad inestable sufren; mitigación: UI liviana + "modo degradado" (ver agenda del día cacheada) como mejora post-v1, no como arquitectura base.

### DD-03 — Descartada: atajos sin integridad (validación solo en UI / Mongo-style)
**Decisión**: NO aceptar validación de solapes solo en frontend ni modelo sin transacciones.
**Contexto**: el diferencial comprometido es "anti-solapamiento real con test que lo pruebe" (MVP Discovery).
**Alternativas consideradas**: constraints en DB (elegido) vs chequeo aplicativo.
**Justificación**: con doble canal (recepción + link 24/7) las carreras son inevitables; solo EXCLUDE + transacciones las cierran. Prioridad escalabilidad/mantenibilidad prohíbe atajos que duelen después.
**Trade-offs aceptados**: más diseño de migraciones/índices al inicio; tests de concurrencia obligatorios.

### DD-04 — Cobertura OS "configurada", no "validada en vivo" (v1)
**Decisión**: tabla (OS × prestación) por tenant + liquidación presentable; validación realtime SOAP/WS en fase 2.
**Contexto**: moat DentalTec (validación preventiva) vs complejidad real (15+ OS, SOAP por OS).
**Justificación**: el consultorio chico (1–3 sillones) necesita flujo simple en 3 clics, no integración institucional; prometer validación sin WS real sería humo (criterio "comprobado vs afirmación" del Discovery).
**Trade-offs aceptados**: riesgo de débito OS persiste en v1; se mitiga transparentando el alcance y priorizando 1–2 OS piloto en fase 2.

### DD-05 — WhatsApp por API oficial declarada + email fallback
**Decisión**: Cloud API/BSP con plantillas aprobadas; proveedor y número declarados por tenant.
**Contexto**: "tener WhatsApp" es estándar; casi ningún vendor transparenta API vs QR (vacío C3.2).
**Justificación**: trazabilidad (ENTREGADO/LEIDO), plantillas y webhook entrante son requisitos de US-020/US-021; el QR informal no los da.
**Trade-offs aceptados**: costo por conversación y aprobación de plantillas; email fallback cubre caídas.

### DD-06 — Paciente sin login en v1 (nombre + teléfono)
**Decisión**: reserva con nombre + teléfono; vinculación por teléfono existente.
**Contexto**: pregunta abierta del Discovery (login vs datos por turno).
**Justificación**: fricción mínima en móvil (= canal principal); el teléfono ya es la identidad operativa del consultorio. Login/OTP queda como endurecimiento post-v1 si hay abuso.
**Trade-offs aceptados**: riesgo de spam/duplicados; mitigación con rate-limit + captcha liviano + validación por WA.

## Supuestos inferidos

### SU-01 — Varios profesionales/sillones desde el día 1
**Supuesto**: el MVP modela multi-profesional + sillón aunque el primer cliente tenga 1. **Origen**: checklist (agenda multi-profesional/sillón) + Q&A (escala multi-tenant). **Riesgo si es falso**: sobrediseño leve. **Cómo validar**: primer tenant piloto (PO-03 en `10_preguntas_abiertas.md`).

### SU-02 — Pacientes adoptan el link si es más fácil que WhatsApp
**Supuesto**: la reserva online desplaza el mensaje manual si el link llega por el mismo WA. **Origen**: riesgo declarado en Discovery §10 (no validado). **Riesgo si es falso**: todo el diferencial de auto-oferta se usa poco. **Cómo validar**: piloto midiendo % reservas online vs teléfono (métrica en `01`).

### SU-03 — 3–5 OS con tabla configurable alcanzan al segmento 1–3 sillones
**Supuesto**: el consultorio chico tolera "configurada" sin validación realtime. **Origen**: MVP Discovery + DD-04. **Riesgo si es falso**: complejidad OS excede el MVP (riesgo §10). **Cómo validar**: entrevistas a 3 consultorios con sus OS reales antes del Sprint 2.

### SU-04 — Mercado Pago como medio de seña universal
**Supuesto**: MP es aceptado por pacientes y consultorios (estándar verificado en FLAP/DentalSoft/turneros). **Origen**: informe-discovery C1/C2. **Riesgo si es falso**: fricción de pago. **Cómo validar**: piloto con 20 reservas con seña.
