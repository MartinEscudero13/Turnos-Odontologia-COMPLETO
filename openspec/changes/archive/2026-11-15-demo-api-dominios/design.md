# Design

## Context

`create_app` ya monta health, auth, catálogos, C-05 y C-06 sobre un composition root en memoria
(`app/demo.py`). Los routers de C-07, C-10 y C-11 existen con el patrón `crear_router(svc)` y sus
servicios se cablean en los harness de tests. Ver `proposal.md`.

## Goals / Non-Goals

**Goals:** exponer C-07/C-10/C-11 en la app real, compartir un único estado demo entre dominios, probar
el flujo por HTTP, mantener verdes los gates existentes.

**Non-Goals:** persistencia SQL de esos dominios, UI de C-09/C-10/C-11, C-08/C-09 montados, proveedor
real de Mercado Pago o WhatsApp, cambios de contrato.

## Decisions

**D1 — Un solo composition root.**
`build_demo_services()` crea un `DemoServices` con todos los servicios y adaptadores. El estado se
comparte: el mismo `ServicioTurnos`, `CatalogoMemoria`, `PacienteMemoria`, `TenantMemoria` y reloj
alimentan C-05, C-06, C-07, C-10 y C-11. Esto permite que una reserva pública genere una seña y que una
cancelación emita el hueco a la lista de espera.

**D2 — Reloj único inyectable.**
El reloj es una función `Callable[[], datetime]` aware; los tests pueden congelarlo. Por defecto usa
`datetime.now(UTC)`. Caja deriva el día operativo en `-03:00`.

**D3 — C-11 enganchado a C-06.**
`ServicioReservasPublicas` recibe `sena_port=servicio_senas`. La configuración demo exige seña del 30%
para `Consulta` y `SIN_SENA` para `Limpieza`, de modo que el flujo feliz crea seña y el alternativo no.

**D4 — Webhook fail-closed.**
Sin `MP_WEBHOOK_SECRET` real, el servicio de webhook se cablea con `secreto=None`; el endpoint responde
`503 WEBHOOK_NO_CONFIGURADO`. Es el comportamiento honesto: no se inventan credenciales.

**D5 — Handler global de `TurnoError`.**
Los routers de dominio no atrapan sus excepciones: las mapea la app que los hospeda. `create_app`
registra un handler que usa `exc.codigo`, `exc.mensaje`, `codigo_dominio` cuando existe y las
alternativas de `ConflictoSolape`. Sin esto, montar los routers convertiría errores de dominio en 500.

**D6 — Datos ficticios y límites declarados.**
Se siembran dos pacientes, dos usuarios internos y turnos de referencia del tenant `demo`. Nada de PHI
ni credenciales. El estado se pierde al reiniciar y la persistencia SQL sigue limitada a auth/catálogos.

## Risks / Trade-offs

- La demo mezcla dominios en memoria: un reinicio borra turnos, movimientos y señas → documentado.
- C-08/C-09 quedan afuera: ficha, odontograma y presupuesto siguen sin ruta → deuda declarada.
- El webhook montado siempre responde 503 sin secreto → se declara en la verificación.

## Verification

- Tests HTTP: lista de espera alta/listado, caja movimiento/consulta, reserva con seña, lectura pública
  de la seña, listado interno y webhook sin secreto.
- Suite completa, `ruff`, `mypy`, `openspec validate --all --strict`.
- Smoke con `uvicorn` sobre `/api/health`, `/api/lista-espera`, `/api/caja/movimientos`.
