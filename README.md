# DocSpace

Plataforma web de documentos colaborativos con espacios de trabajo aislados, permisos granulares por documento, historial de versiones inmutable y bitácora de auditoría.

Prueba técnica — Desarrollador Full Stack Senior (Python + React) — Avio Trade Group.

## Ramas

| Rama | Contenido |
|---|---|
| `fase-1` | Núcleo del sistema, escrito a mano sin asistentes de IA |
| `fase-2` | Colaboración en tiempo real, desarrollada con agentes de IA (ver `PROCESO-AGENTES.md`) |

## Stack

Python 3.11 · Django 5.2 · Django REST Framework · SimpleJWT · drf-spectacular · PostgreSQL 16 · pytest · Docker Compose · React + Vite + TypeScript (frontend).

Fase 2 (tiempo real): Django Channels · Daphne (servidor ASGI) · Redis 7 (channel layer y estado efímero).

Las decisiones técnicas están justificadas en [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) y el modelo de datos en [`docs/diagrama-er.png`](docs/diagrama-er.png).

## Cómo levantar el proyecto
Requisitos: **Docker Desktop** y **Git**. No hace falta instalar Python ni Node.

```bash
git clone https://github.com/alesandroRZc/docspace.git
cd docspace
git checkout fase-2
cp .env.example .env
docker compose up --build
```
> La evaluación de la Fase 2 se hace en la rama **`fase-2`**. La rama `fase-1` conserva el código escrito a mano y está etiquetada como **`fase-1-final`**.
>
> En Windows con CMD, usar `copy .env.example .env` en lugar de `cp`. (En PowerShell `cp` funciona igual.)

En `fase-2` se levantan **cuatro servicios** (en `fase-1`, los mismos sin `redis`):

| Servicio | Qué hace |
|---|---|
| `db` | PostgreSQL 16 (con healthcheck) |
| `redis` | Redis 7 (con healthcheck): channel layer de WebSocket, turno de edición, presencia y borradores |
| `backend` | Aplica migraciones, carga datos demo y levanta Django con Daphne (HTTP + WebSocket) |
| `frontend` | Servidor de desarrollo de Vite con recarga en vivo |

## URLs

| Recurso | URL |
|---|---|
| Aplicación web | http://localhost:5173 |
| API | http://localhost:8000/api/ |
| Documentación Swagger | http://localhost:8000/api/docs/ |
| WebSocket de un documento | `ws://localhost:8000/ws/documents/{id}/` |

## Usuarios de prueba

Todos con la contraseña **`Demo12345`**.

| Email | Rol | Qué permite demostrar |
|---|---|---|
| `gestor@demo.com` | Gestor del "Espacio Demo" | Control total del espacio y sus documentos |
| `editor@demo.com` | Colaborador con permiso de edición | Puede tomar el turno, editar en vivo y guardar nuevas versiones |
| `lector@demo.com` | Colaborador con permiso de lectura | Ve el documento y los cambios en vivo, pero el servidor rechaza lo que intente guardar o emitir (403) |
| `intruso@demo.com` | Colaborador sin espacio | No ve ningún documento (lista vacía / 404) |

Para usar la API desde Swagger: hacer login en `POST /api/auth/login/`, copiar el token `access` y pegarlo en el botón **Authorize**.

## Pruebas automatizadas

Con el proyecto levantado:

```bash
docker compose exec backend pytest -v
```

Cubren los casos críticos que pide la prueba:

- **Aislamiento entre espacios:** un usuario de otro espacio no puede ver documentos ni eventos de bitácora ajenos.
- **Permisos:** jerarquía Lectura < Edición < Administración, casos negativos y positivos, y ciclo completo vía API (un lector ve pero no puede guardar).
- **Versionado:** cada guardado crea una versión consecutiva, las versiones son inmutables, y cada edición queda registrada en la bitácora.
- **Borrado lógico:** el documento deja de ser visible, pero su historial se conserva.

Las pruebas se validaron con **mutación**: al invertir a propósito la verificación de membresía en `obtener_nivel`, la prueba del caso positivo falla, lo que confirma que detectan errores reales.

En total son **63 pruebas**: las 10 originales de la Fase 1 y 53 de la Fase 2. En la Fase 2 se agregan pruebas de tiempo real (`documents/test_tiempo_real.py`) y de control optimista (`documents/test_control_optimista.py`):

- **Conexión:** sin token, token inválido, vencido o refresh token → cierre 4401; documento ajeno o eliminado → 4404; origen no permitido → rechazado; el token nunca vuelve en la respuesta.
- **Permisos en cada mensaje:** un permiso revocado cierra la conexión en el siguiente mensaje; un lector recibe cambios, pero lo que emite se rechaza y no se retransmite.
- **Presencia:** alta, baja, pestañas duplicadas y purga de conexiones muertas.
- **Turno de edición:** uno a la vez; un latido **no** renueva el turno, una edición sí; el turno vence solo aunque la pestaña siga abierta.
- **Guardado y conflictos:** una versión al liberar (no una por tecla); guardado al desconectar, al vencer y de borradores huérfanos; conflicto manual y automático sin perder el texto; límite de tamaño (413).
- **REST:** `/save/` responde 409 ante una versión base vieja; guardar y restaurar avisan en vivo; si Redis falla, el guardado no falla y queda un warning.

Las piezas críticas se validaron también con mutación (quitar `AllowedHostsOriginValidator`, hacer que el latido renueve el turno, quitar el filtro de eco, quitar el aviso desde las vistas): en cada caso la prueba correspondiente falla.

## Endpoints principales

| Método | Ruta | Descripción | Permiso mínimo |
|---|---|---|---|
| POST | `/api/auth/register/` | Registro (Gestor o Colaborador) | Público |
| POST | `/api/auth/login/` | Login, devuelve tokens JWT | Público |
| POST | `/api/auth/refresh/` | Renovar el token de acceso | Público (con refresh token) |
| GET | `/api/auth/me/` | Datos del usuario autenticado | Autenticado |
| GET/POST | `/api/workspaces/` | Listar mis espacios / crear espacio | Crear: Gestor |
| POST | `/api/workspaces/{id}/members/` | Agregar miembro por email | Gestor del espacio |
| POST | `/api/workspaces/{id}/members/create/` | Crear un colaborador dentro del espacio | Gestor del espacio |
| GET/POST | `/api/documents/` | Listar documentos visibles / crear documento | Crear: Gestor del espacio |
| GET/DELETE | `/api/documents/{id}/` | Ver / eliminar (borrado lógico) | Ver: Lectura · Eliminar: Administración |
| POST | `/api/documents/{id}/save/` | Guardar una nueva versión. Acepta `version_base` opcional: si no es la última, responde **409** con `version_actual` y `contenido_actual` | Edición |
| GET | `/api/documents/{id}/versions/` | Historial de versiones | Lectura |
| GET | `/api/documents/{id}/compare/?a=1&b=2` | Comparar dos versiones | Lectura |
| POST | `/api/documents/{id}/versions/{n}/restore/` | Restaurar una versión (crea una nueva) | Administración |
| POST | `/api/documents/{id}/permissions/` | Asignar o cambiar permisos | Administración |
| GET | `/api/audit/` | Consultar la bitácora | Gestor: todo su espacio · Colaborador: sus documentos |

Un recurso de un espacio ajeno responde **404** (no 403), para no confirmar su existencia.

Guardar (`/save/`) y restaurar (`/restore/`) por REST avisan en vivo a quienes tienen el documento abierto (mensaje `version_guardada`).

## Colaboración en tiempo real (Fase 2)

### Cómo probarlo

Abrir el mismo documento con dos o tres usuarios demo en navegadores distintos (por ejemplo, uno normal y otro en incógnito):

1. Cada uno ve el indicador **En vivo** y los avatares de quienes están conectados.
2. `editor@demo.com` pulsa **Editar**: los demás ven «Editando: …» y el texto aparece mientras se escribe.
3. **Guardar** (o 20 s sin escribir) crea **una** versión y libera el turno; el historial se actualiza en todos sin recargar.
4. Si alguien guarda o restaura mientras otra persona edita, a esta se le avisa y, al guardar, se le muestra el **conflicto** con ambos textos para que decida.

El detalle del diseño está en [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md#8-colaboración-en-tiempo-real-fase-2).

### Protocolo del WebSocket

Conexión: `new WebSocket("ws://localhost:8000/ws/documents/{id}/", ["access_token", "<jwt de acceso>"])`. El token viaja como **subprotocolo**, no en la URL.

| Dirección | Mensaje | Campos |
|---|---|---|
| Cliente → servidor | `latido` | — (cada 10 s; mantiene **solo** la presencia) |
| | `pedir_turno` | — (requiere Edición) |
| | `editar` | `contenido` (renueva el turno; no crea versión) |
| | `liberar_turno` | `version_base?` (confirmar la versión vista tras un conflicto), `descartar?` |
| Servidor → cliente | `conectado` | `nivel` |
| | `presencia` | `usuarios` |
| | `turno` | `turno` (`{usuario_id, nombre}` o `null`) |
| | `turno_ocupado` | `turno` |
| | `cambio` | `contenido`, `usuario_id`, `nombre` |
| | `version_guardada` | `numero_version`, `autor` |
| | `conflicto` | `version_actual`, `contenido_actual` |
| | `borrador_en_conflicto` | `autor`, `version_actual` |
| | `error` | `codigo` (400 · 403 · 409 · 413), `motivo`, `detalle` |

Códigos de cierre: **4401** (sin token, inválido o vencido) y **4404** (el documento no existe, fue eliminado, es de otro espacio o ya no tienes acceso).

### Configuración

| Variable / setting | Por defecto | Qué controla |
|---|---|---|
| `REDIS_URL` (entorno) | `redis://localhost:6379/0` (en Compose: `redis://redis:6379/0`) | Conexión a Redis |
| `TURNO_TTL` | 30 s | Vida del turno sin ediciones |
| `PRESENCIA_TTL` | 30 s | Tiempo sin latido para dar por desconectada una pestaña |
| `EDITAR_MAX_CARACTERES` | 200 000 | Tamaño máximo de un mensaje `editar` (si se supera: error 413) |

Los tres últimos se pueden definir en `settings.py`; si no están, se usan los valores por defecto.

### Producción

En desarrollo, `daphne` en `INSTALLED_APPS` hace que `runserver` sirva HTTP y WebSocket (con recarga automática), sin cambiar el comando de arranque. **`runserver` es solo para desarrollo**: en producción se lanzaría `daphne -b 0.0.0.0 -p 8000 config.asgi:application` detrás de un proxy que permita WebSocket.

## Limitaciones conocidas

- **El usuario del WebSocket se carga al conectar.** Si se desactiva una cuenta mientras está conectada, la conexión sigue activa hasta que vence su token de acceso (60 min). Los permisos sobre el documento sí se vuelven a comprobar en cada mensaje.
- **Una salida brusca tarda en reflejarse en la presencia.** Si una pestaña desaparece sin cerrar la conexión (caída de red, proceso del navegador terminado), puede tardar hasta **~40 s** en salir de la presencia: 30 s sin latido más hasta 10 s hasta el siguiente latido de otra conexión, que es cuando se purga. Un cierre normal de pestaña se refleja al instante.
- **La suite de pruebas tarda unos 2 minutos** (entre 1:53 y 2:21 en las últimas ejecuciones), porque varias pruebas esperan la expiración real de un TTL en Redis o dejan una conexión inactiva más de 5 s, en vez de simular el reloj.

## Mejoras futuras

- **Limitar el tamaño del frame WebSocket en Daphne** (o en el proxy). Hoy el límite `EDITAR_MAX_CARACTERES` se aplica después de recibir y leer el JSON del mensaje.
- **Exportar documentos** a `.txt` / `.md` e **importarlos**.
- **Soporte para imágenes** y otros tipos de contenido además de texto.
- **Una interfaz para recuperar borradores en conflicto.** Hoy el texto de un guardado automático en conflicto se conserva en la bitácora (`BORRADOR_EN_CONFLICTO`) y solo puede recuperarse desde la API de auditoría (`/api/audit/`).
- **Pruebas automáticas del frontend.** El comportamiento del editor (turno, conflictos, avisos) se verificó a mano.

## Estado

- [x] Modelo de datos, diagrama ER y documento de arquitectura
- [x] API REST con autenticación JWT y permisos por documento
- [x] Versionado inmutable, comparación y restauración
- [x] Borrado lógico y bitácora de auditoría
- [x] Pruebas automatizadas (pytest): 63 en total
- [x] Frontend en React (login, registro, editor, historial, comparación, gestión de acceso)
- [x] Todo el entorno con un solo comando (Docker Compose)
- [x] **Fase 2 completa** (rama `fase-2`): colaboración en tiempo real con presencia, turno de edición, edición en vivo, control optimista por número de versión y avisos en vivo de versiones guardadas o restauradas