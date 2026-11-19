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


### 8. Paso 6 — Edición en vivo y guardado
- **Requisito agregado por mí (no estaba en el plan):** límite de tamaño para `editar` (200 000 caracteres, configurable): un mensaje que lo supera recibe 413, no se retransmite ni se guarda. Evita que un editor sature Redis o a los demás clientes.
- **Decisión validada:** el agente propuso, y yo aprobé, la estrategia ante conflictos al guardar: en el guardado manual el editor conserva turno y borrador y decide (reintentar confirmando la versión que vio, o descartar); en el guardado automático no se sobrescribe la otra versión y el texto se conserva completo en la bitácora (`BORRADOR_EN_CONFLICTO`). Si el autor perdió el permiso, no se guarda nada y la bitácora no incluye el texto. Descarté la propuesta de limitar el tamaño del frame en Daphne (queda como mejora futura).
- **Bug detectado por mí en la revisión del diff:** al pasar de 2 a 3 claves en Redis, `tomar_turno` quedó con `numkeys=2`, lo que habría desplazado los argumentos y roto todo `pedir_turno`. El agente lo confirmó, lo corrigió y revisó el resto de llamadas.
- **Puntos que verifiqué:** que el borrador se guarde en la base de datos antes de liberar el turno; que un conflicto manual no libere el turno; que el editor no reciba su propio cambio (sin eco).
- **Depuración con evidencia:** la prueba de "sin eco" falló. El agente no asumió la causa: la investigó (era un aviso de presencia), reescribió la prueba para comprobar exactamente la propiedad (ningún mensaje `cambio` al editor) y demostró con un mutante (sin el filtro de origen) que la nueva prueba detecta un eco real. Restauró el archivo y lo verificó con `cmp`.
- **Verificación:** 57 pruebas pasan, incluidas las 10 de la Fase 1.
- **Limitación conocida:** recuperar un `BORRADOR_EN_CONFLICTO` es manual (desde la API de auditoría); no tiene interfaz.