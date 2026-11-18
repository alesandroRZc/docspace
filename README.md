
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

Requisito: Docker Desktop.

1. Copiar las variables de entorno:
   ```bash
   cp .env.example .env
   ```
   (En PowerShell: `copy .env.example .env`)

2. Levantar todo con un solo comando:
   ```bash
   docker compose up --build
   ```

Al arrancar, el backend aplica las migraciones y crea automáticamente los datos de demostración.

| Servicio | URL |
|---|---|
| Documentación de la API (Swagger) | http://localhost:8000/api/docs/ |
| Esquema OpenAPI | http://localhost:8000/api/schema/ |

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

## Estado del proyecto

- [x] Diagrama ER y documento de arquitectura
- [x] Backend completo del flujo principal, con Swagger
- [x] Pruebas automatizadas de aislamiento, permisos y versionado
- [x] Docker Compose con datos de demostración
- [ ] Frontend en React
- [ ] Fase 2: colaboración en tiempo real