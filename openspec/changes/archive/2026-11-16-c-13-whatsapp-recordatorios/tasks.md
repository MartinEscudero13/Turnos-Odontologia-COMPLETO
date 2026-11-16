# Tasks — `c-13-whatsapp-recordatorios`

## 1. Persistencia

- [x] 1.1 `models/whatsapp.py` con `mensajes_wa`.
- [x] 1.2 Migración `012_whatsapp_recordatorios.py` con RLS, estados, UNIQUE de proveedor y downgrade.
- [x] 1.3 Repositorios SQL de mensajes y turnos con teléfono.

## 2. Dominio

- [x] 2.1 `app/whatsapp/puertos.py`: entidades, protocolos y adaptadores fake.
- [x] 2.2 `app/whatsapp/twilio.py`: envío REST y validación de firma.
- [x] 2.3 `app/whatsapp/servicio.py`: recordatorios idempotentes, fallback, cola, webhook, recall.
- [x] 2.4 `ServicioTurnos.confirmar` con transición PENDIENTE → CONFIRMADO.

## 3. Borde y demo

- [x] 3.1 Schemas y router (`/api/whatsapp/*`, `/api/webhooks/whatsapp`).
- [x] 3.2 Cableado en `demo.py` con fake/Twilio por env y auto-oferta C-07.
- [x] 3.3 Página `/app/whatsapp` en el SPA.

## 4. Cierre

- [x] 4.1 Tests de dominio, HTTP y PostgreSQL.
- [x] 4.2 README, `.env.example`, CHANGES, AGENTS/AUTHORS/CONTINUAR y KB PO-03.
- [x] 4.3 Gates, archivado, commit y CI.
