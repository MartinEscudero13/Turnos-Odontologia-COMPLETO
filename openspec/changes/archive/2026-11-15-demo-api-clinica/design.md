# Design

## Context

`create_app` monta C-05, C-06, C-07, C-10 y C-11 sobre un composition root en memoria
(`app/demo.py`). C-08 y C-09 usan el patrón `crear_router(svc)` y comparten varios puertos con los
dominios ya cableados. Ver `proposal.md`.

## Goals / Non-Goals

**Goals:** exponer ficha, odontograma y presupuesto por HTTP, compartir el consentimiento entre los
tres servicios, probar los flujos felices y un error de precondición, mantener los gates verdes.

**Non-Goals:** persistencia SQL de C-08/C-09, UI clínica, wiring real de C-09 hacia C-10, obras
sociales (C-12) y cambios de contrato.

## Decisions

**D1 — Consentimiento único.**
`app.ficha_clinica.puertos.ConsentimientoMemoria` es el mismo tipo que consumen odontograma
(re-exportado) y presupuesto. Se comparte una sola instancia: registrar el consentimiento por
`POST /api/consentimientos` habilita ficha, evolución, hallazgos y líneas clínicas.

**D2 — Pacientes, profesionales y turnos compartidos.**
Ficha y odontograma usan los mismos adaptadores en memoria (`ficha_clinica.puertos`). Se siembra
`DEMO_PACIENTE_1/2`, `PROFESIONAL_DEMO_1` y el vínculo profesional↔paciente para que el rol
`ODONTOLOGO` pueda operar. Presupuesto mantiene su propio `PacienteMemoria` (incluye obra social).

**D3 — Presupuestos y líneas compartidos con odontograma.**
`PresupuestoMemoria` y `LineaMemoria` de `app.presupuesto.puertos` se comparten entre ambos
servicios, para que una derivación del odontograma sea visible en la API de presupuestos.

**D4 — Imputación a caja simulada.**
`ServicioPresupuesto` recibe `ImputacionMemoria`. La aceptación con medio no escribe en C-10 en esta
demo; el wiring real exige un repositorio de líneas dinámico que hoy no existe. Se declara como deuda.

**D5 — Sin cobertura de obra social.**
`CoberturaMemoria` arranca vacía: el paciente demo no tiene obra social y el `a_cargo_paciente` es el
monto completo. La cobertura real llega con C-12.

## Risks / Trade-offs

- La ficha y el odontograma comparten consentimiento; si el usuario no lo registra, ambos responden
  `409 CONSENTIMIENTO_REQUERIDO`. Es el comportamiento del dominio, no un bug de wiring.
- El estado clínico es en memoria: se pierde al reiniciar.
- La aceptación de presupuesto no impacta caja → deuda declarada.

## Verification

- Tests HTTP: ficha 409 → consentimiento → ficha 201; evolución; hallazgo y su listado; presupuesto
  con línea y emisión.
- Suite completa, `ruff`, `mypy`, `openspec validate --all --strict`.
