# **Documento de Arquitectura y Decisiones Técnicas — DocSpace**

## **1\. Stack Tecnológico y Justificación**

| Componente | Elección | Justificación |
| :---- | :---- | :---- |
| **Backend** | Python 3.11 \+ Django REST Framework (DRF) | ORM, migraciones y protección contra inyección SQL integradas. |
| **Base de datos** | PostgreSQL | Soporte nativo de UUID, JSONB y bloqueos de fila. |
| **Autenticación** | JWT (SimpleJWT) | Tokens sin estado; desacopla frontend y backend. |
| **Documentación** | drf-spectacular (Swagger/OpenAPI 3\) | OpenAPI generado desde el código; nunca se desincroniza. |
| **Pruebas** | pytest \+ pytest-django | Fixtures reutilizables para escenarios de permisos. |
| **Frontend** | React \+ Vite \+ TypeScript | Compilación rápida y tipado que previene errores. |
| **Estado del servidor** | TanStack Query (React Query) | Caché y estados de carga sin Redux. |
| **Componentes UI** | Mantine | Componentes responsivos y accesibles listos. |
| **Entorno** | Docker \+ Docker Compose | Un solo comando levanta BD, backend y frontend. |
| **Tiempo real (Fase 2)** | Django Channels \+ Daphne | WebSockets integrados en Django: reutilizan modelos, servicios y permisos existentes. Daphne en `INSTALLED_APPS` permite que `runserver` sirva ASGI sin cambiar el comando de arranque. |
| **Estado compartido (Fase 2)** | Redis 7 | Channel layer entre procesos y estado efímero con expiración (turno, presencia, borradores). Nada vive en memoria del proceso. |

## 

## **2\. Estructura del Proyecto**

```
docspace/
├── backend/
│   ├── config/
│   │   ├── settings.py              # Configuración (incluye Channels y Redis)
│   │   ├── urls.py                  # Rutas de la API REST
│   │   ├── asgi.py                  # HTTP + WebSocket (Fase 2)
│   │   └── wsgi.py
│   ├── accounts/                    # Usuarios y autenticación JWT
│   ├── workspaces/                  # Espacios de trabajo y membresías
│   ├── documents/
│   │   ├── models.py                # Documento, VersionDocumento (inmutable), PermisoDocumento
│   │   ├── services.py              # Reglas de negocio y ÚNICA fuente de permisos
│   │   ├── views.py                 # Vistas REST delgadas
│   │   ├── serializers.py
│   │   ├── consumers.py             # Canal WebSocket por documento (Fase 2)
│   │   ├── routing.py               # Rutas WebSocket (Fase 2)
│   │   ├── middleware_jwt.py        # JWT por subprotocolo (Fase 2)
│   │   ├── estado_vivo.py           # Turno, presencia y borrador en Redis (Fase 2)
│   │   ├── management/commands/
│   │   │   └── seed_demo.py         # Datos y usuarios demo
│   │   ├── tests.py                 # Pruebas de la Fase 1
│   │   ├── test_control_optimista.py  # Pruebas de la Fase 2
│   │   └── test_tiempo_real.py        # Pruebas de la Fase 2
│   ├── audit/                       # Bitácora de auditoría (services.py: registrar_evento)
│   ├── conftest.py                  # Fixture de pruebas: Redis aislado (base 15)
│   ├── pytest.ini
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── cliente.ts           # Cliente HTTP con el JWT
│   │   │   ├── tipos.ts             # Tipos compartidos y jerarquía de niveles
│   │   │   └── tiempoReal.ts        # Hook useDocumentoEnVivo (Fase 2)
│   │   ├── components/              # Historial, comparación, acceso, panel del Gestor,
│   │   │                            # PresenciaDocumento y AvisoTurno (Fase 2)
│   │   ├── pages/                   # Login, registro, lista de documentos y editor
│   │   ├── App.tsx
│   │   └── main.tsx
│   └── Dockerfile
├── docs/
│   ├── ARQUITECTURA.md              # Este documento
│   └── diagrama-er.png              # Modelo de datos
├── docker-compose.yml               # db, redis, backend y frontend
├── CLAUDE.md                        # Reglas de arquitectura para el agente (Fase 2)
├── PROCESO-AGENTES.md               # Proceso de desarrollo con agentes de IA (Fase 2)
└── README.md                        # Instalación, uso, protocolo y limitaciones
```

**Capa de Servicios:** Dentro de cada aplicación del backend, la lógica de negocio compleja (crear versiones, validar permisos, registrar auditoría) se aísla en archivos services.py. Las vistas (controllers) actúan únicamente como puntos de entrada que reciben la petición y devuelven la respuesta HTTP. En la Fase 2, el consumer WebSocket sigue la misma regla: es delgado y delega en `documents/services.py`. Las pruebas viven dentro de cada aplicación (`tests.py` y `test_*.py`), no en una carpeta aparte.

## **3\. Aislamiento entre Espacios de Trabajo (Multi-Tenant)**

* **Filtrado en el origen:** Ninguna consulta a la base de datos devuelve documentos de forma global. El QuerySet base siempre se filtra explícitamente evaluando los espacios donde el usuario posee un registro en la tabla MIEMBRO\_ESPACIO.  
* **Membresía automática:** Al crear un espacio de trabajo, el Gestor creador queda registrado automáticamente como miembro de dicho espacio.  
* **Respuestas 404 Not Found:** Si un usuario intenta consultar o manipular un recurso perteneciente a un espacio al que no pertenece, la API responde estrictamente con un código 404 Not Found en lugar de un 403 Forbidden. Esto evita confirmar la existencia del recurso y previene fugas de información.  
* **UUIDs y validación en servidor:** dificultan la enumeración, pero la seguridad real es la validación de membresía. Hay pruebas que lo verifican esperando 404\.

## **4\. Resolución y Aplicación de Permisos**

1. **Autenticación:** Se valida el token JWT. Si es inválido o ha expirado, se retorna 401 Unauthorized.  
2. **Alcance del Espacio:** Se verifica si el usuario pertenece al espacio de trabajo al que pertenece el documento. Si no forma parte, el servidor responde con 404 Not Found.  
3. **Cálculo del Permiso Efectivo:**  
   * Si el usuario es el Gestor creador del espacio, obtiene nivel ADMINISTRACION de forma automática. (Un Gestor invitado a otro espacio se trata como cualquier miembro.)  
   * Para el resto de usuarios, el sistema consulta la tabla PERMISO\_DOCUMENTO. Si no existe un registro explícito de permiso, el documento se oculta devolviendo 404 Not Found.  
4. **Validación de Jerarquía:** Los permisos son estrictamente jerárquicos (LECTURA \< EDICION \< ADMINISTRACION). Si el usuario intenta ejecutar una acción que supera su nivel efectivo, el sistema devuelve 403 Forbidden.  
5. **Delegación Restringida:** Un usuario con nivel ADMINISTRACION sobre un documento puede otorgar o modificar permisos, pero únicamente a usuarios que ya sean miembros de ese mismo espacio de trabajo, previniendo rupturas en el aislamiento multi-tenant.  
6. **Prevalencia del Gestor:** El Gestor del espacio posee autoridad absoluta; puede revocar o modificar cualquier nivel de permiso delegado (incluso el de ADMINISTRACION asignado a un colaborador).

## **5\. Historial de Versiones y Auditoría**

* **Guardado y Concurrencia:** Cada guardado crea una versión nueva. El número se calcula con select\_for\_update, respaldado por UNIQUE (documento\_id, numero\_version).  
* **Inmutabilidad:** El historial de versiones es inmutable. No existen endpoints en la API para editar o eliminar versiones pasadas; además, el modelo impide modificar o eliminar una versión ya registrada.  
* **Restauración:** Crea una nueva versión con el contenido de la elegida; el historial no se toca. Requiere ADMINISTRACION.  
* **Borrado Lógico (Soft Delete):** La eliminación de un documento se maneja mediante el campo eliminado\_en, preservando intactos el historial de versiones y las bitácoras de auditoría asociadas. Requiere ADMINISTRACION.  
* **Bitácora de Auditoría y Privacidad:** La tabla BITACORA\_AUDITORIA registra de forma transaccional quién, qué, cuándo y sobre qué recurso se ejecutó una acción crítica. En cuanto a la consulta:  
  * El Gestor tiene visibilidad completa de la bitácora de su espacio de trabajo.  
  * El Colaborador solo puede consultar la trazabilidad asociada estrictamente a los documentos sobre los cuales posee acceso autorizado.

## **6\. Suposiciones y Decisiones de Negocio**

* Solo los usuarios con cuenta tipo Gestor pueden crear espacios de trabajo. Solo el Gestor dueño del espacio puede crear documentos; al crear un documento, se genera automáticamente su versión inicial (numero\_version \= 1).  
* Los usuarios registrados con cuenta tipo Colaborador ingresan inicialmente sin espacios asignados, quedando a la espera de ser incorporados mediante invitación directa del Gestor. Un usuario puede pertenecer a múltiples espacios de trabajo simultáneamente.  
* Las invitaciones y altas de miembros se realizan asociando cuentas de usuario existentes mediante su correo electrónico, o mediante la creación directa de colaboradores por parte del Gestor dentro de su espacio.

## **7\. Aclaraciones confirmadas con el equipo de selección

* No existen límites de espacios ni de usuarios por espacio.
* Un usuario puede pertenecer a varios espacios (tabla MIEMBRO_ESPACIO).
* El Gestor tiene control completo y puede revocar cualquier permiso delegado.

## 8. Colaboración en tiempo real (Fase 2)

### 8.1 Principios

* **Una sola fuente de permisos.** El canal en tiempo real no tiene reglas propias: llama a `documentos_visibles`, `obtener_nivel` y `tiene_nivel` de `documents/services.py`, igual que las vistas REST. Se verifica al conectar y **en cada mensaje**.
* **Mismo aislamiento que REST.** Un documento ajeno, eliminado o sin acceso cierra la conexión con **4404** (equivalente al 404); sin sesión válida, **4401**. Sin el nivel suficiente para un mensaje concreto se responde `error 403` sin cerrar: un lector sigue recibiendo cambios, pero lo que emite se rechaza y nunca se retransmite.
* **Las versiones siguen siendo inmutables** y se crean siempre con `guardar_version()`. La edición en vivo **no** crea versiones: se crea una al terminar el turno.
* **Nunca perder datos en silencio.** Cada camino en que un texto podría perderse (conflicto, turno vencido, caída, permiso revocado) termina en una versión, en la bitácora o en un aviso visible.

### 8.2 Piezas

| Archivo | Responsabilidad |
| :---- | :---- |
| `config/asgi.py` | `ProtocolTypeRouter`: HTTP a Django; WebSocket a `AllowedHostsOriginValidator` → middleware JWT → rutas. |
| `documents/middleware_jwt.py` | Identifica al usuario con el JWT del subprotocolo (`AccessToken` de SimpleJWT: rechaza tokens inválidos, vencidos y refresh tokens). No decide permisos. |
| `documents/consumers.py` | Consumer delgado (equivale a una vista): valida, delega en servicios y difunde al grupo del documento. |
| `documents/services.py` | Reglas de negocio: presencia, turno, edición, guardado al terminar el turno, conflictos y aviso desde REST. |
| `documents/estado_vivo.py` | Solo Redis: claves, TTL y scripts Lua atómicos. Sin lógica de permisos. |
| `frontend/src/api/tiempoReal.ts` | Hook `useDocumentoEnVivo`: conexión, latido, reconexión con espera exponencial. |
| `frontend/src/pages/DocumentoPage.tsx`, `components/AvisoTurno.tsx`, `components/PresenciaDocumento.tsx` | Editor, turno, avisos de versión y de conflicto, presencia. |

### 8.3 Autenticación del WebSocket

| Opción | Riesgo | Decisión |
| :---- | :---- | :---- |
| Token en la query string (`?token=`) | Queda en la URL: logs de acceso del servidor y de proxies. | Descartada. |
| Token en el primer mensaje | Hay una ventana con el socket aceptado sin autenticar, y el permiso se conoce después del `accept`. | Descartada. |
| **Token como subprotocolo** (`["access_token", jwt]`) | Uso no estándar de `Sec-WebSocket-Protocol`. El servidor debe devolver solo `access_token`, nunca el token. | **Elegida**: autentica y comprueba permisos **antes** del `accept` y no deja el token en URLs ni logs de acceso. |

Si se rechaza la conexión, el servidor la acepta solo para cerrarla con un código propio (4401/4404), sin enviar ningún dato, porque un rechazo en el handshake llega al navegador como un `1006` genérico. El `exp` del token se vuelve a comprobar en cada mensaje.

### 8.4 Estado en Redis

| Clave | Contenido | Expiración |
| :---- | :---- | :---- |
| `doc:{id}:presencia` | Sorted set: `"{usuario_id}\|{canal}"` → último latido | Entradas de más de 30 s se purgan al leer; la clave expira si nadie late. |
| `doc:{id}:turno` | `{usuario_id, nombre, canal, version_base}` | 30 s, renovado **solo** por `editar`. |
| `doc:{id}:turno:anunciado` | Marcador del último turno anunciado | 24 h. Permite detectar que el turno venció. |
| `doc:{id}:borrador` | Datos del turno \+ `contenido` en vivo | 24 h. Red de seguridad ante vencimiento o caída. |

Todas las operaciones del turno (tomar, editar, liberar, detectar vencimiento, borrar borrador) son **scripts Lua atómicos**, correctos aunque varios procesos atiendan el mismo documento.

### 8.5 Turno de edición y versiones

1. **Pedir turno** (requiere EDICION): `SET NX EX 30`. Un segundo editor recibe `turno_ocupado` con el nombre de quien edita. La `version_base` del turno es la última versión en ese momento.
2. **Editar**: el script renueva el turno y escribe el borrador en un solo paso, y el contenido se retransmite a los demás. Orden de validación: permiso (403) → formato (400) → tamaño `EDITAR_MAX_CARACTERES` (413) → turno (409).
3. **El latido mantiene únicamente la presencia** y nunca renueva el turno. Si el dueño deja la pestaña abierta sin escribir, Redis expira el turno a los 30 s por sí solo, sin depender del cliente.
4. **Detectar el vencimiento.** Redis borra la clave sin avisar, así que el primer mensaje que llega de cualquier conexión del documento (o una conexión nueva) consume el marcador de forma atómica, guarda el borrador y difunde `turno: null`.
5. **Terminar el turno** crea **una** versión con `guardar_version(..., version_base=N)`:
   * con el botón Guardar o tras 20 s sin escribir (temporizador del cliente, que solo adelanta el guardado);
   * al desconectarse el dueño;
   * al detectarse el vencimiento o un borrador huérfano tras una caída.
   Si el borrador es igual a la última versión, no se crea ninguna.

### 8.6 Control optimista y conflictos

`guardar_version()` recibe un `version_base` opcional. Dentro del `select_for_update`, si no coincide con la última versión, lanza `ConflictoVersion` sin crear nada y registra `CONFLICTO_VERSION`. Sin `version_base` se comporta como en la Fase 1.

| Caso | Qué pasa |
| :---- | :---- |
| REST `/save/` con base vieja | **409** con `version_actual` y `contenido_actual`. |
| Guardado **manual** en conflicto | El editor **conserva turno y borrador** y ve ambos textos. Decide: guardar encima confirmando la versión que vio (`version_base: N`) o descartar (`DESCARTAR_BORRADOR`). |
| Guardado **automático** en conflicto (desconexión, vencimiento, huérfano) | No hay a quién preguntar: no se crea una versión que tape la otra. El texto completo queda en la bitácora (`BORRADOR_EN_CONFLICTO`) y se avisa al grupo. |
| Autor sin permiso al guardar | Se vuelve a comprobar con `tiene_nivel`: no se guarda y se registra `BORRADOR_DESCARTADO` (sin el contenido). |

En el frontend, si quien tiene el turno recibe `version_guardada`, su texto **no se reemplaza**: ve «Alguien guardó la versión N» y el conflicto se resuelve al guardar. Al tomar el turno, el editor vuelve a pedir el documento, así que nunca edita sobre una versión anterior a la base del turno.

### 8.7 Avisos desde REST

`/save/` y `/restore/` avisan al grupo con el mismo mensaje `version_guardada`, y el frontend invalida las consultas de documento e historial sin recargar la página. El aviso sale **desde las vistas y no desde `guardar_version()`**: el canal WebSocket ya avisa cuando guarda, y `guardar_version()` también la usan el `seed_demo` y la creación del documento. Se envía con `transaction.on_commit`, y si Redis falla el guardado **no** falla: la versión ya existe, así que se registra un `logger.warning`.

### 8.8 Detalle operativo: `socket_timeout` de Redis

`channels-redis` espera mensajes con una lectura bloqueante `BZPOPMIN` de 5 s, y `redis-py 8` usa `socket_timeout = 5 s` por defecto. Con ambos en 5 s, una conexión sin mensajes durante ~5 s moría con `redis.exceptions.TimeoutError`. Por eso `CHANNEL_LAYERS` fija `socket_timeout: 15`. La prueba `test_conexion_inactiva_mas_de_5_segundos_sigue_abierta_y_recibe` cubre este caso y falla sin el ajuste.

### 8.9 Nuevos eventos de bitácora

| Acción | Cuándo |
| :---- | :---- |
| `CONFLICTO_VERSION` | Un guardado con `version_base` vieja (REST o WebSocket). |
| `BORRADOR_EN_CONFLICTO` | Un guardado automático en conflicto; incluye el texto completo para poder recuperarlo. |
| `BORRADOR_DESCARTADO` | El autor perdió el permiso de edición antes del guardado automático. |
| `DESCARTAR_BORRADOR` | El editor descartó su texto a propósito tras un conflicto. |

Las limitaciones conocidas y las mejoras futuras están en el [README](../README.md#limitaciones-conocidas).