# Reflexión escrita — fundación de Turnos-Odontologia

*Trabajo individual de Martin Escudero. Todas las etapas de la fundación las hice yo, solo, conversando con el agente.*

## Lo que salió mal (o a medias) y cómo me di cuenta

Lo más concreto: el informe de Discovery quedó primero en `discovery/` en vez de `docs/discovery/`, y tres referencias internas apuntaban a la ruta vieja. No lo noté yo en el momento; lo detectó la auditoría contra el PDF, y se corrigió en el commit `9d50fe7`. Me dejó una lección simple: yo daba por sentado que los archivos estaban donde yo creía, y no los verificaba. Desde entonces pido el `git status` y las rutas reales antes de dar algo por hecho.

Lo segundo: los precios de seis competidores no estaban publicados en ningún lado. La tentación era poner un número aproximado "para completar la tabla", pero los dejé marcados como "No evidenciado". Prefiero un hueco honesto a un dato inventado, porque un precio falso después se convierte en una decisión falsa (por ejemplo, posicionar nuestro plan contra un número que no existe).

Y lo tercero: en el gate final del checklist se corrigió una contradicción que venía arrastrándose — había quedado escrita una restricción de "sin restricciones duras" que chocaba con lo ya decidido. El gate la descartó. Era un detalle chico, pero muestra que los documentos largos acumulan inconsistencias si nadie los relee de punta a punta.

## Dónde usé "Ajustar" y por qué importó

Usé Ajustar (revisar y corregir en vez de aceptar automático) en varios puntos: el gate de Discovery (dije que sí, pero con brief ampliado), las rondas de Q&A, el gate final del checklist, el pre-gate del roadmap (cuando dije "seguí"), el install gate (cuando dije "todas") y la auditoría contra el PDF que terminó reordenando archivos.

Si en esos puntos hubiera puesto Continuar automático, creo que habrían pasado dos cosas: la knowledge base se habría generado sobre insumos guardados en la ubicación equivocada, y el informe habría quedado sin el formato del PDF. O sea, documentos "verdes" pero apoyados en algo roto. Ajustar me costó unos minutos cada vez y me ahorró rehacer etapas enteras.

## Spec vs. prompt suelto

La diferencia la viví en la Etapa 6. Implementé el change crear-turno-sin-solapamientos contra un contrato de 6 requisitos y 12 escenarios dado/cuando/entonces, en vez de un prompt suelto tipo "haceme la agenda". Con el contrato sabía exactamente cuándo terminé (primero 79/79 tests en verde con vitest + `tsc` limpio, después 104/104 con pytest al reimplementar en el stack Python obligatorio con el spec intacto) y cómo comprobarlo; con un prompt suelto, termino cuando "parece que anda". Dos detalles me lo confirmaron: primero, el ciclo TDD me obligó a escribir el test antes que el código en cada task, y en la reimplementación Python el RED se observó en cada módulo mientras que la regresión aportó un fallo real (faltaba auditar el crear-con-flag) que corregí en vez de ocultarlo, más un spot-check de mutación en la corrida original que probó que los tests no eran triviales. Segundo, cuando el entorno no tenía PostgreSQL, el contrato me dijo qué parte quedaba sin verificar de verdad (el EXCLUDE en DB viva, en ambas corridas) en vez de fingir que estaba probado. Un prompt suelto jamás me habría dado ese límite con honestidad.

## Qué partes de la fundación valieron más (y cuál menos)

Lo que más valor me dio fue Discovery, porque decidió el MVP con evidencia: qué entra (agenda anti-solape, reserva 24/7, WhatsApp, seña por Mercado Pago) y qué queda afuera (ARCA nativa, validación de obras sociales en tiempo real, IA diagnóstica). Sin eso, yo habría querido meter todo. Lo segundo más valioso fue la KB con las reglas RN-XX, porque es el contrato que va a usar cada change después; ya no discuto dos veces si un turno puede solaparse.

Lo que menos valor me dio fue el registry de skills. No es que esté mal, es que es mecánico: solo indexa las ocho skills instaladas para que el orquestador las resuelva. Útil, pero no me enseñó nada del dominio.

## Cierre

El trabajo está completo de punta a punta: Discovery auditado con informe y PDF, KB de doce archivos, roadmap de quince changes en ocho fases, ocho skills instaladas, reglas del proyecto en AGENTS.md/CLAUDE.md y el primer change (crear-turno-sin-solapamientos) especificado, implementado con TDD, verificado y archivado — y reimplementado en Python (FastAPI + SQLAlchemy + Pydantic + Alembic, 104/104 en verde) cuando el stack obligatorio lo exigió, sin tocar el spec. Si tuviera que quedarme con una sola lección, es esta: corregir temprano es barato, corregir tarde es rehacer. Cada "Ajustar" me costó minutos; cada cosa que se me escapó me costó un commit entero.
