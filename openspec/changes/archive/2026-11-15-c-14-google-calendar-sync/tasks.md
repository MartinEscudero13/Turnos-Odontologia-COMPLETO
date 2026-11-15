# Tasks — `c-14-google-calendar-sync`

## 1. RED

- [x] 1.1 `tests/test_calendario.py`: link (alta, duplicado, RBAC), push (crear, idempotente, sin link), cancelación y auditoría.
- [x] 1.2 `tests/test_calendario.py`: webhook externo (bloqueo, conflicto, token inválido, cross-tenant), cola (pendiente, reintento, agotado, token revocado).
- [x] 1.3 `tests/test_demo_api_calendario.py`: link, push, webhook, bloqueos y RBAC por HTTP.
- [x] 1.4 `tests/test_calendario_pg.py` + helper: RLS sin tenant y roundtrip de link/evento/envío.

## 2. Persistencia

- [x] 2.1 `models/calendario.py` con `calendar_links`, `calendar_eventos`, `calendar_envios`; verificar que `Base.metadata` las registra.
- [x] 2.2 Migración `011_calendar_sync.py` con RLS, UNIQUEs, CHECKs, grants y downgrade reversible; validar el ciclo upgrade/downgrade.
- [x] 2.3 Repositorios SQL de link, evento, envío y solapamiento de turnos; validar con el test PG.

## 3. Dominio y borde

- [x] 3.1 `app/calendario/puertos.py` y `servicio.py`: push idempotente, cancelación, webhook, conflicto, cola con backoff y token revocado.
- [x] 3.2 Schemas y router con RBAC (`ADMIN`/`ODONTOLOGO` propio/`RECEPCION` lectura) y errores 401/403/404/409.
- [x] 3.3 Cablear en `demo.py` un link ficticio con pasarela fake y montar el router en `create_app`.

## 4. Cierre

- [x] 4.1 Actualizar `README.md`, `CONTINUAR.md`, `CHANGES.md` y `knowledge-base/04_modelo_de_datos.md` (migración 011, renumeración de C-14).
- [x] 4.2 `docs/foundation/verification-c-14-google-calendar.md` y gates (`pytest`, `ruff`, `mypy`, `openspec --all --strict`).
- [x] 4.3 Archivar, commitear y verificar CI.
