# Informe de Discovery — Sistema de gestión de turnos odontológicos

**Materia:** Metodología I
**Proyecto:** Turnos-Odontologia
**Integrantes:** A COMPLETAR
**Fecha:** 2026-09-29

---

## Resumen ejecutivo

Se investigaron 18 sistemas con gestión de turnos/agenda (prioridad Argentina, luego Latam e internacionales) más 3 turneros argentinos complementarios, con búsquedas web en vivo el 2026-09-29 y criterio de solo afirmar lo verificado en fuente pública (distinguiendo funcionalidad comprobada de afirmación comercial; lo no demostrado se consigna como "No evidenciado"). Hallazgos: nadie une bien los tres mundos argentinos (clínica odontológica profunda + obras sociales/ARCA + WhatsApp/Mercado Pago); DentalSoft lidera el encaje operativo local, Dentalink es el techo funcional regional, DentalTec tiene el moat de validación de obras sociales, y FLAP el mejor flujo seña→reserva; seña vía Mercado Pago + bot de WhatsApp ya es estándar esperado, los precios locales son mayormente opacos y la trazabilidad/cumplimiento demostrable es un vacío general. El MVP sugerido incluye agenda multi-profesional/sillón con anti-solapamiento, reserva online 24/7, recordatorios por WhatsApp, ficha + odontograma FDI que deriva en presupuesto, caja multi-medio con señas de Mercado Pago, cobertura configurable de obras sociales, lista de espera, Google Calendar y base legal mínima; se postergan ARCA nativa, validación realtime de obras sociales, periodontograma completo e IA diagnóstica.

---

# Investigación de mercado — Sistemas odontológicos con gestión de turnos y agenda

**Proyecto:** Turnos-Odontologia (sistema de gestión de turnos odontológicos)
**Etapa:** Discovery (previo a Knowledge Base)
**Archivo:** `discovery/competidores.md`
**Fecha de consulta de todas las fuentes:** 2026-09-29 (salvo indicación contraria)
**Idioma:** español formal
**Criterio metodológico:** solo se afirma lo verificado en fuente pública (sitio oficial, documentación, precios, ayuda, videos oficiales, normativa oficial). Lo no demostrado se consigna como **"No evidenciado"**. Se distingue entre *funcionalidad comprobada* (visible en producto/documentación) y *afirmación comercial* (marketing sin evidencia funcional pública).

---

## Índice

1. [Metodología y alcance](#1-metodología-y-alcance)
2. [A. Tabla comparativa (18 sistemas, ordenados por relevancia para Argentina)](#a-tabla-comparativa)
3. [Fichas individuales por sistema (relevamiento completo del brief)](#fichas-individuales)
4. [B. Matriz de puntuación ponderada 0–5](#b-matriz-de-puntuación)
5. [C. Análisis competitivo](#c-análisis-competitivo)
6. [D. Recomendación final + MVP sugerido](#d-recomendación-final)
7. [Fuentes (URL + fecha)](#fuentes)
8. [Limitaciones y puntos no cubiertos](#limitaciones)

---

## 1. Metodología y alcance

**Objetivo:** identificar soluciones existentes que gestionen turnos/agenda odontológica, comparar funcionalidades y detectar oportunidades para un producto competitivo argentino.

**Prioridad geográfica:** 1) Argentina, 2) Latinoamérica, 3) internacionales relevantes utilizables o inspiradores.

**Búsquedas realizadas (12+ búsquedas distintas, web en vivo el 2026-09-29):**

1. `software odontológico Argentina gestión turnos agenda`
2. `sistema turnos odontología agenda pacientes nube`
3. `Dentalink software dental funcionalidades precios`
4. `Nubimed historia clínica odontológica Argentina`
5. `Doctoralia agenda online médicos Argentina funcionalidades`
6. `AgendaPro software agenda belleza salud precios funcionalidades`
7. `Fresha software reservas clínicas precios funcionalidades marketplace`
8. `DentiDesk software odontológico Chile Latam odontograma`
9. `Doctoralia Argentina reserva turnos online obras sociales`
10. `OdontoVida / Consultorio odontológico software historia clínica odontograma presupuesto Argentina` (+ hallazgos: DentalTec, OdontoApp, Dentatools, Odontoly, Docfav, DenPro)
11. `Gesden software dental odontograma historia clínica precios`
12. `Clinic Cloud software dental historia clínica odontograma precios España`
13. `DentalTec Argentina obras sociales nomenclador validación`
14. `FLAP software odontólogos Argentina agenda Mercado Pago señas`
15. `Ley 26529 27706 historia clínica electrónica Argentina protección datos personales salud`
16. `Bewe.io SimplyBook software reservas salud Latinoamérica precios WhatsApp`
17. `OdontalWeb OdontoApp DentalPro Argentina precios funcionalidades`

**Dimensiones relevadas por sistema (según brief):** nombre/empresa/país/URL; segmento; modalidad; agenda; turnos digitales; automatización; gestión odontológica; administración; integraciones; operación; seguridad/cumplimiento; modelo comercial; fortalezas/limitaciones/diferenciales; adopción publicada.

**Advertencia crítica de lectura:** los precios en Argentina cambian con frecuencia y varios proveedores no publican precio (piden contacto). Todos los precios citados son los publicados el día de consulta y deben revalidarse antes de decidir. Ninguna afirmación de "cumplimiento Ley X" por parte de un proveedor equivale a certificación oficial salvo registro verificable (ej. ReNaPDiS, ARCA, RGPD).

---

## A. Tabla comparativa

Ordenada por **relevancia para Argentina** (combinación de: focos odontológico + operación real en ARS/obras sociales/Mercado Pago/WhatsApp + soporte local + evidencia de adopción local).

| # | Sistema / Empresa / País | URL oficial | Segmento | Modalidad | Agenda | Turnos digitales + WhatsApp | Clínica odontológica | Admin / cobros AR | Precio publicado (2026-09-29) | Diferencial clave | Limitación clave |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **Dentalink** — Dentalink SpA, Chile (Latam + España) | https://www.softwaredentalink.com | Consultorios y clínicas dentales 1–N sillones | SaaS nube 100% web (Chrome recomendado) | Comprobada: agenda multiusuario, control de agenda, multi-sede, reportes | Comprobada: agenda online, confirmaciones automáticas por sucursal, notificaciones correo + WhatsApp, tareas automáticas de reagendamiento, videoconsulta; IA (Contact Center, Rx, notas) como afirmación comercial 2026 | Comprobada: HCD, odontograma + periodontograma, presupuestos, documentos clínicos, módulos ortodoncia/estética, videos 3D | Comprobada: caja, pagos presenciales y online, cuotas/créditos, cobranza programada, gastos, inventario, liquidaciones, +50 reportes Excel; facturación electrónica según país (VeriFactu ES comprobado; ARCA **No evidenciado**) | No publica precio; recurrente mensual/semestral/anual; sin contratos mínimos (afirmación oficial) | Líder latam en profundidad odontológica + escala; API en plan Titanium | Sin precio público; sin evidencia de validación de obras sociales argentinas ni Mercado Pago / ARCA nativos |
| 2 | **DentalTec** — Tándem Digital, Argentina | https://web.dentaltec.com.ar | Odontólogos, clínicas, círculos/federaciones/CORA | SaaS web 100% (afirmación oficial) | Comprobada (descripción): agenda + recordatorios WhatsApp (98% entrega, 40% menos ausentismo — afirmación comercial) | Reserva/validación de prácticas online; recordatorios WhatsApp | Comprobada: odontograma digital, CIE-10, imágenes adjuntas (detalle periodontograma **No evidenciado**) | **Diferencial AR:** validación en tiempo real vs +15 OS (OSDE, Swiss, Jerárquicos, Sancor…), nomencladores versionados, flujo Círculo→Federación→CORA, facturación ARCA (ex-AFIP) (afirmación oficial con casos CORA/Círculo Sgo. del Estero) | No publica precio | Único con validación preventiva anti-débitos (−64% según vendor) y gestión jerárquica institucional | Foco institucional/administrativo; UX clínica menos demostrada públicamente; sin versión internacional |
| 3 | **DentalSoft** — Equipo argentino (La Plata/Rosario), Argentina | https://dentalsoft.com.ar | Clínicas dentales PyME (300+ clínicas, afirmación oficial) | SaaS nube, cualquier dispositivo | Comprobada: vista día/semana/mes, drag&drop con confirmación, bloqueos/feriados, urgencias/sobreturnos con anti-solapamiento, multi-sucursal, Google Calendar por profesional, horarios por odontólogo | Comprobada: turnos online 24/7 en 4 pasos (DNI reconoce paciente existente, filtro por especialidad/OS), recordatorios WhatsApp/email auto-actualizables (−40% ausencias según vendor), chatbot web | Comprobada (módulo): historias clínicas (detalle odontograma/periodontograma **No evidenciado** en página pública) | Comprobada: caja diaria multi-medio (efectivo/tarjeta/transf./**Mercado Pago**/OS), cobertura automática por OS y plan, liquidaciones OS, comisiones, egresos/anulaciones trazables, KPIs | No publica precio | Mejor equilibrio AR turnos+WhatsApp+Mercado Pago+OS+Google Calendar con contacto directo con desarrolladores | Odontograma no demostrable públicamente; seguridad/cumplimiento y precios no publicados |
| 4 | **Odontal Web** — Argentina | https://odontalweb.com | Odontólogos/consultorios que facturan a OS vía colegios | SaaS nube, sin instalación | Comprobada (descripción): agenda por profesional, duración, vacaciones/feriados, rol recepcionista | Recordatorios para reducir ausentismo (canal **No evidenciado** si es WhatsApp; help no público) | Comprobada (descripción): ficha digital, antecedentes, Rx/fotos adjuntas, odontograma intuitivo, presupuestos desde odontograma con honorarios/OS | **Diferencial AR:** facturación OS mensual + seguimiento liquidaciones, aranceles actualizados por OS/colegio, estados de cuenta y reportes de deuda | No publica precio; "asesoría sin costo" | Integración con colegios profesionales y aranceles (encaje institucional AR) | Sin reserva online 24/7 demostrada; sin Mercado Pago/WhatsApp/API demostrados; precios y seguridad no publicados |
| 5 | **FLAP** — Argentina (flap.com.ar) | https://flap.com.ar/odontologos | Odontólogo independiente → clínica multi-box | SaaS nube | Comprobada: agenda multi-profesional por especialidad/box, duraciones, bloqueos, estados, autoasignación por carga | Comprobada: página de reserva 24/7 (prestación+profesional+fecha), avisos email/WhatsApp según config, seña vinculada a reserva | Comprobada: HCD + evoluciones, odontograma FDI (piezas/superficies/eventos), prestaciones con tiempos/precios/especialidades | Comprobada: señas y cobros con **Mercado Pago**, analíticas de agenda (reservas, cancelaciones, demanda) | No publica precio; configuración y capacitación inicial sin cargo (oficial) | Seña + Mercado Pago + autoasignación en el flujo de reserva (anti-sillón-vacío) | Sin obras sociales/ARCA demostrados; sin periodontograma/firma digital demostrados |
| 6 | **Dentatools** — opera AR (dentatools.co/ar), origen Latam | https://dentatools.co/ar/ | Consultorios particulares en pesos (1–3 sillones) | SaaS nube navegador | Comprobada: agenda compartida, enlace de auto-agendado, bloqueo instantáneo, recordatorios WhatsApp | Comprobada: auto-agendado por link (WhatsApp/redes/sitio), confirmación auto | Comprobada: HCD (anamnesis/evolución), odontograma interactivo con historial, adjuntos, presupuestos PDF | Comprobada parcial: cobros/presupuestos/saldos en ARS; suscripción en ARS; **explícitamente NO:** OS/prepagas ni factura AFIP del servicio | **Inicial $15.000/mes (1 prof.), Profesional $30.000/mes (hasta 3), +$8.000/prof. extra**; trial sin tarjeta; precios sin impuestos; no emiten factura AFIP (oficial) | Precio ARS claro + onboarding guiado; ideal particular sin OS | Descarta OS y facturación fiscal: inútil si el consultorio factura OS; integraciones (API/GCal/AFIP) **No evidenciadas** |
| 7 | **Livio** — Argentina | https://www.liviodental.com | Clínicas con facturación ARS 5–20M/mes (afirmación oficial) | SaaS nube + inbox/CRM | Comprobada (descripción): agenda visual por profesional/sucursal, estados (pendiente/confirmado/no-show/cancelado) | Comprobada (descripción): chatbot omnicanal 24/7 que agenda solo, recordatorios WhatsApp/SMS/email 24h antes, pipeline leads→paciente, inbox único | Historia clínica mencionada al pasar (detalle **No evidenciado**) | Comprobada (descripción): dashboard (facturación estimada, producción por profesional, no-shows, ocupación), leads→conversión | No publica precio | Enfoque comercial/IA conversacional + "Hecho en Argentina, listo para Ley 27.706" (alcance legal **No evidenciado** con registro) | Sin odontograma/periodontograma/presupuestos/OS/ARCA/Mercado Pago demostrables; riesgo de humo IA sin demo |
| 8 | **DentalCore** — Argentina/Latam | https://dentalcore.app/ | Consultorio unipersonal → multi-sucursal | SaaS nube + portal paciente + bot WA + voz | Comprobada (descripción): agenda multi-doctor drag&drop, confirmación WA, auto-relleno de huecos, sala de espera virtual, tareas/chat interno | Comprobada (descripción): portal (turnos, tratamiento, consentimientos, chatbot IA), bot WA con 9 flujos vía QR (confirmar, huecos, recall, leads, fotos a ficha) | Afirmación diferencial: CDSS con "17 motores", odontograma, HCD, facturación ARCA + OS (todo como afirmación comercial; demo necesaria) | Afirmación: ARCA + OS, inventario con escaneo de facturas | Plan gratis mencionado (detalle **No evidenciado**) | Apuesta IA/CDSS + voz + auto-relleno huecos (si es real, diferenciador fuerte) | Casi todo es afirmación sin evidencia funcional pública; exigir demo + pruebas |
| 9 | **Odontoly** — Argentina | https://odontoly.com/ | Consultorios que priorizan dato local y trabajo offline | Local-first (PC propia) + app móvil iOS/Android + acceso remoto | Comprobada (descripción): agenda con GCal bidireccional, bloqueo por procedimiento, reprogramación 1-clic, confirmación WA 24h antes | Confirmación WA, bot agendamiento 24/7 y recepcionista por voz (como add-ons pagos) | Comprobada (descripción): ficha (antecedentes/alergias/medicación), Rx/fotos/PDF, odontograma anatómico (32 marcas, cuadrante/arcada/pieza, PDF), presupuestos/cuotas→caja | Comprobada (descripción): caja diaria, cuotas vencidas, métricas; add-ons: WA Business, IA, AFIP; backup 3-2-1, Ley 25.326 (afirmación) | **Setup USD 599,90 + desde USD 99,90/mes Básico; cobro en ARS a blue del mes, lock 12m** (oficial) | Único local-first + offline 30 días + backup 3-2-1; honestidad comparativa vs SaaS USD | Precio en USD (fricción AR); OS/ARCA como add-on no incluido; modelo instalable choca con SaaS puro |
| 10 | **Dentidesk** — Chile (Latam: AR, MX, CO, PE, UY…) | https://www.dentidesk.cl / https://www.dentidesk.com | Clínicas dentales Latam multi-sede | SaaS nube + app móvil (Play; App Store "pronto") | Comprobada (módulos): gestión avanzada de citas, multi-sucursal, 20+ reportes | Cita online y comunicaciones (detalle canal **No evidenciado** en fuentes abiertas) | Comprobada: fichas por especialidad (odontograma, disfunción, endodoncia, periodoncia, cirugía ortognática, ortodoncia), nomenclaturas chilena/internacional/universal, interconsultas/derivaciones | Comprobada (módulos): facturación, insumos, reportes financieros/administrativos (detalle AR/OS/Mercado Pago **No evidenciado**) | No publica precio | Profundidad clínica multi-especialidad + multi-país (incluye Argentina) | Sin evidencia AR local (OS/Mercado Pago/ARCA/WhatsApp API); precios y seguridad no publicados |
| 11 | **Doctoralia** — Grupo Docplanner (Polonia/España), fuerte AR | https://www.doctoraliar.com / https://pro.doctoralia.com/ar | Profesionales/centros que necesitan captación (marketplace) | Marketplace + SaaS agenda (reserva online) | Comprobada: agenda por consulta/profesional, horarios por servicio con duración/costo, sincronizable con sistema propio, confirmación/modificación/anulación | Comprobada: reserva online gratuita para paciente, recordatorios SMS, gestión en app (confirmar/reprogramar/cancelar, chat, fotos), filtros por OS/prepaga (OSDE, OSECAC…), videoconsulta | **No:** sin odontograma/HCD odontológica (ficha clínica personalizable genérica en planes Pro, no dental) | Comprobada parcial: muestra precios particulares (responsabilidad del centro); pagos/facturación clínica **No evidenciado** | Paciente gratis; profesional: planes de pago (precio **No evidenciado** públicamente AR) | Marketplace líder (+110k perfiles AR, 80M pacientes grupo, reseñas) + filtro OS + app 4.9★ | No es software odontológico: sin odontograma/presupuestos/caja/OS-liquidación; dependencia del marketplace |
| 12 | **AgendaPro** — Chile (opera AR/MX/CL…), 20k+ negocios | https://agendapro.com/ar | Belleza/spa/salud/estética (no dental nativo) | SaaS nube + marketplace + POS | Comprobada: agenda online multi-calendario, colores por estado, anticipos, bloqueos, multi-sucursal | Comprobada: reservas 24/7 por link/redes/QR, recordatorios WA/email/SMS (1–3 días antes), Sofía IA agenda, Julia IA ventas, Google Reserve, LinkPro | Comprobada parcial: ficha cliente + historial + exámenes adjuntos; **sin odontograma/periodontograma** | Comprobada: caja, inventario, comisiones automáticas, pagos online/link/POS, facturación según país (CFDI MX, SII CL; ARCA **No evidenciado**), reportes IA | No publica precio AR (planes mensual/anual; prueba gratis) | Maquinaria comercial (marketplace 2M usuarios, marketing, comisiones, POS) + soporte 24/7 | Sin clínica dental (odontograma/presupuestos por pieza/OS argentinas); facturación AR no demostrada |
| 13 | **Fresha** — Reino Unido (global) | https://www.fresha.com/es | Belleza/bienestar/salud (no dental nativo) | SaaS nube + apps iOS/Android + marketplace global | Comprobada: calendario multiusuario/recursos, lista de espera auto-relleno, tiempos de espera, formularios | Comprobada: reservas online web/Google/IG/FB 24/7, notificaciones email gratis + SMS/WA pagas (100 gratis/miembro/mes; luego 0,02 USD SMS, 0,04–0,11 WA), depósitos anti-no-show, chat | Comprobada parcial: registros/notas/SOAP/admisión/fotos; **sin odontograma**; HIPAA para salud (afirmación oficial) | Comprobada: TPV, presupuestos/facturas, membresías/bonos/giftcards, inventario; Mercado Pago/ARCA/OS **No evidenciado** | **Desde 19,95 USD/mes (1 miembro) / 14,95 USD por miembro en equipo; +20% comisión solo por cliente nuevo vía marketplace (mín. 6 USD); SMS/marketing e Insights de pago** | Mejor UX de reservas + marketplace mundial (130k negocios) + precios transparentes | Sin odontología; costo USD + add-ons; sin encaje AR (OS/ARCA/Mercado Pago) |
| 14 | **Nubimed** — España (euro-foco) | https://www.nubimed.com | Clínicas médicas pequeñas/medianas (no dental nativo) | SaaS nube + app + sala de espera | Comprobada: agenda clínica multiagenda, control sala de espera con turnos/pantalla, cita online 24/7 | Comprobada parcial: cita online, recordatorios email gratis + SMS 0,08€, envío/actualización vía WhatsApp (API **No evidenciado**) | Comprobada parcial: HCD personalizable (apartados/preguntas, CIE-10, Vademécum, dibujo sobre imagen), presupuestos/paquetes/descuentos/aseguradoras; **odontograma nativo No evidenciado** | Comprobada: contabilidad/facturación (TicketBAI/VeriFactu ES), mutuas, laboratorios, liquidaciones, firma digital, receta electrónica, trazabilidad, cuadro de mando | **Lite 27,40€/mes +IVA (1 agenda; +2,40€/agenda extra); Full 50,10€/mes +IVA (+5,10€/extra); recepción/admin ilimitados gratis; 25 GB incl.; SMS 0,08€** | HCD ultra-personalizable + sala de espera + recepción ilimitada gratis | Sin odontograma; foco fiscal ES; precio en EUR; sin AR (OS/Mercado Pago/ARCA) |
| 15 | **Clinic Cloud** — España (+3.000 clínicas, afirmación) | https://clinic-cloud.com | Clínicas dentales y polis (ES) | SaaS nube multi-sede | Comprobada (docs): agendas por profesional/servicio, alarmas email/SMS | Cita online, recordatorios WA/correo (plan-dependiente; API **No evidenciado**) | Comprobada (docs): odontograma online (situación/tratamientos/presupuesto/citas/histórico) + periodontograma | Comprobada: presupuestos, facturación, caja, marketing; ARCA/OS/Mercado Pago **No evidenciado** | **Mini 29€/mes, Pro 49€/mes +IVA, Max a medida; demo 15 días** | Referencia europea de odontograma→presupuesto→factura en un flujo | Sin encaje AR; RGPD (no Ley 25.326); precios EUR |
| 16 | **Gesden G5 / One (Infomed)** — España, 30 años | https://www.infomedsoftware.com/software/gesden/gesden-g5/ | Clínicas dentales tradicionales ES | Local (G5) y nube (One) + PACS imagen | Agenda multi (descripción general; detalle anti-solapamiento **No evidenciado** en abierto) | Cita online (portal); recordatorios **No evidenciado** en abierto | Comprobada: odontograma con evolución, periodontograma comparativo, ortodoncia básica, imagen/PACS, dentIA Rx→odontograma (módulo) | Facturación VeriFactu (certificados G5 5.54 / One 1.585.0 oficiales); AR/OS **No evidenciado** | **Compra desde 1.200€ + mantenimiento desde 75€/mes; Easy 75€/mes + 150€ licencia extra + 200€ instalación (fuentes 2025–2026)** | Estándar de facto ES + PACS + IA radiológica | Modelo licencia pesado, sin trial publicado, nula tropicalización AR |
| 17 | **Docfav** — España (opera AR) | https://pro.docfav.com/es-ar/software-para-odontologos | Consultorios odontológicos PyME | SaaS nube | Comprobada (descripción): agenda online por tratamiento/cirugía/revisión, GCal | Comprobada (descripción): agenda online, recordatorios WA (título) aunque cuerpo cita SMS/email (inconsistencia → verificar en demo), presupuestos por email, portal paciente | Comprobada (descripción): HCD odontológica (anamnesis personalizable, evolutivos por visita, Rx/fotos ilimitadas, consentimientos), presupuestos con seguimiento, odontogramas interactivos (mención) | Comprobada parcial: cobros asociados, informes (ingresos/ocupación); OS/ARCA/Mercado Pago **No evidenciado** | Trial gratis (precio **No evidenciado**) | HCD odontológica + portal + firma + videollamada centralizados; servidores UE (adecuación AR según vendor) | Inconsistencia WA; sin evidencia AR fiscal; precio oculto |
| 18 | **Bewe (+ SimplyBook genérico)** — España/Latam/US, 20+ países | https://www.bewe.io / https://simplybook.me/es/ | Belleza/wellness/fitness/salud (no dental) | SaaS nube + IA "Linda" | Comprobada: agenda multi-recurso (profesional/sala/equipo), duración auto, disponibilidad real | Comprobada: Linda agenda/reagenda/cancela por WA/IG/web 24/7 (<2 seg, afirmación), campañas WA/email, penalización no-shows | **No:** fichas cliente genéricas; sin odontograma | Comprobada: cobros, informes, suscripciones; Mercado Pago/ARCA/OS **No evidenciado** | **Bewe desde 29 USD/mes (1–3 empleados, 50 conv. Linda); SimplyBook freemium + SMS/WA de pago** | IA conversacional madura + marca blanca agencias | Sin odontología; costo USD; sin encaje AR clínico-fiscal |

**Turneros argentinos complementarios (no puntuados en matriz, pero relevantes como referencia de UX local):** Booksolut (https://booksolut.com/industria/odontologia — agenda + bot WA + seña Mercado Pago + odontograma básico; comparativa anti-Calendly), TurnoLink (https://turnolink.com.ar/salud/odontologos — agenda 24/7 + cobro Mercado Pago + ficha + videollamada; 14 días trial), Mi Agenda Profesional (https://miagendaprofesional.com/para-odontologos — bot IA WA 24h + recordatorios 24h/2h + seña Mercado Pago; plan gratuito). Consultados el 2026-09-29. Son la prueba de que **seña vía Mercado Pago + bot WhatsApp** ya es estándar esperado en AR, no diferencial.

**Descartados del top con motivo:** XDentalCloud/DriCloud (excelentes en ES —desde 42€/mes, 15 días trial— pero sin operación AR ni OS/Mercado Pago; sirven solo como referencia UX/IA), OdontoApp (odontoapp.com.ar —solo landing "10+ odontólogos", sin funcionalidades/precios públicos → insuficiente evidencia), Odonto-web.com (origen no-AR claro, precios en MXN/USD antiguos → baja relevancia AR), DenPro AR (denpro.ar —$19.900 Basic/$29.900 Team, odontograma FDI— pero marca espejo de la española + "50+ consultorios" sin evidencia AR sólida → observar, no priorizar), DentalPro.tech (USD 29/69/129 —agenda/GCal/odontograma/pagos/IA briefing— origen no declarado, sin OS/ARCA/WhatsApp nativo → interesante UX pero débil AR).

---

## Fichas individuales

> Formato por sistema: identificación → agenda → turnos digitales → automatización → clínica → administración → integraciones → operación → seguridad/cumplimiento → comercial → fortalezas/limitaciones → adopción. Todo lo no demostrado = "No evidenciado".

### F1. Dentalink (Chile / Latam + España) — https://www.softwaredentalink.com

- **Empresa/país:** Dentalink SpA, Chile; operación Latam (CL/CO/MX/PE…) + España. **Segmento:** consultorios y clínicas dentales de cualquier tamaño.
- **Modalidad:** SaaS 100% en línea, sin instalación; Chrome recomendado; PC/tablet/móvil (comprobado en FAQ).
- **Agenda:** agenda e historia clínica digitales, control de agenda, multi-sede, comisiones/multicentro, informes de gestión, roles/permisos (comprobado en planes/funcionalidades).
- **Turnos digitales:** agendamiento online desde canales, confirmaciones automáticas configurables por sucursal con estado visible, videoconsulta, tareas automáticas de reagendamiento (comprobado). Contact Center IA 24/7 por WA/teléfono (afirmación 2026, verificar en demo).
- **Automatización:** recordatorios/notificaciones correo + WhatsApp, email marketing, encuestas/campañas, análisis de pacientes, panel de tareas críticas (comprobado). IA (Rx, notas por voz, resumen clínico, Contralor, simulador sonrisa) como afirmación comercial.
- **Clínica:** HCD (demográficos, antecedentes, evoluciones, planes, recetas, imágenes), documentos clínicos + firma electrónica, odontograma + periodontograma, presupuestos, módulos ortodoncia/estética facial, videos 3D (comprobado).
- **Administración:** caja, pagos presenciales/online + "maquinitas", cuotas/créditos/cobranza programada, gastos, inventario, laboratorios, convenios, liquidaciones, +50 reportes Excel (comprobado). Facturación electrónica integrada / VeriFactu ready en ES (comprobado ES; ARCA **No evidenciado**).
- **Integraciones:** API en plan Titanium (comprobado CO/MX); WhatsApp como canal (comprobado); Mercado Pago / GCal / AFIP-ARCA **No evidenciado**.
- **Operación:** usuarios ilimitados simultáneos con perfiles (comprobado); multi-sede (comprobado); exportación Excel (comprobado); migración/carga de pacientes (comprobado); soporte y actualizaciones incluidos (comprobado); auditoría como "Contralor IA" (afirmación).
- **Seguridad:** AWS + RGPD UE (comprobado ES); Ley 25.326 / 27.706 **No evidenciado**.
- **Comercial:** trial/demo personalizada sin compromiso; sin contratos mínimos; pago recurrente mensual/semestral/anual (o trimestral según país); tarjeta; precio a cotizar (comprobado). Planes Esencial/Pro(+gastos, inventario, comisiones, multicentro, informes)/Titanium(+campañas, tareas, ortodoncia, chat interno, API).
- **Fortalezas:** amplitud odontológica real + marketing/recupero + escala regional. **Limitaciones:** precio opaco; sin tropicalización AR demostrada. **Adopción:** liderazgo declarado Latam sin cifra pública verificada en fuentes abiertas (consignar como afirmación).

### F2. DentalTec (Argentina) — https://web.dentaltec.com.ar

- **Empresa/país:** Tándem Digital, Argentina. **Segmento:** odontólogos, clínicas, círculos, federaciones, CORA.
- **Modalidad:** 100% web sin instalación (afirmación oficial).
- **Agenda:** agenda con recordatorios WhatsApp, 40% menos ausentismo, 98% entrega (afirmaciones con métricas vendor; exigir evidencia).
- **Turnos digitales:** carga de prácticas + validación instantánea en consultorio; portal institucional (comprobado en descripción).
- **Automatización:** validación preventiva (afiliado, nomenclador, topes, frecuencias, autorizaciones, dependencias) antes de cargar (diferencial declarado); 64% menos débitos, 75–80% menos tiempo gestión (afirmaciones).
- **Clínica:** odontograma digital, CIE-10, imágenes adjuntas (comprobado en descripción); periodontograma **No evidenciado**.
- **Administración:** facturación jerárquica Círculo→Federación→CORA, comisiones por nivel, branding por entidad, nomenclador versionado, ARCA ex-AFIP (afirmaciones oficiales con casos de éxito).
- **Integraciones:** +15 OS vía SOAP (OSDE, Swiss, Sancor, Jerárquicos, OSSEG, IOSEP, NOBIS, Prevención, Federada, COLMED, Staff/Brindar, Traditum, OSP San Juan, OSMATA/Sanitas, Hamburgo, Policía Federal) (listado oficial); Mercado Pago / GCal / WA-API **No evidenciado**.
- **Operación:** multi-entidad, roles, trazabilidad 100% (afirmación); soporte 24/7 (afirmación). **Seguridad:** "JWT+bcrypt, nivel empresarial" (afirmación; Ley 25.326/27.706 **No evidenciado** con detalle).
- **Comercial:** sin precio público; contacto consultivo. **Adopción:** +2.000 profesionales, 5/5 en 30 reseñas, CORA + Círculo Sgo. del Estero (afirmaciones vendor).
- **Fortalezas:** único anti-débitos + jerarquía institucional AR. **Limitaciones:** UX clínica y turnos 24/7 menos demostrados; dependencia de integraciones SOAP por OS.

### F3. DentalSoft (Argentina) — https://dentalsoft.com.ar/

- **Empresa/país:** equipo desarrollador argentino (La Plata + Rosario). **Segmento:** clínicas dentales PyME.
- **Modalidad:** nube 100%, sin instalación, multi-dispositivo (comprobado).
- **Agenda:** día/semana/mes, drag&drop con confirmación, mensual con chips, urgencias/sobreturnos con anti-solapamiento, bloqueos/feriados, multi-sucursal, GCal por profesional, horarios por odontólogo intersectados con clínica (comprobado —el anti-solapamiento más explícito del relevamiento).
- **Turnos digitales:** reserva online 24/7 en 4 pasos (datos→profesional→fecha→confirmar), slots realtime, DNI reconoce existente, filtro especialidad/OS, confirmación WA inmediata, landing propia `tuclinica.dentalsoft.com.ar`, chatbot (comprobado).
- **Automatización:** recordatorios WA/email configurables (anticipación/horario/mensaje), auto-actualización ante confirma/cancela (comprobado).
- **Clínica:** historias clínicas (módulo listado; odontograma/periodontograma/imágenes **No evidenciado** en abierto).
- **Administración:** caja multi-medio con Mercado Pago + OS, cobertura automática por tratamiento/plan, cierre diario, egresos/anulaciones trazables, registro turno→caja 1-clic, liquidaciones OS, comisiones, KPIs realtime (ocupación, facturación, tratamientos/turno, ranking por odontólogo, ausentismo) (comprobado).
- **Integraciones:** GCal (comprobado), Mercado Pago (comprobado como medio; checkout online **No evidenciado** si es link/QR/API), WA (canal comprobado; Business API **No evidenciado**).
- **Operación:** roles configurables, multi-sucursal, importación pacientes + capacitación, puesta en marcha <24h (afirmaciones con contacto directo dev). Exportación **No evidenciada**.
- **Seguridad/cumplimiento:** **No evidenciado** (exigir Ley 25.326/27.706, backup, 2FA en demo).
- **Comercial:** sin precio público; soporte ES por WA/email (comprobado). **Adopción:** 300+ clínicas AR (afirmación).
- **Fortalezas:** flujo turno→caja→liquidación OS + Mercado Pago + GCal, todo AR-céntrico. **Limitaciones:** clínica profunda por demostrar.

### F4. Odontal Web (Argentina) — https://odontalweb.com

- **Segmento:** odontólogos que facturan a OS vía colegios. **Modalidad:** nube sin instalación (comprobado).
- **Agenda:** por profesional (horarios, duración, vacaciones/feriados, delegación a recepcionista) (comprobado). Bloqueos/sobreturnos/anti-solapamiento **No evidenciado**.
- **Turnos digitales:** reserva online 24/7 **No evidenciada**; recordatorios anti-ausentismo (canal **No evidenciado**).
- **Clínica:** ficha digital (antecedentes, Rx/fotos/documentos), odontograma intuitivo, presupuestos desde odontograma con honorarios/OS (comprobado en descripción).
- **Administración:** estados de cuenta, reportes de deuda por antigüedad/monto, facturación OS mensual + liquidaciones, aranceles auto-actualizados por OS/colegio (comprobado en descripción —diferencial institucional).
- **Integraciones:** colegios profesionales (afirmación); WA-API/GCal/Mercado Pago/ARCA **No evidenciado**. **Operación/seguridad/comercial:** asistencia personalizada, implementación en días (comprobado); precio/roles/exportación/seguridad **No evidenciado**.

### F5. FLAP (Argentina) — https://flap.com.ar/odontologos

- **Segmento:** independiente → clínica multi-box. **Modalidad:** SaaS (página de reservas + agenda + clínica).
- **Agenda:** multi-profesional (especialidades, box, duración, disponibilidad), bloqueos, estados, anti-cruces, autoasignación por carga diaria/semanal (comprobado).
- **Turnos digitales:** turnero 24/7 (prestación+profesional+fecha), seña/email/WA según config (comprobado).
- **Clínica:** HCD + evoluciones, odontograma FDI (piezas/superficies/eventos + historial), prestaciones con tiempos/precios/especialidades, ortodoncia (mención) (comprobado).
- **Administración:** señas y cobros con Mercado Pago vinculados a reserva, analíticas semanales (reservas, horas, cancelaciones, demanda) (comprobado). OS/ARCA **No evidenciado**.
- **Operación:** permisos (recepción vs odontólogo), sucursales según plan (comprobado). **Seguridad:** **No evidenciado**. **Comercial:** sin precio; setup + capacitación sin cargo (comprobado).

### F6. Dentatools (AR) — https://dentatools.co/ar/

- **Segmento:** particulares en pesos. **Modalidad:** nube navegador (comprobado).
- **Agenda/turnos:** agenda compartida + auto-agendado por link + bloqueo instantáneo + recordatorios WA auto-actualizables (comprobado).
- **Clínica:** anamnesis/antecedentes/alergias/evolución, odontograma interactivo con historial, adjuntos (comprobado). Periodontograma/imágenes avanzadas **No evidenciado**.
- **Administración:** cobros/presupuestos PDF/saldos en ARS (comprobado); OS/prepagas y factura AFIP explícitamente NO (comprobado —honestidad valorable).
- **Comercial:** $15.000 / $30.000 / +$8.000, trial sin tarjeta, sin impuestos incl., sin factura AFIP (comprobado). Soporte ES remoto (comprobado). Adopción **No evidenciada** con cifras.

### F7. Livio (Argentina) — https://www.liviodental.com

- **Segmento:** clínicas ARS 5–20M/mes (afirmación). **Modalidad:** plataforma + inbox/CRM + chatbot (descripción).
- **Agenda/turnos:** visual por profesional/sucursal, estados, recordatorios WA/SMS/email, chatbot 24/7 que agenda solo, pipeline leads, inbox único, dashboard (no-shows, leads, producción) (descripción oficial; exigir demo).
- **Clínica:** mención "registrado en historia clínica" (detalle **No evidenciado**). **Administración:** facturación estimada/producción (descripción). OS/Mercado Pago/ARCA **No evidenciado**. **Seguridad:** "listo para Ley 27.706" (afirmación sin registro demostrable).

### F8. DentalCore (Argentina/Latam) — https://dentalcore.app/

- **Todo lo diferencial es afirmación comercial a verificar:** CDSS 17 motores, agenda drag&drop + auto-relleno huecos + sala virtual, bot WA 9 flujos por QR, voz que carga odontograma/dicta evolución, portal (turnos/tratamiento/consentimientos/chatbot), inventario con escaneo, ARCA + OS, plan gratis. **Nada de esto tiene evidencia funcional pública suficiente.** Oportunidad si es real; riesgo alto si no. Demo obligatoria con guion (ver §D).

### F9. Odontoly (Argentina) — https://odontoly.com/

- **Modalidad diferencial:** local-first en PC + app móvil + remoto `usuario.odontoly.com`; offline hasta 30 días; backup 3-2-1 (local+Drive cifrado+cloud); Ley 25.326 (afirmaciones detalladas).
- **Agenda/turnos:** GCal bidireccional, bloqueo por procedimiento, reprogramación 1-clic, confirmación WA 24h; bot agenda e IA voz como add-ons (descripción).
- **Clínica:** ficha (alergias/medicación destacadas, Rx/fotos/PDF, búsqueda DNI/tel, export CSV/JSON), odontograma anatómico 32 marcas + PDF, presupuestos/cuotas→caja + recordatorio cuotas (descripción).
- **Comercial:** USD 599,90 setup + USD 99,90/mes base, ARS a blue, lock 12m (comprobado). Migración Excel/Sheets incluida (afirmación).

### F10. Dentidesk (Chile/Latam) — https://www.dentidesk.cl

- **Clínica (comprobado):** fichas especializadas (odontograma, disfunción, endodoncia, periodoncia, cirugía ortognática, ortodoncia), nomenclaturas chilena/internacional/universal, interconsultas/derivaciones, multi-sucursal, 20+ reportes, app móvil. Agenda avanzada + facturación/insumos como módulos (listado oficial). **AR-local (OS/Mercado Pago/ARCA/WA-API/precios/seguridad): No evidenciado.**

### F11. Doctoralia (Grupo Docplanner) — https://www.doctoraliar.com

- **Marketplace + agenda (comprobado):** +110k especialistas AR, reserva online gratuita, SMS + app (confirmar/cancelar/chat/fotos), filtros OS/prepaga, videoconsulta, reseñas, sincronización con agenda propia, agenda por consulta/profesional con servicios/duración/costo. **Clínica dental y caja: no.** Precio profesional no público. App AR 4.9★ (2k reseñas). Cumplimiento sanitario **No evidenciado** como HCD.

### F12. AgendaPro (Chile/Latam, opera AR) — https://agendapro.com/ar

- **Comercial no-dental (comprobado):** agenda 24/7 link/redes/QR, recordatorios WA/email/SMS, IA Sofía/Julia, ficha + sesiones, caja/inventario/comisiones, pagos online/link/POS, marketplace 2M usuarios, Google Reserve, marketing/lealtad/giftcards, multi-sucursal, soporte 24/7, 20k negocios. Ficha clínica personalizable + exámenes (comprobado). **Odontograma/periodontograma/OS-AR/ARCA: no.** Precio AR no público.

### F13. Fresha (UK/global) — https://www.fresha.com/es

- **Reservas/marketplace (comprobado con precios):** calendario multiusuario/recursos, lista de espera, formularios, reservas web/Google/IG/FB, email gratis + SMS/WA pagas, depósitos, TPV, presupuestos/facturas, bonos/membresías, inventario, insights, apps. 19,95 USD / 14,95 USD por miembro; marketplace 20% (mín. 6 USD) solo nuevo cliente; 100 WA/SMS gratis luego pago; trial 7 días. **Odontograma: no.** HIPAA (afirmación). Mercado Pago/ARCA/OS: no.

### F14. Nubimed (España) — https://www.nubimed.com

- **Clínica general (comprobado):** HCD personalizable (tablas/textos/selects/imagen/dibujo), CIE-10 + Vademécum, presupuestos/paquetes/descuentos/aseguradoras, agenda + sala de espera con tickets/pantalla, cita online 24/7, email gratis + SMS 0,08€ + WA (canal, API no demostrada), contabilidad TicketBAI/VeriFactu, mutuas, laboratorios, liquidaciones, firma digital, receta electrónica, trazabilidad, 25 GB. Lite 27,40€ / Full 50,10€ +IVA. **Odontograma nativo: No evidenciado.** RGPD (marco ES).

### F15. Clinic Cloud (España) — https://clinic-cloud.com

- **Dental ES (comprobado en docs/FAQ):** agendas por profesional/servicio, odontograma (situación/tratamientos/presupuesto/citas/histórico) + periodontograma, presupuestos, facturación, caja, marketing, multi-sede, permisos. Mini 29€ / Pro 49€ / Max a medida; demo 15 días; +3.000 clínicas (afirmación). **AR: No evidenciado.**

### F16. Gesden G5/One (Infomed, España) — https://www.infomedsoftware.com/software/gesden/gesden-g5/

- **Dental tradicional ES (comprobado):** odontograma con evolución médico-económica, periodontograma comparativo, ortodoncia básica, PACS imagen, dentIA Rx, VeriFactu certificado (G5 5.54 / One 1.585.0). Compra 1.200€ + 75€/mes; Easy 75€/mes + extras; sin trial. **AR: No evidenciado.**

### F17. Docfav (España, opera AR) — https://pro.docfav.com/es-ar/software-para-odontologos

- **Odontología PyME (descripción oficial):** agenda por tratamiento/cirugía/revisión, GCal, recordatorios (WA en título vs SMS/email en cuerpo —inconsistencia), HCD con anamnesis personalizable + evolutivos + Rx/fotos ilimitadas + consentimientos, odontogramas interactivos (mención), presupuestos con seguimiento, portal paciente, firma, videollamada, cobros, informes. Trial gratis; precio no público; servidores UE (adecuación AR según vendor). **OS/ARCA/Mercado Pago: No evidenciado.**

### F18. Bewe / SimplyBook (España/global) — https://www.bewe.io

- **No-dental con IA (comprobado):** agenda multi-recurso, Linda agenda/reagenda/cancela por WA/IG/web, campañas WA/email, penalización no-shows, cobros, informes, suscripciones, marca blanca; 20+ países. Desde 29 USD/mes. SimplyBook: reservas + WA/SMS/email + pagos + IA "Ask Simply" + MCP. **Odontograma/OS/ARCA: no.**

---

## B. Matriz de puntuación

**Pesos (brief):** Turnos y automatización 25% · Clínica odontológica 20% · Integraciones locales y WhatsApp 15% · Administración/cobros/facturación 15% · Experiencia del paciente 10% · Seguridad/exportación/trazabilidad 10% · Precio/facilidad de adopción 5%.

**Escala 0–5:** 0 ausente/sin evidencia · 1 mención sin evidencia · 2 parcial/débil · 3 sólido con evidencia · 4 fuerte/diferencial · 5 referencia de mercado. **Regla:** lo no evidenciado públicamente no supera 2 aunque el vendor lo afirme (criterio crítico del brief).

| # | Sistema | T&Aut 25% | Clínica 20% | Integ-Local+WA 15% | Admin 15% | Exp-Pac 10% | Seg/Exp/Traz 10% | Precio/Adop 5% | **Total /5** |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Dentalink | 4 | 5 | 3 | 4 | 4 | 3 | 2 | **3.95** |
| 2 | DentalSoft AR | 5 | 2 | 4 | 5 | 5 | 1 | 2 | **3.80** |
| 3 | DentalTec AR | 3 | 3 | 4 | 5 | 2 | 2 | 2 | **3.30** |
| 4 | FLAP AR | 4 | 4 | 3 | 3 | 4 | 1 | 3 | **3.35** |
| 5 | Dentidesk | 3 | 5 | 2 | 3 | 3 | 2 | 2 | **3.10** |
| 6 | Clinic Cloud | 3 | 4 | 1 | 3 | 3 | 2 | 3 | **2.80** |
| 7 | Doctoralia | 4 | 0 | 3 | 1 | 5 | 1 | 3 | **2.35** |
| 8 | Dentatools AR | 4 | 3 | 2 | 2 | 3 | 1 | 5 | **2.85** |
| 9 | Odontal Web AR | 2 | 3 | 2 | 4 | 1 | 1 | 2 | **2.25** |
| 10 | AgendaPro | 4 | 1 | 2 | 3 | 4 | 1 | 3 | **2.60** |
| 11 | Livio AR | 3 | 1 | 2 | 2 | 3 | 1 | 2 | **2.05** |
| 12 | DentalCore AR | 3 | 3 | 2 | 2 | 3 | 1 | 3 | **2.50** |
| 13 | Odontoly AR | 3 | 4 | 2 | 3 | 2 | 3 | 1 | **2.85** |
| 14 | Fresha | 4 | 0 | 1 | 3 | 5 | 2 | 3 | **2.45** |
| 15 | Nubimed | 3 | 2 | 1 | 4 | 2 | 2 | 2 | **2.40** |
| 16 | Gesden | 2 | 5 | 0 | 3 | 2 | 2 | 1 | **2.40** |
| 17 | Docfav | 3 | 3 | 1 | 2 | 4 | 2 | 3 | **2.55** |
| 18 | Bewe | 4 | 0 | 1 | 3 | 3 | 1 | 3 | **2.10** |

**Cálculo ejemplo (Dentalink):** 4×.25=1.00 + 5×.20=1.00 + 3×.15=.45 + 4×.15=.60 + 4×.10=.40 + 3×.10=.30 + 2×.05=.10 → **3.95**.

**Lectura:** nadie domina todo. Dentalink lidera por profundidad odontológica integral; DentalSoft lidera en encaje operativo AR (turnos+Mercado Pago+OS+GCal); DentalTec lidera en capa institucional/fiscal AR; FLAP equilibra agenda+clínica+seña; Dentidesk/Clinic Cloud/Gesden son referencias clínicas sin tropicalización AR; Doctoralia/AgendaPro/Fresha/Bewe son referencias de captación/UX, no de clínica dental.

---

## C. Análisis competitivo

### C1. Estándares de mercado (lo que el cliente ya espera y no diferencia)

1. **Agenda multi-profesional/sillón con duraciones, bloqueos y anti-solapamiento.** DentalSoft (drag&drop + detección), FLAP (autoasignación por carga), Dentalink/Dentidesk (multi-sede) lo tienen. Un MVP sin esto nace obsoleto.
2. **Reserva online 24/7 por link + recordatorios automáticos.** Todos los relevantes lo ofrecen; la vara es: link compartible (WA/IG/web), slots realtime, confirma/cancela/reprograma sin llamar, recordatorio configurable. Reducción de ausentismo declarada 40% (DentalSoft, DentalTec) —cifra vendor, no auditada, pero marca la promesa esperada.
3. **WhatsApp como canal por defecto.** Recordatorio + confirmación + aviso. La diferencia ya no es "tener WhatsApp" sino *qué protocolo*: ¿API oficial con plantillas y trazabilidad, o QR/informal? Casi ningún vendor AR lo transparenta (solo precios WA en Fresha; el resto "No evidenciado" a nivel API). Oportunidad de transparencia.
4. **Odontograma + presupuestos vinculados.** Dentalink, Dentidesk, Clinic Cloud, Gesden, FLAP, Dentatools lo tienen en algún grado. El estándar es: hallazgo por pieza → plan → presupuesto → aceptación parcial → imputación a agenda/caja. Sin este encadenamiento, el odontograma es un dibujo.
5. **Caja multi-medio + reportes.** Cierre diario, métodos de pago, comisiones, reportes exportables. Dentalink (+50 Excel), DentalSoft (KPIs realtime), AgendaPro (comisiones auto) lo normalizan.
6. **Precios opacos + trial.** La mayoría AR no publica precio (Dentalink, DentalSoft, DentalTec, FLAP, Odontal Web). Los que publican (Dentatools ARS, Odontoly USD, Fresha USD, Nubimed EUR, Gesden EUR) permiten anclar expectativas. El mercado tolera "pedir demo", pero castiga la falta de trial sin tarjeta.

### C2. Diferenciadores reales (verificados, no slogans)

- **DentalTec:** validación preventiva contra OS + jerarquía Círculo→Federación→CORA. Nadie más lo demuestra. Es el único moat regulatorio-administrativo AR.
- **DentalSoft:** anti-solapamiento explícito (urgencias/sobreturnos) + GCal por profesional + cobertura OS automática + Mercado Pago en el mismo flujo turno→caja. Moat operativo.
- **FLAP:** seña con Mercado Pago atada a reserva + autoasignación por carga. Moat anti-sillón-vacío.
- **Odontal Web:** aranceles actualizados por OS/colegio + liquidación OS. Moat institucional silencioso.
- **Dentatools:** honestidad radical (declara lo que NO hace: OS/AFIP) + precio ARS transparente. Moat de confianza para particulares.
- **Odontoly:** local-first + offline 30 días + backup 3-2-1 + export CSV/JSON. Moat de soberanía del dato (a costo USD).
- **Dentalink:** amplitud (periodontograma, ortodoncia/estética, videos 3D, laboratorios, API Titanium) + escala regional. Moat de completitud.
- **Dentidesk:** fichas multi-especialidad + nomenclaturas configurables. Moat clínico.
- **Doctoralia:** marketplace + reseñas + filtro OS + app 4.9★. Moat de demanda (no de gestión).
- **Fresha/AgendaPro/Bewe:** UX de reserva, lista de espera auto-relleno, depósitos, marketing/retención, IA conversacional. Moat de conversión.

### C3. Vacíos del mercado argentino (oportunidades)

1. **Nadie une bien los tres mundos AR: clínica odontológica profunda + OS/ARCA + WhatsApp/Mercado Pago.** DentalTec domina OS/ARCA pero flojea en turnos 24/7/UX; DentalSoft/FLAP dominan turnos/Mercado Pago pero flojean en OS-profunda/ARCA; Dentalink domina clínica pero sin AR. **El hueco es el producto que haga las tres a la vez con evidencia.**
2. **Transparencia de integraciones.** Ningún AR publica: ¿WhatsApp Business API oficial o QR? ¿Mercado Pago via Checkout/QR/link? ¿ARCA via WS con CUIT? ¿GCal OAuth bidireccional? Todo es "integración" genérica. Un producto que documente esto gana confianza técnica.
3. **Trazabilidad y cumplimiento demostrable.** Ley 27.706 (HCE interoperable, firma digital, 3 niveles de acceso, auditoría), Ley 26.529 (derechos del paciente, consentimiento), Ley 25.326 (datos personales). Todos dicen "cumplimos"; casi nadie muestra: roles/permisos granulares, log de auditoría, export, backup, consentimiento firmado, firma digital. Solo Odontoly (backup/export) y Nubimed/Gesden (marco ES) dan algo. **Vacío enorme y sensible.**
4. **Precios ARS con factura AFIP/ARCA del propio servicio.** Dentatools cobra en ARS pero *no emite factura AFIP* (declarado). Odontoly cobra en USD-blue. El resto oculta precio. Hay espacio para "precio ARS claro + factura ARCA + sin setup abusivo".
5. **Lista de espera inteligente + seña + reprogramación.** Solo DentalCore (afirmación) y Fresha (lista de espera) lo tienen; FLAP/Booksolut/TurnoLink tienen seña pero sin lista de espera demostrada. Combinar *hueco cancelado → oferta automática a lista → seña Mercado Pago → reagenda* es diferencial concreto.
6. **Obras sociales sin fricción para el consultorio chico.** DentalTec apunta a instituciones; Odontal Web a colegios; DentalSoft a cobertura automática. Falta el flujo simple para 1–3 sillones: verificar afiliado, aplicar arancel, separar paciente/OS, generar liquidación presentable, en 3 clics.
7. **Migración y salida.** Solo Odontoly (migración Excel/Sheets + export CSV/JSON) y Dentalink (carga/migración) lo mencionan. Nadie promete "tus datos salen en 1 clic". En salud, el lock-in asusta. Garantizar exportación es diferencial ético y comercial.
8. **Offline real.** Solo Odontoly lo aborda. En interior con conectividad inestable, SaaS puro se cae. Modo degradado (ver agenda del día, cobrar, sincronizar luego) es oportunidad.

### C4. Oportunidades de innovación (con criterio crítico)

- **IA útil, no decorativa:** briefing diario (qué silla rinde, quién no confirmó, qué presupuesto vence), resumen por paciente antes de entrar, detección de huecos + oferta WA, transcripción de evolución con firma (DentalCore/Docfav/Livio lo prometen; nadie lo demuestra). Hacerlo *con trazabilidad* (quién aprobó qué) es el diferencial vs "IA mágica".
- **Seña dinámica + política de cancelación:** seña mayor en horarios pico/sábados, exención para recurrentes cumplidores, liberación automática si no paga (Mi Agenda Profesional ya lo hace). Copiar y mejorar con transparencia.
- **Recall clínico (controles periódicos) + recupero comercial separados.** Casi todos mezclan "campañas" con "recall". Separar *recall sanitario* (limpieza 6m, ortodoncia, post-quirúrgico) de *marketing* genera confianza y adherencia.
- **Consentimiento + firma + foto/Rx en un flujo.** DentalCore/Docfav/Clinic Cloud lo listan; hacerlo simple en móvil (paciente firma en tablet/celu, queda en ficha con timestamp) es estándar esperado post-2024.
- **Interoperabilidad futura (HL7 FHIR / ReNaPDiS).** Solo ClinIA demuestra registro ReNaPDiS #248 (recetario). Anticipar FHIR + firma digital + consentimiento explícito posiciona para Ley 27.706 sin sobre-prometer.

---

## D. Recomendación final

### D1. Cinco competidores prioritarios para demo (con guion)

| Prioridad | Sistema | Por qué | Qué validar en demo (guion de 45 min) |
|---|---|---|---|
| 1 | **DentalSoft** (AR) | Mejor encaje operativo AR hoy: agenda anti-solapamiento + online 4 pasos + WA auto + Mercado Pago + OS + GCal | 1) Crear 2 profesionales + 2 sillones, solapar un sobreturno (¿bloquea?). 2) Reservar online filtrando por OS. 3) Confirmar/cancelar por WA y ver agenda. 4) Cobrar mixto (MP + OS) y cerrar caja. 5) Generar liquidación OS. 6) Preguntar: ¿WA API oficial? ¿Precio? ¿Backup/roles/auditoría? ¿Exportación? |
| 2 | **Dentalink** (Latam) | Referencia funcional completa + escala; techo a igualar en clínica/marketing/API | 1) Odontograma→presupuesto→cuotas→cobranza. 2) Confirmación por sucursal + reagendamiento auto. 3) Periodontograma + ortodoncia. 4) Reportes Excel + liquidaciones. 5) Preguntar: precio AR + ARCA/Mercado Pago/OS-AR + SLA/soporte ES-AR. |
| 3 | **DentalTec** (AR) | Moat regulatorio: validación OS + ARCA + jerarquía; si el producto apunta a OS, es socio o amenaza | 1) Validar afiliado ficticio vs OS (¿en vivo o mock?). 2) Cargar práctica con tope/frecuencia (¿bloquea antes?). 3) Flujo Círculo→Federación→CORA. 4) Agenda + WA. 5) Preguntar: qué OS tienen WS real, latencia, manejo de caída OS, precio, auditoría, Ley 27.706. |
| 4 | **FLAP** (AR) | Mejor flujo seña→reserva + autoasignación + odontograma FDI; UX moderna AR | 1) Configurar prestación con seña MP y reservar. 2) Autoasignación entre 2 odontólogos por carga. 3) Odontograma FDI→evolución→cobro. 4) Analítica semanal. 5) Preguntar: OS/ARCA roadmap, WA API, precio, multi-sucursal, exportación. |
| 5 | **Dentidesk** (CL/Latam) | Referencia clínica multi-especialidad + multi-país (incluye AR); vara de odontograma | 1) Fichas endodoncia/periodoncia/ortodoncia. 2) Nomenclatura por profesional. 3) Multi-sucursal + 20 reportes. 4) Cita online + comunicaciones. 5) Preguntar: operación AR (facturación, soporte, precio ARS, OS/MP/ARCA). |

**Suplentes para demo corta (20 min):** Dentatools (precio/UX particular sin OS —ideal para comparar onboarding), Odontoly (dato local/offline/backup —para discutir arquitectura), Doctoralia (captación/marketplace —para decidir si integrar o competir).

**Referencias de UX (las 3 pedidas + 1 extra):**
1. **Fresha** — reserva en segundos (servicio→profesional→hora→pago/depósito), lista de espera, depósitos anti-no-show, marketplace. Copiar: simplicidad del checkout de reserva + política de cancelación visible.
2. **AgendaPro** — agenda por colores/estados + recordatorios 1/2/3 días + comisiones auto + LinkPro/QR. Copiar: densidad operativa sin caos + marketing post-visita.
3. **DentalSoft** — reserva 4 pasos con DNI + filtro OS/especialidad + turno→caja 1-clic + KPIs. Copiar: encadenamiento turno→cobertura→caja→liquidación.
4. *(Extra)* **Nubimed/Clinic Cloud** — HCD configurable + odontograma→presupuesto→cita en un flujo. Copiar: no separar clínica de agenda.

### D2. MVP sugerido

**Imprescindibles (sin esto no lanzar):**
- Agenda día/semana multi-profesional/sillón con duraciones variables, bloqueos/feriados, sobreturnos y anti-solapamiento real (con test que lo pruebe).
- Reserva online 24/7 por link (servicio→profesional→hora) + confirmación/cancelación/reprogramación por el paciente sin llamar.
- Recordatorios + confirmación por WhatsApp (con proveedor declarado: API oficial vs QR) y email fallback; estados visibles (pendiente/confirmado/cancelado/no-show).
- Ficha + HCD mínima (antecedentes/alergias/evolución fechada + adjuntos Rx/fotos) + odontograma interactivo (FDI, historial por pieza) → presupuesto por pieza → aceptación parcial → imputación a agenda/caja.
- Caja diaria multi-medio (efectivo/transf./MP/OS) + señas Mercado Pago atadas a reserva + cierre diario + comisiones básicas + reportes (ocupación, ausentismo, facturación por profesional).
- Roles/permisos (admin/recepción/profesional), auditoría mínima (quién creó/modificó/cobró qué, cuándo), exportación CSV/Excel 1-clic, backup diario declarado.

**Diferenciadores (para ganar en AR, elegir 2–3):**
- Seña Mercado Pago con liberación automática + política de cancelación visible + lista de espera que auto-ofrece huecos cancelados.
- Cobertura OS automática por tratamiento/plan + liquidación presentable (empezar con 3–5 OS, sin prometer validación realtime hasta tener WS real; transparentar "cobertura configurada" vs "validada en vivo" —la honestidad de Dentatools como modelo).
- Google Calendar bidireccional por profesional (DentalSoft lo tiene; es muy valorado).
- Recall sanitario separado de marketing (controles 6m, post-tratamiento) + recupero de presupuestos vencidos.
- Consentimiento + firma en móvil con timestamp en ficha (base Ley 26.529/27.706).

**Postergables (no hacer en MVP):**
- Facturación fiscal ARCA nativa con CUIT (integrar después con contador; no bloquear MVP; declarar roadmap).
- Validación realtime contra OS vía SOAP/WS (complejidad DentalTec; fase 2 con 1–2 OS piloto).
- Periodontograma completo, ortodoncia/estética facial, PACS/DICOM, inventarios con lotes, multi-sucursal avanzada, IA diagnóstica/voz, marketplace propio, app nativa (portal web responsive alcanza), marca blanca.

**Principios transversales del MVP:** precio ARS transparente + factura del servicio; declarar qué es "comprobado" vs "roadmap"; demo con datos ficticios AR (DNI, OSDE/OS, nomenclador); pruebas de anti-solapamiento y de caja antes de prometer; accesibilidad móvil para recepción y paciente.

---

## Fuentes

> Todas consultadas el **2026-09-29**. Precios y funcionalidades pueden haber cambiado; revalidar antes de contratar/diseñar.

**Generales/AR:**
- ClinIA Odontología — https://www.clinia.com.ar/odontologia
- Livio — https://www.liviodental.com/
- FLAP Odontólogos — https://flap.com.ar/odontologos
- DentalSoft — https://dentalsoft.com.ar/
- DentalCore — https://dentalcore.app/
- Dentatools AR — https://dentatools.co/ar/
- Odontoly — https://odontoly.com/
- Adiasoft ERP dental AR — https://www.adiasoft.com/ar/sistema-para-clinicas-dentales
- Odontal Web — https://odontalweb.com/
- OdontoApp — https://odontoapp.com.ar/
- Odonto-web (MX/Latam, referencia) — https://odonto-web.com/
- DentalPro.tech (precios) — https://dentalpro.tech/
- DenPro AR — https://www.denpro.ar/ + precios https://www.denpro.ar/precios/
- DentalTec — https://web.dentaltec.com.ar/ + funcionalidades https://web.dentaltec.com.ar/funcionalidades + guía AR https://web.dentaltec.com.ar/software-odontologos-argentina + casos https://web.dentaltec.com.ar/casos-de-exito + top-5 https://web.dentaltec.com.ar/mejor-software-odontologico-argentina
- Docfav AR — https://pro.docfav.com/es-ar/software-para-odontologos
- Booksolut Odontología — https://booksolut.com/industria/odontologia
- TurnoLink Odontólogos — https://turnolink.com.ar/salud/odontologos
- Mi Agenda Profesional Odontólogos — https://miagendaprofesional.com/para-odontologos

**Latam:**
- Dentalink funcionalidades — https://www.softwaredentalink.com/funcionalidades
- Dentalink planes ES — https://www.softwaredentalink.com/es/planes ; planes Latam — https://www.softwaredentalink.com/planes ; home ES — https://www.softwaredentalink.com/es/
- Dentidesk CL — https://www.dentidesk.cl/ + features https://www.dentidesk.cl/dentidesk/feature ; global https://www.dentidesk.com/
- AgendaPro AR — https://agendapro.com/ar ; ES — https://agendapro.com/es ; MX — https://agendapro.com/mx ; estética — https://agendapro.com/es/medicina-estetica/software-para-clinicas-esteticas
- Doctoralia AR — https://www.doctoraliar.com/ ; activar reserva https://pro.doctoralia.com/ar/preguntas-frecuentes/activar-reserva-de-cita ; configurar reserva https://pro.doctoralia.com/ar/guias/configuracion-de-la-reserva-de-cita ; nosotros https://pro.doctoralia.com/ar/sobre-nosotros ; apps https://play.google.com/store/apps/details?id=com.doctoraliar + https://apps.apple.com/ar/app/doctoralia-argentina/id1471977166
- Bewe — https://www.bewe.io/ + https://www.bewe.ai/agenda + https://www.bewe.ai/industries/wellness

**Internacionales:**
- Fresha pricing — https://www.fresha.com/es/pricing ; features — https://www.fresha.com/es/for-business/features ; health — https://www.fresha.com/es/for-business/health-practice
- Nubimed — https://www.nubimed.com/ + planes https://www.nubimed.com/planes-precios/ + HCD https://www.nubimed.com/software-historia-clinica/ + sala espera https://www.nubimed.com/software-gestion-salas-espera/
- Clinic Cloud tarifas — https://clinic-cloud.com/tarifas ; dental — https://clinic-cloud.com/software-clinica-dental-programa-odontologico ; odontograma — https://clinic-cloud.com/faq/historia-clinica-y-pacientes/odontograma
- Gesden G5 — https://www.infomedsoftware.com/software/gesden/gesden-g5/ ; One — https://www.infomedsoftware.com/software/gesden/gesden-one/ ; VeriFactu — https://www.infomedsoftware.com/software/gesden/verifactu/
- Comparativa ES (precios 2026) — https://mejorsoftware.org/software-para-clinicas-dentales/
- SimplyBook — https://simplybook.me/es/

**Normativa AR:**
- Ley 27.706 texto — https://www.argentina.gob.ar/normativa/nacional/ley-27706-380710/texto + https://www.argentina.gob.ar/normativa/nacional/norma-380710/texto + InfoLEG https://servicios.infoleg.gob.ar/infolegInternet/anexos/380000-384999/380710/norma.htm
- Ley simple HCE — https://www.argentina.gob.ar/justicia/derechofacil/leysimple/salud/historia-clinica-electronica
- Reglamentación (BO 2025) — https://www.boletinoficial.gob.ar/pdf/aviso/primera/291214/20250729

---

## Limitaciones

**Puntos del brief parcialmente cubiertos y por qué:**

1. **Precios exactos de Dentalink, DentalSoft, DentalTec, FLAP, Odontal Web, Livio, Doctoralia (profesional), Docfav:** no publicados en sus sitios oficiales al 2026-09-29 (modelo "pedir cotización/demo"). No se inventaron cifras; se consignó el modelo comercial declarado. Requiere contacto comercial / demo para completar.
2. **Evidencia de adopción con cifras auditadas:** solo se consignaron datos publicados por los vendors (ej. DentalSoft "300+", DentalTec "2.000+", AgendaPro "20.000", Fresha "130.000", Clinic Cloud "3.000"). No existen fuentes independientes verificables en abierto para validarlas; se marcan como afirmaciones comerciales.
3. **Seguridad y cumplimiento profundo (cifrado, backup, 2FA, auditoría, Ley 25.326/27.706, ARCA, firma digital):** la mayoría no lo documenta públicamente. Se consignó como "No evidenciado" y se dejó como guion obligatorio de demo. Solo normativa oficial (Leyes 26.529/25.326/27.706) se verificó en argentina.gob.ar / InfoLEG / Boletín Oficial.
4. **Detalles técnicos de integraciones (WhatsApp Business API vs QR, Mercado Pago Checkout/API, Google Calendar OAuth, AFIP/ARCA WS, APIs abiertas):** los vendors hablan de "integración" genérica sin documentar endpoints ni alcances. Solo Fresha (precios WA/SMS), Dentalink-Titanium (API) y DentalTec (adaptadores SOAP) dan pista técnica. Requiere demo técnica + documentación para cerrar.
5. **Videos oficiales y centros de ayuda:** se priorizaron sitios oficiales, documentación pública, precios y normativa; no se visionaron videos oficiales completos por límite de tiempo (se citan funcionalidades visibles en web/docs). Se recomienda revisarlos en fase demo.
6. **Reseñas verificadas (Capterra/Trustpilot/Play Store):** solo se citó la calificación pública de Doctoralia AR (4.9★ App Store) y menciones de comparadores (mejorsoftware.org, comparasoftware.com). No se usaron testimonios sin fuente como evidencia funcional.

---

## Verificación de fuentes

> PENDIENTE — tarea del estudiante: comprobar personalmente 5 fuentes y registrar hallazgo/corrección.

## Referencias

PENDIENTE — completar referencias en el formato exigido por la consigna.
