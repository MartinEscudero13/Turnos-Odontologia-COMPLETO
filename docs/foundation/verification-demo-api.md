# Verification — `demo-api-integration`

**Fecha**: 2026-11-15 · **Alcance**: C-05/C-06 montados en la API real

## Resultado

| Gate | Resultado |
|---|---|
| Tests del flujo demo | **4 passed** (`tests/test_demo_api.py`) |
| Suite completa | exit 0 |
| `ruff` | `All checks passed!` |
| `mypy` | 102 archivos, 0 errores |
| OpenSpec | `demo-api-integration` válido |

## Rutas verificadas

- `GET /api/health`
- `GET /api/turnos` con actor de headers
- `GET /api/publico/demo/catalogo`
- `GET /api/publico/demo/disponibilidad`
- `POST /api/publico/demo/verificacion`
- `POST /api/publico/demo/reservas` → `201` con `token_publico`
- Reserva sin verificación → `403`

## Composición

`backend/app/demo.py` crea:

- `ServicioTurnos` en memoria;
- `ServicioReservasPublicas` con catálogo, pacientes, tenants, tokens, contador, verificador y auditoría en memoria;
- catálogo demo `demo` con 2 profesionales, 2 sillones, 2 prestaciones y horarios Lun–Dom;
- datos ficticios, sin PHI ni credenciales.

## Límites

- El estado de C-05/C-06 se pierde al reiniciar el proceso.
- La persistencia SQL real sigue aplicando solo a auth/catálogos.
- C-07…C-11 siguen sin montar.
- Caja/señas siguen usando el adaptador fake de Mercado Pago y no están expuestas en la app de demo.
