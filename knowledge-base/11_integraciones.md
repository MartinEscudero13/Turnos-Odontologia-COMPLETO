# Integraciones Argentina (extra)

> Extra no canónico: profundiza lo que el Discovery marcó "No evidenciado" (precios WA, MP Checkout vs link, ARCA WS, validación OS). Nunca reemplaza los canónicos; traza a RN-IN, RN-SE, RN-OS.

## Estado por integración (v1 vs roadmap)

| Integración | v1 (MVP) | Post-v1 | Qué transparentar por tenant |
|---|---|---|---|
| WhatsApp | Cloud API/BSP oficial: plantillas (confirmación, recordatorio 24 h, cancelación, auto-oferta) + webhook entrante + estados | Bot conversacional que agenda solo; recall automático | Proveedor (BSP), número, costo/conversación |
| Mercado Pago | Link/Checkout Pro para señas + webhook idempotente + política visible | Cobro total online, devoluciones automáticas, cuotas | Modo (link/checkout/QR), credenciales por tenant |
| Google Calendar | OAuth por profesional, sync bidireccional, sistema como fuente de verdad | Multi-calendario por sillón, videollamada | Cuenta vinculada, última sync, conflictos |
| Obras sociales | Cobertura configurable + liquidación (RN-OS) | Validación realtime 1–2 OS piloto (SOAP/WS), manejo de caída OS | "Configurada" vs "validada en vivo" por OS |
| ARCA (ex-AFIP) | Fuera: integra con contador | Facturación electrónica con CUIT por tenant, factura del propio servicio en ARS | Roadmap declarado, no promesa |

## Guion técnico de demo (competidores top-5)

1. WA: ¿API oficial o QR? Mostrar plantilla aprobada + estado LEIDO en agenda. 2. MP: ¿checkout/link/QR? Pagar seña ficticia ($1 de prueba) y ver webhook. 3. GCal: revocar OAuth y ver degradación. 4. OS: cargar afiliado ficticio (DNI 99.999.999, OSDE) y ver si valida en vivo o aplica tabla. 5. Exportación 1-clic + backup declarado + roles.

## Riesgos y mitigaciones

- Caída de OS/MP/WA → cola con backoff, email fallback, agenda/caja intactas (RN-IN-03).
- Cambio de precios WA/API → costo visible por tenant; plantillas utilitarias (no marketing) para menor costo.
- Deuda regulatoria (ARCA/Ley 27.706) → roadmap público "comprobado vs roadmap", asesor legal (PO-07/PO-10).
