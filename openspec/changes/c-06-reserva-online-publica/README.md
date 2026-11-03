# C-06 `reserva-online-publica` — estado: preparado, NO implementado

> Artefacto SDD preparado el **2026-11-03**. No hay código de este change en
> `backend/` ni en `tests/`. No está verificado, no está archivado y el
> checkbox de `CHANGES.md` sigue en `[ ]`.

## Qué resuelve

El paciente reserva, cancela o reprograma por un link público sin login
(`/r/:tokenTenant`), viendo **sólo huecos reales** calculados en el servidor. El
anti-solapamiento, el cálculo de `fin`, los estados y las 3 alternativas del
`409` ya existen en C-05: C-06 los expone a un actor anónimo sin relajar ninguna
garantía (RN-AG-02, RN-GL-02).

## Artefactos

| Archivo | Contenido |
|---|---|
| `proposal.md` | Problema, alcance, actores, US-010/US-011, dependencia con C-05, deuda declarada (C-03, C-04, C-13, C-11, C-07, UI) y criterios globales |
| `design.md` | Decisiones D1–D11 con alternativas y trade-offs, OQ-1..OQ-9, seams con firmas, riesgos y plan de despliegue (sin DDL) |
| `specs/reserva-publica/spec.md` | 9 requirements, 32 escenarios (feliz, error de negocio, borde exacto de anticipación, concurrencia, multi-tenant, privacidad) |
| `tasks.md` | 47 tareas TDD rojo-primero, cada una con el test exacto y el archivo destino |

## Decisiones en una línea

1. **D1** Disponibilidad server-side reusando el motor de C-05 (grilla 15 min).
2. **D2** Tenant resuelto por la ruta; el token de turno no cruza tenants.
3. **D3** Token público UUID por turno, vigente mientras el turno es gestionable.
4. **D4** Identificación nombre + teléfono E.164 con vinculación por teléfono.
5. **D5** Anti-spam en capas: rate-limit + verificación single-use.
6. **D6** Anticipación `CANCEL_ANTICIPACION_H` (default 24 h) reusando la
   comparación de C-05 (borde exacto acepta).
7. **D7** `409` + 3 alternativas reusando `ConflictoSolape`, sin locks ni carrito.
8. **D8** Privacidad por allow-list de DTO y `404` uniforme; logs sin PHI.
9. **D9** Puertos (`CatalogoPort`, `PacientePort`, `TokenRepositorio`,
   `VerificadorPort`, `ContadorPort`, `NotificadorPort`, `AuditoriaPort`) con
   adaptadores en memoria.
10. **D10** Sin migración nueva: `turnos.token_publico` e índice único de la 003;
    contadores en Redis.
11. **D11** `:tokenTenant` resuelto por puerto (hoy `slug`, sujeto a OQ-4).

## Lo que NO hace (por diseño)

- No implementa login/JWT (C-03): las rutas públicas no leen headers de actor.
- No crea señas ni toca Mercado Pago (C-11): el turno queda `PENDIENTE`.
- No auto-oferta huecos a lista de espera (C-07): sólo libera el hueco.
- No envía WhatsApp/email (C-13): emite evento por `NotificadorPort`.
- No trae UI: no hay `frontend/` en el árbol (C-01 pendiente).

## Valores pendientes (no inventados)

`RESERVA_TTL_H`, `CANCEL_ANTICIPACION_H` (default 24 h fijado por RN-RE-03),
`PUBLIC_RATE_LIMIT_MAX`, `PUBLIC_RATE_LIMIT_VENTANA_S`,
`PUBLIC_VERIFICACION_TTL_MIN`, `PUBLIC_DISPONIBILIDAD_HORIZONTE_D`,
`PUBLIC_ANTISPAM_MODO` y el formato de `:tokenTenant` se documentan por **nombre**;
todo número que la KB no fije queda como OQ en `design.md`.

## Siguiente paso

1. Revisar `specs/reserva-publica/spec.md` con `revisor-escenarios-turnos`.
2. Cerrar las OQ con el dueño.
3. Recién entonces `/opsx:apply c-06-reserva-online-publica`.
