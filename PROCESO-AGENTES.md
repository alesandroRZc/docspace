# Proceso con agentes — Fase 2


## Herramientas y forma de trabajo

| Herramienta | Uso |
|---|---|
| **Claude Code** (CLI, modelo Claude Opus 5.5) | Agente de desarrollo: exploró el código, propuso el plan y escribió los cambios de backend, frontend y pruebas. |
| **Claude** (chat) | Asistente de apoyo: me ayudó a redactar CLAUDE.md y los prompts, y a revisar los diffs del agente antes de aprobarlos. Todo lo que entró al repositorio pasó por mi revisión. |

**Método:**
- Antes de que el agente escribiera código, fijé las reglas de arquitectura en `CLAUDE.md` (primer commit de la rama `fase-2`).
- Plan primero: el agente trabajó en *plan mode* hasta que aprobé un plan de 9 pasos.
- Aprobación manual de cada edición y comando. Nunca usé el modo automático.
- Un commit por paso, hecho por mí después de revisar y correr las pruebas.

## Bitácora

### 1. Verificación de comprensión (plan mode)
- **Prompt:** pedí que leyera CLAUDE.md y explicara permisos, guardado de versiones y qué tocaría, sin cambiar nada.
- **Acertó:** orden de `obtener_nivel`, 404/403, `select_for_update`; detectó que no había control optimista.
- **Errores detectados:** olvidó el indicador de presencia; propuso cambiar el servidor ASGI en Compose sin necesidad; no definió dónde vive el turno de edición ni cuándo se crean versiones.
- **Corrección:** segundo prompt con decisiones explícitas (ver punto 2).

### 2. Plan de implementación (plan mode)
- **Prompt:** le di 5 decisiones (presencia obligatoria, daphne en INSTALLED_APPS, estado en Redis con expiración, versión al liberar el turno y no por tecla, opciones para el JWT) y pedí un plan por pasos con pruebas.
- **Aceptado:** plan de 9 pasos con prueba por paso; JWT por subprotocolo (no queda en URLs ni logs); evento nuevo `CONFLICTO_VERSION` en la bitácora.
- **Error detectado:** el turno se renovaba con el latido, así que una pestaña abierta sin escribir retendría el turno para siempre, dependiendo del cliente.
- **Corrección:** el turno solo se renueva con ediciones y su vencimiento lo garantiza el servidor (TTL en Redis). El agente ajustó el plan y la prueba correspondiente.


### 3. Paso 1 — Infraestructura (Channels, Daphne, Redis)
- **Aprobé cada edición revisando el diff.** Aceptados tal cual: dependencias con versión fija, `daphne` primero en `INSTALLED_APPS`, `ProtocolTypeRouter` en `asgi.py` (respetando que `get_asgi_application()` se llame antes de importar Channels), servicio `redis` con healthcheck y sin puerto expuesto.
- **Punto que vigilé:** que dentro de Compose `REDIS_URL` usara el host `redis` y no `localhost` (el mismo caso de `POSTGRES_HOST: db`). Lo hizo bien.
- **Verificación:** 11 pruebas pasan (las 10 de la Fase 1 + la del channel layer). Comprobé a mano que el login y los documentos siguen funcionando en el navegador.


### 4. Paso 2 — Control optimista (REST)
- **Aceptado:** `ConflictoVersion` y `version_base` opcional en `guardar_version`, con la comparación dentro del `select_for_update` (evita la condición de carrera); el conflicto se registra fuera de la transacción para que el `raise` no lo revierta; 409 con `detail`, que el frontend ya sabe mostrar.
- **Desviación detectada:** modificó `DocumentoPage.tsx` aunque no estaba en el plan. Le pedí la justificación: sin `version_base` desde la interfaz, el 409 solo existiría en las pruebas. Además reportó por su cuenta un efecto secundario (falso conflicto con doble clic en Guardar, que se resuelve en el Paso 8).
- **Decisión:** mantuve el cambio (es preferible un aviso de más que perder datos en silencio) y agregué la regla "no modificar archivos fuera del plan sin avisar" a CLAUDE.md.
- **Verificación:** 16 pruebas pasan (10 de la Fase 1 + 1 del Paso 1 + 5 de control optimista).


### 5. Paso 3 — WebSocket autenticado
- **Aceptado:** middleware JWT por subprotocolo (valida firma, vencimiento, tipo de token y `is_active`; nunca registra el token); consumer que reutiliza `documentos_visibles` + `obtener_nivel` (mismo patrón que REST); validación de permiso y vencimiento en cada mensaje; `AllowedHostsOriginValidator`; acepta y cierra para entregar 4401/4404 al navegador.
- **Modificado a mano:** detecté que no había pruebas para el validador de origen ni para el uso de un refresh token. Pedí ambas, diseñadas para fallar si se quita la protección correspondiente.
- **Verificación por mutación:** pedí al agente quitar temporalmente `AllowedHostsOriginValidator`; la prueba falló (`assert True is False`: un origen ajeno logró conectarse). Restauró el archivo y lo verificó byte a byte con `cmp`; yo lo confirmé con `git diff`.
- **Limitación conocida:** el usuario se carga al conectar; si una cuenta se desactiva estando conectada, el socket sigue activo hasta que vence el token (máx. 60 min). Los permisos sí se revalidan en cada mensaje.
- **Verificado a mano:** desde la consola del navegador abrí el WebSocket con mi token y recibí `{"tipo": "conectado", "nivel": "ADMINISTRACION"}`.


### 6. Paso 4 — Presencia
- **Aceptado:** módulo `estado_vivo.py` solo con operaciones de Redis (sin permisos); sorted set con una entrada por pestaña y lista de usuarios únicos; purga de pestañas que dejaron de latir; el latido solo mantiene la presencia (respetó la corrección del plan); los demás conectados solo ven `id` y `nombre`. Las pruebas usan la base 15 de Redis con `flushdb`, sin tocar los datos de desarrollo.
- **Error del agente (detectado y rechazado):** intentó agregar las pruebas con `cat >>` desde Bash, evitando la revisión del diff. Además, el código que proponía tenía una prueba sin encabezado (`@pytest.mark.django_db` y `def`), lo que habría impedido ejecutar todo el archivo de pruebas. Rechacé el comando, pedí usar la herramienta de edición y corregir la prueba. Agregué la regla correspondiente a CLAUDE.md.
- **Sospecha verificada:** pregunté si la función `_miembro()` estaba definida porque no aparecía en la vista del diff; el agente confirmó que sí existía (falsa alarma por la vista parcial).
- **Desviación avisada:** la prueba de purga simula un latido antiguo en lugar de reducir el TTL por configuración.
- **Verificación:** 32 pruebas pasan, incluidas las 10 de la Fase 1 sin cambios.


### 7. Paso 5 — Turno de edición
- **Decisiones avisadas antes de escribir** (aplicando la regla de CLAUDE.md): `editar` mínimo en este paso; un marcador `turno:anunciado` consumido con un script Lua atómico para detectar el vencimiento (Redis no avisa cuando expira una clave); extraer `nivel_alcanza()` de `tiene_nivel()` sin cambiar su comportamiento, para que el canal no duplique la comparación de niveles.
- **Aceptado:** turno en Redis con 4 scripts Lua atómicos (tomar con `SET NX`, renovar y liberar solo si el canal es el dueño, detectar vencimiento con `GETDEL` para avisar una sola vez); reglas en `services.py`; el canal interno nunca se expone a los demás.
- **Punto que verifiqué:** que la detección de vencimiento corra antes de procesar `pedir_turno`, para que un turno vencido siempre se anuncie (y en el Paso 6 su borrador se guarde) antes de entregarlo a otro editor.
- **Error del agente:** una prueba leía un mensaje equivocado (no consumía su propio aviso de turno concedido). Lo detectó al correr las pruebas; verifiqué que la corrección no debilitara las aserciones.
- **Verificación por mutación (iniciativa del agente):** hizo que el latido renovara el turno; la prueba `test_un_latido_sin_ediciones_no_renueva_el_turno` falló. Restauró el archivo y lo verificó con `cmp`.
- **Trade-off:** tres pruebas esperan la expiración real de Redis (1-2 s), así que la suite tarda ~55 s, a cambio de probar la expiración real y no un reloj simulado.
- **Verificación:** 43 pruebas pasan.
- **Incidente detectado al probar a mano:** el login fallaba. Los logs mostraban un `ImportError`: el servidor de desarrollo se había recargado a mitad de la edición del Paso 6 (con `services.py` ya cambiado y `consumers.py` todavía no) y quedó caído. Las 57 pruebas pasaban porque `pytest` arranca un proceso nuevo con los archivos ya completos. Lo resolví reiniciando el backend y agregué a CLAUDE.md la regla de verificar los logs del servidor al terminar cada paso. **Lección:** las pruebas automáticas no reemplazan comprobar la aplicación en ejecución.


### 8. Paso 6 — Edición en vivo y guardado
- **Requisito agregado por mí (no estaba en el plan):** límite de tamaño para `editar` (200 000 caracteres, configurable): un mensaje que lo supera recibe 413, no se retransmite ni se guarda. Evita que un editor sature Redis o a los demás clientes.
- **Decisión validada:** el agente propuso, y yo aprobé, la estrategia ante conflictos al guardar: en el guardado manual el editor conserva turno y borrador y decide (reintentar confirmando la versión que vio, o descartar); en el guardado automático no se sobrescribe la otra versión y el texto se conserva completo en la bitácora (`BORRADOR_EN_CONFLICTO`). Si el autor perdió el permiso, no se guarda nada y la bitácora no incluye el texto. Descarté la propuesta de limitar el tamaño del frame en Daphne (queda como mejora futura).
- **Bug detectado por mí en la revisión del diff:** al pasar de 2 a 3 claves en Redis, `tomar_turno` quedó con `numkeys=2`, lo que habría desplazado los argumentos y roto todo `pedir_turno`. El agente lo confirmó, lo corrigió y revisó el resto de llamadas.
- **Puntos que verifiqué:** que el borrador se guarde en la base de datos antes de liberar el turno; que un conflicto manual no libere el turno; que el editor no reciba su propio cambio (sin eco).
- **Depuración con evidencia:** la prueba de "sin eco" falló. El agente no asumió la causa: la investigó (era un aviso de presencia), reescribió la prueba para comprobar exactamente la propiedad (ningún mensaje `cambio` al editor) y demostró con un mutante (sin el filtro de origen) que la nueva prueba detecta un eco real. Restauró el archivo y lo verificó con `cmp`.
- **Verificación:** 57 pruebas pasan, incluidas las 10 de la Fase 1.
- **Limitación conocida:** recuperar un `BORRADOR_EN_CONFLICTO` es manual (desde la API de auditoría); no tiene interfaz.


### 9. Paso 7 — Frontend: conexión y presencia
- **Aceptado:** hook `useDocumentoEnVivo` (JWT por subprotocolo, nunca en la URL; URL `ws`/`wss` derivada de `VITE_API_URL`; latido cada 10 s; reconexión con espera exponencial, sin reintentar ante 4401/4404) y componente de presencia con avatares.
- **Línea base:** antes de tocar nada, el agente corrió lint y build y reportó un error de lint heredado de la Fase 1 (`react-hooks/set-state-in-effect` en `DocumentoPage.tsx`); acordamos no introducir errores nuevos y resolverlo en el Paso 8.
- **Verificado a mano con dos navegadores:** el gestor y un usuario de solo lectura se ven mutuamente; al salir, el usuario desaparece de la lista; el de solo lectura no ve controles de edición. También vi la reconexión automática cuando reinicié el backend.
- **Incidente 1 (servidor caído):** el login fallaba. Los logs mostraban un `ImportError`: el servidor de desarrollo se recargó a mitad de la edición del Paso 6 y quedó caído, mientras las 57 pruebas pasaban porque `pytest` arranca un proceso nuevo. Lo reinicié y agregué a CLAUDE.md la regla de revisar los logs del servidor al terminar cada paso. **Lección:** las pruebas automáticas no reemplazan comprobar la aplicación en ejecución.
- **Incidente 2 (bug detectado al probar a mano):** vi reconexiones constantes. Con la regla nueva, el agente encontró un `TimeoutError` de Redis cada ~5 s: el `socket_timeout` por defecto de redis-py 8 (5 s) chocaba con la espera bloqueante de 5 s de channels-redis. Venía desde el Paso 3 y ninguna prueba lo detectaba porque ninguna dejaba una conexión inactiva más de 5 s. Se corrigió en un commit aparte (`fix:`) siguiendo el orden prueba primero: la prueba de regresión falló sin el arreglo con el mismo error de los logs y pasó con él (58/58). Confirmé en los logs y en el navegador que la conexión ya no se corta.


### 10. Paso 8 — Frontend: turno, edición en vivo y conflictos
- **Requisito agregado por mí (detectado probando a mano):** los guardados y restauraciones por REST no avisaban a los demás conectados; había que recargar para ver la versión nueva. Lo agregué al Paso 8. El agente propuso, y yo validé, avisar desde las vistas REST (no desde `guardar_version()`, para evitar avisos duplicados con el canal WebSocket), con `transaction.on_commit` (sin avisos de versiones que se reviertan) y sin hacer fallar el guardado si falla el aviso. Agregué la condición de registrar ese fallo con `logger.warning`. Se cubrió con 5 pruebas (incluida una con Redis caído simulado) y se verificó con mutantes que las pruebas fallan si se quita el aviso. Va en un commit `feat:` del backend aparte.
- **Requisito agregado por mí:** si el usuario tiene el turno, una versión que llega no reemplaza el texto de su editor: se muestra un aviso y el conflicto se resuelve al guardar.
- **Decisiones del agente, avisadas antes de escribir:** el aviso de conflicto como componente dentro de `AvisoTurno.tsx` (para no crear un archivo fuera del plan); una pestaña considera el turno como suyo solo si lo pidió y el usuario coincide (evita que otra pestaña del mismo usuario edite por accidente); el texto pendiente del envío diferido (300 ms) se envía al salir del editor, al guardar y antes de cerrar la pestaña; si se pierde el turno con texto sin enviar, se muestra para copiarlo.
- **Autocorrección del agente:** deshabilitó el botón Editar hasta tener cargado el usuario actual, para evitar quedar con el turno tomado sin que la pestaña lo reconociera como propio.
- **Lint:** desapareció el error heredado de la Fase 1 (`react-hooks/set-state-in-effect`); `npm run lint` queda en 0 problemas.
- **Honestidad del agente:** aclaró que el proyecto no tiene pruebas automáticas de frontend y que solo había verificado con lint y build; el comportamiento debía comprobarse a mano.
- **Verificado a mano con tres navegadores (editor, gestor y lector):** el editor toma el turno y los demás ven "Editando: …" y el texto en vivo; el lector no tiene botón de edición; al guardar, el historial se actualiza en todos sin recargar; el guardado automático tras 20 s de inactividad libera el turno; con el editor escribiendo, una restauración hecha por el gestor muestra el aviso sin borrar su texto, y al guardar aparece el conflicto con ambos textos lado a lado; guardar encima crea la versión nueva y libera el turno.


## Resumen

### Qué acepté tal cual
- La arquitectura del tiempo real: Django Channels con Redis, consumer delgado que reutiliza `documentos_visibles`/`obtener_nivel`, estado efímero en Redis con scripts Lua atómicos, y JWT por subprotocolo.
- El diseño de conflictos: turno de edición más control optimista, guardado manual con decisión del usuario y guardado automático que nunca sobrescribe (el texto queda en la bitácora).
- Las pruebas de mutación que el agente empezó a hacer por iniciativa propia a partir del Paso 5.

### Qué modifiqué o agregué yo
- Indicador de presencia (el agente lo había omitido del plan).
- El turno solo se renueva al editar, nunca con el latido: el vencimiento lo garantiza el servidor.
- Límite de tamaño de 200 000 caracteres para los mensajes `editar` (413).
- Pruebas que faltaban: origen no permitido, uso de un refresh token y conexión inactiva más de 5 s.
- Aviso en vivo al guardar o restaurar por REST, detectado probando a mano.
- No reemplazar el texto de quien está editando cuando llega una versión nueva.
- Registrar con `logger.warning` el fallo del aviso por Redis, en vez de ignorarlo.
- Corrección de la estructura del proyecto en `ARQUITECTURA.md`, que no coincidía con el código.

### Qué descarté
- Token en la query string o en el primer mensaje del WebSocket (riesgos documentados en `ARQUITECTURA.md`, sección 8.3).
- Cambiar el comando de arranque para usar Daphne: bastó con agregarlo a `INSTALLED_APPS`.
- Agregar código con `cat >>` desde Bash, porque evitaba la revisión del diff.
- Fijar `redis<8` para esquivar el timeout: se corrigió la configuración.
- Limitar el tamaño del frame en Daphne: quedó como mejora futura.

## Errores del agente y cómo los detecté

| # | Error | Cómo lo detecté |
|---|---|---|
| 1 | Omitió el indicador de presencia en su análisis inicial | Revisión del análisis (plan mode) |
| 2 | El turno se renovaba con el latido | Revisión del plan |
| 3 | Modificó `DocumentoPage.tsx` fuera del plan sin avisar | Revisión del diff |
| 4 | Intentó agregar pruebas con `cat >>` (sin diff), y una prueba venía sin encabezado | Revisión del comando antes de aprobarlo |
| 5 | `tomar_turno` quedó con `numkeys=2` al pasar a 3 claves en Redis | Revisión del diff |
| 6 | Una prueba leía un mensaje equivocado (no consumía su propio aviso de turno) | Ejecución de las pruebas |
| 7 | La prueba "sin eco" fallaba por un aviso de presencia | Ejecución de las pruebas + investigación con evidencia |
| 8 | El servidor de desarrollo quedó caído tras recargarse a mitad de una edición, con las pruebas en verde | Prueba manual (el login fallaba) + logs |
| 9 | `TimeoutError` de Redis cada ~5 s, presente desde el Paso 3 | Prueba manual (reconexiones visibles) + logs |
| 10 | Guardar o restaurar por REST no avisaba a los demás conectados | Prueba manual con dos navegadores |

## Cómo verifiqué que no se rompió la Fase 1
- **Las 10 pruebas originales nunca se modificaron** y pasaron en cada paso (63 en total al final).
- Los cambios al código de la Fase 1 (`guardar_version`, `tiene_nivel`) fueron opcionales o refactors sin cambio de comportamiento, cubiertos por esas pruebas.
- Después de cada paso de infraestructura comprobé a mano en el navegador el login, los permisos, el historial y la gestión de acceso.
- **Clon limpio desde GitHub:** cloné el repositorio en otra carpeta, seguí el README al pie de la letra y el proyecto levantó con un solo comando, aplicando todas las migraciones desde cero.
- La rama `fase-1` no recibió cambios y está etiquetada como `fase-1-final`.

## Reglas que agregué a CLAUDE.md durante el proceso
1. **No modificar archivos fuera del plan sin avisar** → tras el error 3.
2. **Editar archivos solo con la herramienta de edición, nunca con comandos de shell** → tras el error 4.
3. **Revisar los logs del servidor al terminar cada paso** → tras el error 8. Esta regla permitió encontrar el error 9.

## Lecciones
- **Revisar el plan antes del código** evitó errores de diseño (1 y 2) que habrían sido caros de corregir después.
- **Las pruebas automáticas no bastan:** tres errores importantes (8, 9 y 10) solo aparecieron al usar la aplicación de verdad.
- **Cada error se convirtió en una regla o una prueba**, para que no se repita.

### 11. Valor añadido: sección «Más allá de lo pedido» y prueba del autor

**Qué pedí:** documentar en el README lo que implementamos fuera de los requisitos, indicando dónde verificar cada punto, y que el agente primero comprobara en el código que cada uno existía y si tenía prueba automatizada.

**Qué hizo bien el agente:**
- Revisó los siete puntos antes de escribir y reportó con honestidad que tres no tenían prueba automatizada (pruebas de mutación, reconexión y autor visible). También aclaró que no tenía el PDF y que no podía confirmar qué estaba fuera de los requisitos.
- Antes de enlazar PROCESO-AGENTES.md, verificó que el archivo realmente hablara de las pruebas de mutación. No lo editó y me avisó que la línea 140 decía «63».
- La prueba nueva usa a una segunda usuaria (Ana) para la