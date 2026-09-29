# Preguntas Abiertas

## Inconsistencias detectadas

### IN-01 — Precios de competidores: todos "a cotizar"
**Documento A dice**: el mercado tolera pedir demo (`informe-discovery.md` C1.6). **Documento B dice**: el MVP exige "precio ARS transparente + factura" como principio transversal (D2). **Impacto**: no hay ancla de precio para posicionarse. **Resolución propuesta**: relevar precios en las demos de los 5 priorizados (DentalSoft, Dentalink, DentalTec, FLAP, Dentidesk) y fijar precio ARS público antes del lanzamiento.

### IN-02 — Alcance de la seña sin cerrar
**Documento A dice**: "seña obligatoria (alcance exacto a definir)" (checklist §5/§7). **Documento B dice**: flujos y US la asumen configurable. **Impacto**: bloquea RN-SE-05 y US-041. **Resolución propuesta**: default "por prestación con `requiere_sena`" editable por tenant; validar en piloto (SU-04).

## Preguntas abiertas (priorizadas)

| Prioridad | Pregunta | Bloquea | Decisor |
|---|---|---|---|
| Alta | PO-01 ¿Seña siempre o por prestación? ¿Monto fijo o %? ¿Anticipación mínima exacta de cancelación? | Sprint 1 (RN-SE-05, US-011/US-041) | Dueño + piloto |
| Alta | PO-02 Precios no publicados de Dentalink, DentalSoft, DentalTec, FLAP, Odontal Web, Livio — relevar en demos | Posicionamiento/precio | Equipo (demos D1) |
| Alta | PO-03 Profundidad técnica: ¿WA Business API oficial o QR? ¿MP Checkout/link/QR? ¿GCal OAuth bidireccional? (todo "No evidenciado" en vendors) | Sprint 1 (US-020, US-041, US-050) | Equipo técnico (guion demo D1 + `11_integraciones.md`) |
| Alta | PO-04 Validación OS realtime: ¿qué OS tienen WS/SOAP real, latencia y manejo de caída? (moat DentalTec por verificar) | Fase 2 OS | Dueño + DentalTec/demo |
| Media | PO-05 ¿Uno o varios profesionales desde el día 1 en el piloto? (SU-01) | Sprint 1 (seed) | Dueño |
| Media | PO-06 ¿Login de paciente o nombre + teléfono? (DD-06 asume sin login; confirmar con tasa de spam) | Sprint 2 | Dueño + datos piloto |
| Media | PO-07 Alcance ARCA: ¿facturación nativa o integración con contador? ¿CUIT por tenant? | Post-v1 | Dueño + contador |
| Media | PO-08 Validación OS con colegios/CORA: ¿aranceles por colegio o por OS directa? | Fase 2 OS | Dueño |
| Baja | PO-09 Stack/presupuesto/plazo: ¿hay restricción del dueño além de lo propuesto en DD-01? | Planificación | Dueño |
| Baja | PO-10 Cumplimiento Ley 27.706/25.326: alcance exacto exigible (firma digital, niveles de acceso, ReNaPDiS) — validar con asesor legal, no con vendors | Lanzamiento | Asesor legal |
| Baja | PO-11 Videos oficiales y centros de ayuda de competidores (limitación §5 del informe) + reseñas verificadas | Refinamiento | Equipo |
