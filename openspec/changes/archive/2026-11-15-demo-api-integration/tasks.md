# Tasks — `demo-api-integration`

## 1. Composition root

- [x] 1.1 Crear `backend/app/demo.py` con `ServicioTurnos` y `ServicioReservasPublicas` cableados sobre adaptadores en memoria; verificar que el módulo importa sin DB ni red.
- [x] 1.2 Sembrar tenant `demo`, 2 profesionales, 2 sillones, prestaciones y horarios semanales; verificar que el catálogo público devuelve datos.
- [x] 1.3 Verificar que el seed no usa datos reales ni credenciales y que el estado es explícitamente en memoria.

## 2. App wiring

- [x] 2.1 Montar `crear_router(turnos)` y `crear_router_publico(reservas)` en `create_app`; verificar que health/auth/catalogos siguen funcionando.
- [x] 2.2 Resolver conflictos de rutas/errores y mantener un único OpenAPI; verificar `/api/turnos` y `/api/publico/demo/catalogo` no devuelven 404.
- [x] 2.3 Agregar tests HTTP de catálogo, disponibilidad y reserva; verificar 201 con token y 403 sin verificación.

## 3. Documentación y verificación

- [x] 3.1 Actualizar `README.md`/`CONTINUAR.md` con el alcance de la demo (C-05/C-06 en memoria; C-07…C-11 pendientes).
- [x] 3.2 Correr `pytest`, `ruff`, `mypy`, `openspec validate demo-api-integration --strict`; verificar el flujo con un smoke HTTP.
- [x] 3.3 Archivar el change, sincronizar spec y dejar el working tree limpio.
