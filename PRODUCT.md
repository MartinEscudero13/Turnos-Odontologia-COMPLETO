# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Existing: React 18 + TypeScript + Vite, FastAPI, PostgreSQL 15, Docker Compose. This foundation does not change the stack.

## Users

- **Paciente**: llega desde el celular, muchas veces desde un link de WhatsApp, con poca paciencia y sin cuenta. Quiere ver horarios reales y reservar sin llamar.
- **Recepción**: trabaja en desktop durante todo el día, con alta densidad de turnos, cancelaciones, sobreturnos y cobros.
- **Odontólogo**: consulta su agenda y, más adelante, ficha clínica; necesita lectura rápida y bajo ruido visual.
- **Admin del consultorio**: configura catálogos, usuarios y reglas; necesita claridad y control.

## Product Purpose

Reducir turnos perdidos y ausentismo en consultorios odontológicos pequeños y medianos, reemplazando la coordinación manual por reserva online 24/7 y una agenda operativa con anti-solapamiento real en base de datos.

## Positioning

La promesa no es “otro calendario”: el sistema combina reserva pública sin fricción, agenda multi-profesional/sillón y una restricción de exclusión en PostgreSQL que impide dobles reservas incluso bajo concurrencia. El diseño debe hacer visible esa precisión sin volver la experiencia clínica ni burocrática.

## Operating Context

- El paciente usa principalmente el celular; la reserva debe funcionar con una mano y una conexión mediocre.
- La recepción usa desktop con teclado, múltiples profesionales y cambios constantes.
- El consultorio trabaja en Argentina: español rioplatense, teléfonos E.164, fechas `-03:00`, seña por Mercado Pago y WhatsApp manual en v1.
- Hay múltiples tenants conviviendo en un mismo deploy; ningún dato de un consultorio puede aparecer en otro.

## Capabilities and Constraints

- Ya existen: tenants, usuarios, auth JWT, catálogos básicos, pacientes y turnos anti-solape.
- En preparación: reserva online pública (C-06), lista de espera, WhatsApp, pagos, caja, reportes.
- La UI no debe inventar módulos clínicos ni estados que el backend todavía no ofrece.
- Datos ficticios en demos y screenshots; nunca PHI ni credenciales.
- El paciente no tiene login en v1; la recepción y el admin sí.

## Brand Commitments

- Nombre de trabajo: **Turnos-Odontologia**.
- Tono: preciso, humano, sin infantilizar al paciente ni sobrecargar al personal.
- Sin identidad gráfica previa obligatoria; no hay logo, manual de marca ni paleta aprobada.
- Español rioplatense, sin jerga técnica en la superficie pública.

## Evidence on Hand

- `knowledge-base/`: visión, discovery, actores, reglas RN-XX, modelo de datos y flujos.
- `docs/discovery/informe-discovery.md` y PDF.
- Backend C-02/C-03/C-04 con tests.
- No hay testimonios, clientes reales, precios de venta ni métricas de producción verificadas: no inventarlos.

## Product Principles

1. **El próximo turno es la prioridad**: la interfaz reduce pasos hasta reservar, confirmar o resolver un conflicto.
2. **La precisión se muestra, no se explica**: estados, horarios y reglas se hacen visibles en la estructura.
3. **Densidad donde trabaja la recepción, calma donde decide el paciente**: misma marca, distinta intensidad.
4. **Los estados difíciles también son diseño**: sin disponibilidad, error, permiso denegado, carga y vacío tienen una salida clara.
5. **Cero datos inventados**: si la API no lo tiene, la UI lo declara o lo deja fuera.

## Accessibility & Inclusion

- WCAG 2.2 AA como objetivo.
- Navegación completa por teclado, foco visible, labels persistentes y mensajes de error asociados.
- Targets táctiles de al menos 44px en superficies móviles.
- Respeto por `prefers-reduced-motion`.
- Español claro, sin abreviaturas internas en la superficie del paciente.
