# Flujos Principales

Cada flujo extremo a extremo, con actores, pasos y errores. Reglas en `05_reglas_de_negocio.md`.

## Flujo 1: Reserva online con seña
**Disparador**: paciente abre `/r/:tokenTenant` (ruta pública de la SPA). **Actor**: Paciente.
**Pasos**:
1. Frontend pide `GET /api/disponibilidad?prestacion=&desde=` → API calcula slots (profesional × sillón × duración, menos bloqueos) del tenant.
2. Paciente elige slot → ingresa nombre + teléfono → `POST /api/reservas/publicas` crea turno PENDIENTE + token.
3. Si la prestación exige seña: API crea seña PENDIENTE + preferencia MP → paciente paga en `/pagar/:token`.
4. Webhook MP (`mp_payment_id` idempotente) → seña ACREDITADA → turno CONFIRMADO → WA de confirmación.
5. Si expira sin pago: turno liberado → auto-oferta a lista de espera → slot público.
**Casos de error**: slot tomado entre pasos → 409 + 3 alternativas (RN-GL-02); webhook duplicado → 200 sin efecto (RN-SE-03); MP caído → reserva PENDIENTE + reintento/backoff (RN-IN-03).

## Flujo 2: Recordatorio y confirmación por WhatsApp
**Disparador**: cron de recordatorios (ej. 24 h antes). **Actor**: Sistema + Paciente.
**Pasos**:
1. Scheduler lee turnos CONFIRMADOS/PENDIENTES del tenant → envía plantilla WA (API oficial) → guarda `mensajes_wa` ENVIADO.
2. Webhook WA actualiza ENTREGADO/LEIDO visibles en agenda.
3. Paciente responde "SI"/"NO": webhook → CONFIRMADO o CANCELADO; si cancela con anticipación → Flujo 4.
**Casos de error**: WA caído → email fallback + reintento (RN-IN-03); respuesta ambigua → link de confirmación.

## Flujo 3: Odontograma → presupuesto → agenda/caja
**Disparador**: odontólogo abre ficha en consulta. **Actor**: Odontólogo (+ Recepción).
**Pasos**:
1. Verifica consentimiento firmado (si falta, paciente firma en móvil) → abre odontograma FDI.
2. Registra hallazgos por pieza → "derivar a presupuesto" crea líneas (pieza + prestación + monto).
3. Sistema aplica cobertura OS del paciente → muestra total, a-cargo-OS, a-cargo-paciente.
4. Paciente acepta parcial/total (en consultorio o por link) → lo aceptado genera turnos (Flujo 1 interno) e imputación a caja.
5. Evolución firmada cierra la visita; lo no aceptado va a recupero/recall.
```
Odontólogo → Frontend → API → DB (hallazgo + presupuesto, transacción)
Paciente → acepta → API → turnos + caja (imputación)
```
**Casos de error**: sin consentimiento → bloquea clínica, permite solo agenda (RN-AU-03); OS sin cobertura cargada → 100% particular visible.

## Flujo 4: Cancelación + lista de espera con auto-oferta
**Disparador**: cancelación (paciente, WA o recepción). **Actor**: Paciente/Sistema.
**Pasos**:
1. API valida anticipación mínima (default 24 h); si OK → turno CANCELADO + aplica política de seña (devolver/aplicar según lo visible al reservar).
2. Sistema busca lista de espera compatible (prestación/profesional/ventana) ordenada → envía oferta WA con expiración (ej. 2 h).
3. Primer aceptante ocupa el hueco (revalida solape); si nadie acepta → slot público general.
**Casos de error**: cancelación tardía → solo recepción + auditoría; seña en disputa → estado explícito, nunca limbo.

## Flujo 5: Cierre de caja diario
**Disparador**: fin del día, recepción/admin. **Actor**: Recepción/Admin.
**Pasos**:
1. `GET /api/caja/movimientos?fecha=` muestra ingresos/egresos por medio (efectivo/transf./MP/OS) + señas aplicadas.
2. Responsable cuenta efectivo → carga real → sistema compara: diferencia 0 → `POST /api/caja/cierre`; si no, registra motivo y permite cerrar con observación (auditable).
3. Reportes base: ocupación, ausentismo, facturación por profesional (KPIs vara DentalSoft).
**Casos de error**: día con movimientos sin responsable → no cierra; anulación post-cierre → requiere motivo + nuevo movimiento compensatorio (nunca edita el cierre).

## Flujo 6: Sync Google Calendar (bidireccional)
**Disparador**: evento en sistema o en Google. **Actor**: Sistema.
**Pasos**:
1. Turno creado/modificado/cancelado → push a GCal del profesional (OAuth propio); evento externo → webhook/polling → refleja bloqueo informativo.
2. Ante conflicto gana el sistema (fuente de verdad); el hueco externo se marca no-reservable y se avisa.
**Casos de error**: token OAuth revocado → aviso al profesional + agenda interna intacta; GCal caído → cola con reintento.
