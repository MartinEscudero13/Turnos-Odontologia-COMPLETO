# Tasks — `demo-api-dominios`

## 1. RED — tests HTTP primero

- [x] 1.1 Escribir `tests/test_demo_api_dominios.py` con lista de espera (201/403), caja (201 + consulta + día cerrado 409) y seña (reserva con/sin seña, lectura pública, listado interno, webhook 503); verificar que fallan por rutas ausentes (404) antes de implementar.

## 2. Composition root

- [x] 2.1 Extender `backend/app/demo.py` con reloj único, lista de espera (servicio + auto-oferta + hueco/oferta ports) y seed de pacientes/usuarios ficticios; verificar que el módulo importa sin DB ni red.
- [x] 2.2 Cablear caja en memoria (movimientos, cierres, pendientes, ajustes, cuentas, turnos, usuarios, UoW) y verificar que un movimiento se registra y se consulta.
- [x] 2.3 Cablear señas (servicio, consulta, aplicación, webhook con `secreto=None`), configurar la regla demo y pasar `sena_port` a C-06; verificar que la reserva devuelve el bloque `sena`.

## 3. App wiring

- [x] 3.1 Montar los routers de C-07, C-10 y C-11 (público, interno, webhook) en `create_app`; verificar que health/auth/catálogos/C-05/C-06 siguen respondiendo.
- [x] 3.2 Registrar el handler global de `TurnoError` con `codigo`, `codigo_dominio` y alternativas; verificar 403/404/409 en los routers montados.
- [x] 3.3 Correr los tests nuevos hasta GREEN y triangular el caso de día cerrado y `SIN_SENA`.

## 4. Documentación y cierre

- [x] 4.1 Actualizar `README.md`, `CONTINUAR.md` y `CHANGES.md` con el estado real (C-05/C-06/C-07/C-10/C-11 montados; C-08/C-09 pendientes).
- [x] 4.2 Escribir `docs/foundation/verification-demo-api-dominios.md` con evidencia y límites.
- [x] 4.3 Correr `pytest`, `ruff`, `mypy`, `openspec validate --all --strict`; archivar el change y dejar el árbol limpio.
