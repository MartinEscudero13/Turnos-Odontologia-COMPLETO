# Reflexión escrita — fundación de Turnos-Odontologia

*Trabajo individual de Martin Escudero. Todas las etapas de la fundación las hice yo, solo, conversando con el agente.*

## Lo que salió mal (o a medias) y cómo me di cuenta

Lo más concreto: el informe de Discovery quedó primero en `discovery/` en vez de `docs/discovery/`, y tres referencias internas apuntaban a la ruta vieja. No lo noté yo en el momento; lo detectó la auditoría contra el PDF, y se corrigió en el commit `9d50fe7`. Me dejó una lección simple: yo daba por sentado que los archivos estaban donde yo creía, y no los verificaba. Desde entonces pido el `git status` y las rutas reales antes de dar algo por hecho.

Lo segundo: los precios de seis competidores no estaban publicados en ningún lado. La tentación era poner un número aproximado "para completar la tabla", pero los dejé marcados como "No evidenciado". Prefiero un hueco honesto a un dato inventado, porque un precio falso después se convierte en una decisión falsa (por ejemplo, posicionar nuestro plan contra un número que no existe).

Y lo tercero: en el gate final del checklist se corrigió una contradicción que venía arrastrándose — había quedado escrita una restricción de "sin restricciones duras" que chocaba con lo ya decidido. El gate la descartó. Era un detalle chico, pero muestra que los documentos largos acumulan inconsistencias si nadie los relee de punta a punta.

## Dónde usé "Ajustar" y por qué importó

Usé Ajustar (revisar y corregir en vez de aceptar automático) en varios puntos: el gate de Discovery (dije que sí, pero con brief ampliado), las rondas de Q&A, el gate final del checklist, el pre-gate del roadmap (cuando dije "seguí"), el install gate (cuando dije "todas") y la auditoría contra el PDF que terminó reordenando archivos.

Si en esos puntos hubiera puesto Continuar automático, creo que habrían pasado dos cosas feas: la knowledge base se habría generado sobre insumos guardados en la ubicación equivocada, y el informe habría quedado sin el formato del PDF. O sea, documentos "verdes" pero apoyados en algo roto. Ajustar me costó unos minutos cada vez y me ahorró rehacer etapas enteras.

## Spec vs. prompt suelto

La Etapa 6 (Apply) todavía no la ejecuté al momento de escribir esto, así que no puedo contar experiencia propia implementando. Lo que sí puedo decir es la expectativa concreta que me deja la fundación: cuando implemente el change crear-turno-sin-solapamientos voy a tener un contrato verificable con tres escenarios (solape de profesional, solape de sillón y sobreturno explícito auditado), en vez de un prompt suelto tipo "haceme la agenda". La diferencia es que con el contrato sé exactamente cuándo terminé y cómo comprobarlo; con el prompt suelto, termino cuando "parece que anda".

## Qué partes de la fundación valieron más (y cuál menos)

Lo que más valor me dio fue Discovery, porque decidió el MVP con evidencia: qué entra (agenda anti-solape, reserva 24/7, WhatsApp, seña por Mercado Pago) y qué queda afuera (ARCA nativa, validación de obras sociales en tiempo real, IA diagnóstica). Sin eso, yo habría querido meter todo. Lo segundo más valioso fue la KB con las reglas RN-XX, porque es el contrato que va a usar cada change después; ya no discuto dos veces si un turno puede solaparse.

Lo que menos valor me dio fue el registry de skills. No es que esté mal, es que es mecánico: solo indexa las ocho skills instaladas para que el orquestador las resuelva. Útil, pero no me enseñó nada del dominio.

## Cierre

La fundación está completa: Discovery auditado, KB de doce archivos, roadmap de quince changes en ocho fases, ocho skills instaladas y las reglas del proyecto en AGENTS.md/CLAUDE.md. El siguiente paso es la Etapa 6, empezando por el change crear-turno-sin-solapamientos, que es el corazón del sistema.
