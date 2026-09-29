# Reglas de Negocio

Cada regla tiene código único `RN-{DOMINIO}-{NN}` para trazabilidad con `06_funcionalidades.md` y `07_flujos_principales.md`.

## Dominio: Agenda (RN-AG)

- **RN-AG-01**: La duración de un turno deriva de `prestaciones.duracion_min` (variable por prestación); el fin se calcula, no se ingresa — evita turnos mal medidos (estándar DentalSoft/FLAP).
- **RN-AG-02**: Un profesional no puede tener dos turnos superpuestos, ni un sillón/box puede estar doble-asignado; el control vive en DB (constraint EXCLUDE), no solo en UI.
- **RN-AG-03**: El sobreturno es una acción explícita (botón propio + motivo obligatorio) y auditada; nunca un solapamiento accidental — anti-patrón "doble reserva por WhatsApp".
- **RN-AG-04**: Los bloqueos (feriados, vacaciones, almuerzo, ausencias) restan disponibilidad; sin hueco real no hay slot ofrecido.
- **RN-AG-05**: Todo turno existe dentro de un `tenant_id`; la agenda nunca mezcla consultorios.
- **RN-AG-06**: Los horarios del profesional se intersectan con los del consultorio: fuera de ambos no hay disponibilidad.

## Dominio: Reserva online (RN-RE)

- **RN-RE-01**: El link público muestra solo slots reales (disponibilidad calculada servidor-side por profesional + prestación + sillón).
- **RN-RE-02**: El paciente puede confirmar, cancelar y reprogramar sin llamar; cada acción genera token/sms de verificación liviana anti-spam.
- **RN-RE-03**: Cancelar o reprogramar exige la anticipación mínima configurable del tenant (default 24 h); debajo del umbral, solo por recepción y queda auditado.
- **RN-RE-04**: Todo hueco liberado por cancelación se ofrece automáticamente a la lista de espera (orden: prioridad/fecha de alta) antes de quedar libre general.
- **RN-RE-05**: En v1 basta nombre + teléfono por turno (sin login de paciente obligatorio); si el teléfono ya existe, se vincula al paciente existente (patrón DNI-reconoce de DentalSoft).

## Dominio: Señas y Mercado Pago (RN-SE)

- **RN-SE-01**: La reserva puede exigir seña (siempre o por prestación según config del tenant); sin seña acreditada antes de `expira_at`, el turno se libera automáticamente.
- **RN-SE-02**: La seña está atada 1──1 a la reserva y es visible en agenda (estado: PENDIENTE/ACREDITADA/APLICADA/DEVUELTA/LIBERADA).
- **RN-SE-03**: Los webhooks de Mercado Pago son idempotentes (`mp_payment_id` único); un pago duplicado nunca duplica la seña ni el turno.
- **RN-SE-04**: La seña acreditada se aplica al cobro del tratamiento o se devuelve según la política de cancelación visible al reservar (transparencia estilo Fresha/FLAP).
- **RN-SE-05**: Monto y alcance exactos de la seña los define cada tenant (ver `10_preguntas_abiertas.md` PO-01).

## Dominio: Clínica y odontograma (RN-CL)

- **RN-CL-01**: Odontograma en notación FDI (piezas 11–48, superficies/eventos) con historial por pieza; cada hallazgo puede derivar en línea de presupuesto.
- **RN-CL-02**: El presupuesto admite aceptación parcial por línea; solo lo aceptado imputa a agenda/caja — el odontograma nunca es "un dibujo suelto".
- **RN-CL-03**: Toda evolución queda fechada, firmada por profesional y no se edita: se corrige con nueva evolución (trazabilidad Ley 27.706).
- **RN-CL-04**: Adjuntos (Rx/fotos) pertenecen a la ficha del paciente del tenant; nada de PHI sale a logs ni a mensajes.

## Dominio: Obras sociales (RN-OS)

- **RN-OS-01**: Cobertura **configurable** por (OS × prestación): porcentaje/monto a cargo OS vs paciente; en v1 es tabla del tenant, NO validación en vivo (honestidad modelo Dentatools: declarar "configurada" vs "validada").
- **RN-OS-02**: La liquidación agrupa turnos atendidos con OS por período y genera un presentable (detalle por práctica/paciente/monto).
- **RN-OS-03**: Empieza con 3–5 OS por tenant; validación realtime vía WS/SOAP es fase 2 (moat DentalTec, fuera del MVP).

## Dominio: Caja (RN-CJ)

- **RN-CJ-01**: Caja multi-medio (efectivo/transferencia/MP/OS); todo movimiento registra usuario, fecha y turno asociado si aplica.
- **RN-CJ-02**: Cierre diario obligatorio por tenant con totales por medio; la diferencia debe ser 0 para cerrar (o registrar motivo).
- **RN-CJ-03**: Las anulaciones son trazables (motivo obligatorio, nunca borrado físico).

## Dominio: Autenticación, auditoría y datos (RN-AU)

- **RN-AU-01**: RBAC por `(tenant_id, rol)`: Paciente / Odontólogo / Recepción / Admin (ver `03_actores_y_roles.md`).
- **RN-AU-02**: Auditoría append-only de agenda, caja, señas, presupuestos y accesos (quién/qué/cuándo/antes/después).
- **RN-AU-03**: Consentimiento informado firmado (móvil, con timestamp) requerido antes de registrar clínica (Ley 26.529).
- **RN-AU-04**: Exportación de datos del tenant en 1 clic (CSV/Excel + JSON) y respaldo diario declarado; sin lock-in (vacío de mercado C3.7).
- **RN-AU-05**: 2FA exigible para roles internos; sesiones con expiración; secretos solo en variables de entorno.

## Dominio: Integraciones (RN-IN)

- **RN-IN-01**: WhatsApp por API oficial con plantillas aprobadas; proveedor y número declarados por tenant; email como fallback (nunca SMS fantasma).
- **RN-IN-02**: Google Calendar sincroniza bidireccional por profesional (OAuth propio); el sistema es fuente de verdad ante conflicto (gana el turno interno, se re-oferta el hueco).
- **RN-IN-03**: Toda integración externa degrada con gracia: si WA/MP/GCal caen, la agenda y la caja siguen operando y los eventos se reintentan con backoff.

## Excepciones globales

- **RN-GL-01**: Ninguna regla de conveniencia (UX, marketing, IA) puede violar RN-AG-02 (anti-solapamiento) ni RN-AU-02 (auditoría).
- **RN-GL-02**: Ante conflicto entre disponibilidad mostrada y real, vale la real al momento de confirmar (último en confirmar pierde, con oferta alternativa inmediata).
- **RN-GL-03**: Todo dato personal de ejemplo en docs/demos es FICTICIO (DNI/nombres inventados).
