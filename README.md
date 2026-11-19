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

Las decisiones técnicas están justificadas en [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) y el modelo de datos en [`docs/diagrama-er.png`](docs/diagrama-er.png).

## Cómo levantar el proyecto
Requisitos: **Docker Desktop** y **Git**. No hace falta instalar Python ni Node.

```bash
git clone https://github.com/alesandroRZc/docspace.git
cd docspace
git checkout fase-1
cp .env.example .env
docker compose up --build
```
> En Windows con CMD, usar `copy .env.example .env` en lugar de `cp`. (En PowerShell `cp` funciona igual.)

Con eso se levantan **tres servicios**:

| Servicio | Qué hace |
|---|---|
| `db` | PostgreSQL 16 (con healthcheck) |
| `backend` | Aplica migraciones, carga datos demo y levanta Django |
| `frontend` | Servidor de desarrollo de Vite con recarga en vivo |

## URLs

| Recurso | URL |
|---|---|
| Aplicación web | http://localhost:5173 |
| API | http://localhost:8000/api/ |
| Documentación Swagger | http://localhost:8000/api/docs/ |

## Usuarios de prueba

Todos con la contraseña **`Demo12345`**.

| Email | Rol | Qué permite demostrar |
|---|---|---|
| `gestor@demo.com` | Gestor del "Espacio Demo" | Control total del espacio y sus documentos |
| `editor@demo.com` | Colaborador con permiso de edición | Puede guardar nuevas versiones |
| `lector@demo.com` | Colaborador con permiso de lectura | Ve el documento, pero recibe 403 al intentar guardar |
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
| POST | `/api/documents/{id}/save/` | Guardar una nueva versión | Edición |
| GET | `/api/documents/{id}/versions/` | Historial de versiones | Lectura |
| GET | `/api/documents/{id}/compare/?a=1&b=2` | Comparar dos versiones | Lectura |
| POST | `/api/documents/{id}/versions/{n}/restore/` | Restaurar una versión (crea una nueva) | Administración |
| POST | `/api/documents/{id}/permissions/` | Asignar o cambiar permisos | Administración |
| GET | `/api/audit/` | Consultar la bitácora | Gestor: todo su espacio · Colaborador: sus documentos |

Un recurso de un espacio ajeno responde **404** (no 403), para no confirmar su existencia.

## Estado

- [x] Modelo de datos, diagrama ER y documento de arquitectura
- [x] API REST con autenticación JWT y permisos por documento
- [x] Versionado inmutable, comparación y restauración
- [x] Borrado lógico y bitácora de auditoría
- [x] Pruebas automatizadas (pytest)
- [x] Frontend en React (login, registro, editor, historial, comparación, gestión de acceso)
- [x] Todo el entorno con un solo comando (Docker Compose)
- [ ] Fase 2: colaboración en tiempo real (rama `fase-2`)