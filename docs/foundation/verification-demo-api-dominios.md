# Verification — `demo-api-dominios`

**Fecha**: 2026-11-15 · **Alcance**: C-07, C-10 y C-11 montados en la API real

## Resultado

| Gate | Resultado |
|---|---|
| Tests nuevos del tramo | **10 passed** (`tests/test_demo_api_dominios.py`) |
| Suite completa | exit 0 |
| `ruff` | `All checks passed!` |
| `mypy` | 102 archivos, 0 errores |
| OpenSpec | `demo-api-dominios` válido (`--strict`) |

## Rutas verificadas por HTTP

- `GET /api/health`
- `GET /api/turnos` y `GET /api/publico/demo/catalogo` (siguen montados)
- `POST /api/lista-espera` → `201` · `403` para rol `PACIENTE`
- `GET /api/lista-espera` → `200`, con filtro por `prestacion_id`
- `POST /api/caja/movimientos` → `201`
- `GET /api/caja/movimientos?fecha=` → `200` con `totales_vigentes` acumulados
- `POST /api/caja/cierre` → `201`; movimiento posterior en el día cerrado → `409`
- `POST /api/publico/demo/reservas` → `201` con bloque `sena` (`PENDIENTE`, `3000` centavos)
- `GET /api/publico/demo/senas/{token}` → `200` con la misma seña
- `GET /api/senas?desde=&hasta=` → `200` con la seña del tenant
- `POST /api/webhooks/mercadopago` → `503 WEBHOOK_NO_CONFIGURADO`

## Composición

`backend/app/demo.py` arma un único grafo en memoria:

- **C-05/C-06**: turnos, catálogo, pacientes, tenants, tokens, verificación y auditoría.
- **C-07**: `ListaEsperaMemoria`, `OfertaMemoria`, `ServicioListaEspera`, `ServicioAutoOferta` y
  `HuecoLiberadoMemoria` conectado al worker (una cancelación emite el hueco).
- **C-10**: movimientos, cierres, pendientes, ajustes, cuentas por cobrar, usuarios y unidad de trabajo
  con rollback por excepción.
- **C-11**: `ServicioSenas`, `ServicioSenasConsulta`, `ServicioSenasAplicacion` y
  `ServicioSenasWebhook` con pasarela fake. La reserva pública recibe `sena_port`.
- Regla demo: `Consulta` exige `PORCENTAJE 30` sobre `10000` (3000 centavos); `Limpieza` es `SIN_SENA`.
- Datos ficticios: 2 pacientes, 2 usuarios internos, 2 profesionales, 2 sillones y horarios Lun–Dom.

## Decisiones de wiring

- **D4 — Webhook fail-closed**: sin `MP_WEBHOOK_SECRET` real se cablea `secreto=None`; el endpoint
  responde `503` y no muta señas. No se inventan credenciales.
- **D5 — Handler global de `TurnoError`**: los routers de dominio no atrapan sus excepciones; la app
  compuesta las mapea a `exc.codigo` con `codigo_dominio` y alternativas de solape. Sin esto los
  errores de C-07/C-10/C-11 se habrían convertido en `500`.

## Límites que siguen

- Todo el estado de la demo es **en memoria**: se pierde al reiniciar el proceso.
- La persistencia SQL real sigue limitada a `auth` y `catalogos`.
- **C-08 y C-09 no están montados**: ficha clínica, odontograma y presupuesto siguen sin ruta.
- La aceptación de auto-ofertas existe en el router, pero no hay endpoint para listar el token de la
  oferta emitida; el flujo cancelación → oferta se verifica a nivel de dominio, no por HTTP.
- Caja y señas comparten el adaptador fake de Mercado Pago; no hay llamadas reales al proveedor.
