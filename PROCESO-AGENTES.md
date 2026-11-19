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