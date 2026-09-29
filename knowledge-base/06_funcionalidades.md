# Funcionalidades

Organizadas por **épica** y luego por **historia de usuario** (US-NNN). Trazan a `05_reglas_de_negocio.md`.

## Épica 1: Agenda del consultorio

### US-001 — Agenda día/semana multi-profesional y por sillón
**Como** recepcionista **Quiero** ver la agenda día/semana por profesional y sillón **Para** saber quién viene, a qué hora y a qué.
**Criterios de aceptación**: - [ ] CA-1 Vista día/semana con colores por estado (RN-AG-05). - [ ] CA-2 Drag&drop con confirmación revalida solape en servidor. - [ ] CA-3 Bloqueos/feriados ocultan slots (RN-AG-04).
**Reglas relacionadas**: RN-AG-01, RN-AG-02, RN-AG-04, RN-AG-05, RN-AG-06.

### US-002 — Anti-solapamiento con sobreturno explícito
**Como** sistema **Quiero** rechazar todo solape profesional/sillón salvo sobreturno explícito auditado **Para** eliminar dobles reservas.
**Criterios de aceptación**: - [ ] CA-1 Constraint EXCLUDE en DB + test que intenta solapar y falla (RN-AG-02). - [ ] CA-2 Sobreturno exige motivo y deja rastro en auditoría (RN-AG-03).
**Reglas relacionadas**: RN-AG-02, RN-AG-03, RN-AU-02, RN-GL-01.

### US-003 — Catálogos (prestaciones, sillones, horarios, bloqueos)
**Como** admin **Quiero** configurar prestaciones (duración/precio/seña), sillones y horarios **Para** que la agenda refleje la realidad del consultorio.
**Criterios de aceptación**: - [ ] CA-1 Duración variable por prestación (RN-AG-01). - [ ] CA-2 Intersección horario profesional × consultorio (RN-AG-06).
**Reglas relacionadas**: RN-AG-01, RN-AG-06, RN-SE-05.

## Épica 2: Reserva online 24/7

### US-010 — Reserva por link sin llamar
**Como** paciente **Quiero** ver huecos reales y reservar (prestación → profesional → hora) **Para** no llamar ni mandar WhatsApp.
**Criterios de aceptación**: - [ ] CA-1 Slots calculados servidor-side (RN-RE-01). - [ ] CA-2 Identificación liviana nombre + teléfono; teléfono existente vincula ficha (RN-RE-05). - [ ] CA-3 Confirmación inmediata por WA/email.
**Reglas relacionadas**: RN-RE-01, RN-RE-02, RN-RE-05.

### US-011 — Cancelar / reprogramar con anticipación
**Como** paciente **Quiero** cancelar o reprogramar con anticipación **Para** liberar el horario a tiempo.
**Criterios de aceptación**: - [ ] CA-1 Respeta anticipación mínima configurable (RN-RE-03, default 24 h). - [ ] CA-2 Debajo del umbral deriva a recepción auditada.
**Reglas relacionadas**: RN-RE-03.

### US-012 — Lista de espera con auto-oferta
**Como** paciente en espera **Quiero** que me ofrezcan automáticamente huecos liberados **Para** adelantar mi atención.
**Criterios de aceptación**: - [ ] CA-1 Hueco liberado se ofrece a lista antes de publicarse (RN-RE-04). - [ ] CA-2 Oferta con expiración; si vence pasa al siguiente.
**Reglas relacionadas**: RN-RE-04.

## Épica 3: WhatsApp y recordatorios

### US-020 — Recordatorios automáticos
**Como** consultorio **Quiero** recordatorios WA configurables (anticipación/horario/mensaje) **Para** bajar el ausentismo.
**Criterios de aceptación**: - [ ] CA-1 Plantillas aprobadas, proveedor declarado (RN-IN-01). - [ ] CA-2 Estados ENVIADO/ENTREGADO/LEIDO/FALLIDO visibles por turno. - [ ] CA-3 Email fallback si WA falla.
**Reglas relacionadas**: RN-IN-01, RN-IN-03.

### US-021 — Confirmación por WhatsApp
**Como** paciente **Quiero** confirmar/cancelar respondiendo el mensaje **Para** no entrar al link.
**Criterios de aceptación**: - [ ] CA-1 Webhook entrante actualiza estado del turno y reprograma recordatorios. - [ ] CA-2 Cancelación por WA dispara auto-oferta a lista (RN-RE-04).
**Reglas relacionadas**: RN-RE-02, RN-RE-04, RN-IN-03.

## Épica 4: Clínica (ficha + odontograma → presupuesto)

### US-030 — Ficha clínica mínima
**Como** odontólogo **Quiero** antecedentes/alergias/evolución fechada + adjuntos Rx/fotos **Para** atender con la historia a mano.
**Criterios de aceptación**: - [ ] CA-1 Consentimiento firmado previo (RN-AU-03, RN-CL-04). - [ ] CA-2 Evoluciones inmutables, solo apéndice (RN-CL-03).
**Reglas relacionadas**: RN-CL-03, RN-CL-04, RN-AU-03.

### US-031 — Odontograma FDI con historial
**Como** odontólogo **Quiero** registrar hallazgos por pieza/superficie (FDI) con historial **Para** planificar tratamiento.
**Criterios de aceptación**: - [ ] CA-1 Notación FDI 11–48 + historial por pieza (RN-CL-01). - [ ] CA-2 Hallazgo convertible en línea de presupuesto en 1 clic.
**Reglas relacionadas**: RN-CL-01, RN-CL-02.

### US-032 — Presupuesto con aceptación parcial
**Como** odontólogo/recepción **Quiero** presupuesto por pieza con cobertura OS y aceptación parcial **Para** cerrar planes que el paciente sí puede pagar.
**Criterios de aceptación**: - [ ] CA-1 Líneas con monto + cobertura OS + a-cargo-paciente (RN-OS-01, RN-CL-02). - [ ] CA-2 Lo aceptado imputa a agenda/caja; lo pendiente queda en recupero (recall comercial).
**Reglas relacionadas**: RN-CL-02, RN-OS-01.

## Épica 5: Caja, señas y obras sociales

### US-040 — Caja multi-medio + cierre diario
**Como** recepción **Quiero** registrar cobros multi-medio y cerrar caja diaria **Para** que ningún peso quede sin trazabilidad.
**Criterios de aceptación**: - [ ] CA-1 Medios: efectivo/transferencia/MP/OS (RN-CJ-01). - [ ] CA-2 Cierre cuadra en 0 o registra motivo (RN-CJ-02). - [ ] CA-3 Anulación con motivo, nunca borrado (RN-CJ-03).
**Reglas relacionadas**: RN-CJ-01, RN-CJ-02, RN-CJ-03.

### US-041 — Seña Mercado Pago con liberación automática
**Como** consultorio **Quiero** exigir seña online atada a la reserva **Para** reducir sillón vacío por no-show.
**Criterios de aceptación**: - [ ] CA-1 Pago por link MP; webhook idempotente (RN-SE-03). - [ ] CA-2 Sin acreditación antes de expirar → turno liberado + auto-oferta (RN-SE-01, RN-RE-04). - [ ] CA-3 Política de cancelación visible al reservar (RN-SE-04).
**Reglas relacionadas**: RN-SE-01, RN-SE-02, RN-SE-03, RN-SE-04, RN-SE-05.

### US-042 — Cobertura OS configurable + liquidación
**Como** recepción/admin **Quiero** cobertura por (OS × prestación) y liquidación presentable **Para** facturar OS sin fricción en 1–3 sillones.
**Criterios de aceptación**: - [ ] CA-1 Tabla configurable, etiquetada "configurada, no validada en vivo" (RN-OS-01). - [ ] CA-2 Liquidación por período exportable (RN-OS-02). - [ ] CA-3 Arranque con 3–5 OS (RN-OS-03).
**Reglas relacionadas**: RN-OS-01, RN-OS-02, RN-OS-03.

## Épica 6: Calendario y plataforma

### US-050 — Google Calendar bidireccional
**Como** odontólogo **Quiero** mi agenda sincronizada con Google Calendar **Para** ver mis turnos donde ya miro mi día.
**Criterios de aceptación**: - [ ] CA-1 OAuth por profesional; alta/baja/modificación en ambos sentidos. - [ ] CA-2 Ante conflicto gana el sistema y se re-oferta (RN-IN-02).
**Reglas relacionadas**: RN-IN-02, RN-IN-03.

### US-051 — RBAC, auditoría, exportación y respaldo
**Como** admin **Quiero** roles, auditoría, exportación 1-clic y respaldo declarado **Para** cumplir la base legal mínima.
**Criterios de aceptación**: - [ ] CA-1 Matriz `03_actores_y_roles.md` enforced en API (RN-AU-01). - [ ] CA-2 Log append-only consultable (RN-AU-02). - [ ] CA-3 Export CSV/Excel+JSON en 1 clic (RN-AU-04).
**Reglas relacionadas**: RN-AU-01, RN-AU-02, RN-AU-04, RN-AU-05.

### US-052 — Recall sanitario separado
**Como** odontólogo **Quiero** recall de controles (limpieza 6 m, post-tratamiento) separado de marketing **Para** adherencia clínica con confianza.
**Criterios de aceptación**: - [ ] CA-1 Recall con motivo clínico y fecha objetivo; canal WA. - [ ] CA-2 No mezcla con campañas (fuera de alcance v1).
**Reglas relacionadas**: RN-IN-01.
