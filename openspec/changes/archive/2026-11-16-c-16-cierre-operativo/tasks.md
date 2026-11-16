# Tasks — `c-16-cierre-operativo`

## 1. Agenda

- [x] 1.1 `ServicioTurnos.confirmar`, `marcar_presente`, `marcar_ausente` con auditoría.
- [x] 1.2 Endpoints `/confirmar`, `/presente`, `/ausente`.
- [x] 1.3 Acciones en `AgendaPage` según la máquina de estados.
- [x] 1.4 `tests/test_turnos_estado.py` y cobertura HTTP.

## 2. Caja y presupuesto

- [x] 2.1 `ImputacionCaja` conecta la aceptación de C-09 con `imputar_tramo_paciente`.
- [x] 2.2 UI de caja: anular con motivo, cobrar pendientes, cierres y reportes por rango.
- [x] 2.3 UI de presupuesto: aceptar/rechazar líneas y resolver hallazgos.
- [x] 2.4 Tests HTTP y de componentes.

## 3. OS, calendario y usuarios

- [x] 3.1 Activar/desactivar obras sociales y ver detalle de liquidación.
- [x] 3.2 Desconectar links de Google Calendar.
- [x] 3.3 Activar/desactivar usuarios del tenant.

## 4. C-15 restante

- [x] 4.1 KPI `ocupacion_pct` en dominio, SQL, schema y UI.
- [x] 4.2 `tools/superadmin.py` cross-tenant por CLI.
- [x] 4.3 `tools/backup.py` + servicio Compose `backup` + `backups/` ignorado.

## 5. Cierre

- [x] 5.1 `tests/test_demo_api_acciones.py` y tests de componentes.
- [x] 5.2 Gates: ruff, mypy, pytest local/PostgreSQL, frontend y OpenSpec.
- [x] 5.3 Documentación, archivado y CI.
