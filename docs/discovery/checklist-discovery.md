# Discovery — Turnos-Odontologia

**Fecha**: 2026-09-29
**Fuentes investigadas**: investigación de mercado propia, 18 sistemas + 3 turneros AR (ver `discovery/competidores.md`)

## 1. Problema que resuelve

Los consultorios odontológicos chicos-medianos coordinan turnos por WhatsApp y
teléfono, lo que genera dobles reservas, tiempo perdido en confirmaciones
manuales y huecos improductivos. A eso se suma el ausentismo: pacientes que se
olvidan o cancelan a último momento sin que el consultorio pueda reasignar el
hueco a tiempo.

## 2. Usuarios / roles

- **Paciente**: reserva, cancela y reprograma turnos online sin llamar ni escribir.
- **Odontólogo**: ve su agenda del día y atiende con la ficha clínica a mano.
- **Recepcionista/Admin**: gestiona la agenda completa, la caja, las señas y las
  obras sociales.

## 3. Casos de uso

1. Como paciente, quiero ver los horarios libres y reservar online 24/7 para no
   tener que llamar ni mandar WhatsApp.
2. Como profesional/recepción, quiero ver la agenda del día (multi-profesional
   y por sillón) para saber quién viene, a qué hora y a qué.
3. Como paciente, quiero cancelar o reprogramar con anticipación para liberar
   el horario; como consultorio, quiero que la lista de espera auto-ofrezca
   esos huecos.
4. Como consultorio, quiero recordatorios automáticos por WhatsApp para bajar
   el ausentismo.

## 4. Competidores / soluciones existentes

Relevamiento completo en `discovery/competidores.md`: 18 sistemas comparados
(ordenados por relevancia para Argentina) + 3 turneros argentinos
complementarios, con matriz de puntuación ponderada y análisis de vacíos.

| Competidor | Relevancia | Nota |
|---|---|---|
| DentalSoft (AR) | Alta | Mejor encaje operativo argentino, vara de UX local |
| Dentalink | Alta | Techo funcional regional |
| DentalTec (AR) | Alta | Moat en obras sociales + ARCA |
| FLAP (AR) | Alta | Seña + autoasignación + odontograma FDI |
| Dentidesk (CL) | Media-alta | Vara clínica multi-especialidad |

**Notas**: los 5 de arriba son los priorizados para demo. Referencias de UX:
Fresha, AgendaPro y DentalSoft. Vacíos detectados: precios no publicados,
integración WhatsApp raramente documentada como API oficial, liquidación de
obras sociales débil fuera de DentalTec, exportación de datos poco clara.

## 5. Funcionalidades necesarias

- Agenda multi-profesional y por sillón, con duraciones por prestación,
  bloqueos y anti-solapamiento real (sobreturnos como excepción explícita).
- Reserva online 24/7 por link: confirma, cancela y reprograma sin llamar.
- Recordatorios por WhatsApp con estados (proveedor declarado).
- Ficha clínica + odontograma FDI con historial, que deriva en presupuesto por
  pieza con aceptación parcial, conectado a agenda y caja.
- Caja multi-medio + señas por Mercado Pago con liberación automática + cierre
  diario + reportes base.
- Cobertura de obras sociales configurable + liquidación simple.
- Lista de espera que auto-ofrece huecos liberados.
- Sincronización bidireccional con Google Calendar.
- Base legal mínima: roles y permisos, auditoría, consentimiento firmado,
  exportación en 1 clic, respaldo declarado (Leyes 25.326, 26.529 y 27.706).
- Reglas: anticipación mínima de cancelación, sin solapamientos,
  seña obligatoria (alcance exacto a definir, ver preguntas abiertas).

## 6. Funcionalidades opcionales

- Facturación electrónica nativa ARCA.
- Validación de cobertura de obra social en tiempo real.
- Periodontograma, ortodoncia, integración PACS/imágenes.
- IA diagnóstica, app móvil nativa, marketplace.
- Campañas y recuperación de pacientes.

## 7. Reglas de negocio

- No se puede cancelar un turno con menos de la anticipación mínima
  configurada (valor exacto a definir).
- Un profesional/sillón no puede tener dos turnos superpuestos; el
  sobreturno es una acción explícita y auditada, no un accidente.
- La reserva puede exigir seña por Mercado Pago (siempre o por prestación,
  a definir); si la seña no se acredita, el turno se libera automáticamente.

## 8. Integraciones

- WhatsApp (recordatorios y confirmación) — v1.
- Mercado Pago (señas online) — v1.
- Google Calendar (sincronización bidireccional) — v1.
- A explorar post-v1: AFIP/ARCA, validación de obras sociales, radiología,
  firma digital.

## 9. Restricciones

- El canal principal del paciente es el celular: tiene que andar perfecto en
  móvil.
- Stack obligatorio y presupuesto/plazo pendientes de definición por el dueño
  (ver preguntas abiertas).

## 10. Riesgos

- **Supuesto sin probar**: que los pacientes adopten la reserva online en vez
  de seguir mandando WhatsApp por costumbre — no validado con usuarios reales.
- **Riesgo operativo**: si el consultorio no mantiene actualizada la
  disponibilidad, el sistema muestra huecos que en realidad no están libres.
- **Riesgo de dominio**: la complejidad de las obras sociales argentinas
  (coberturas, validaciones, liquidaciones) puede exceder la "cobertura
  configurable + liquidación simple" del MVP.

## 11. Preguntas abiertas

- ¿Anticipación mínima exacta de cancelación? ¿Seña siempre o por prestación?
- ¿Stack obligatorio y presupuesto/plazo concretos?
- ¿Un odontólogo o varios profesionales desde el día 1?
- ¿Login para el paciente o alcanza con nombre + teléfono por turno?
- Precios de competidores clave no publicados (Dentalink, DentalSoft,
  DentalTec, FLAP, Odontal Web, Livio) — relevar en las demos.
- Profundidad de seguridad/integraciones técnicas (WA-API vs QR, MP Checkout,
  ARCA WS) — guion de demo pendiente.
