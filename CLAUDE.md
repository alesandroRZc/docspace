# DocSpace — Instrucciones para el agente

## Contexto
- Prueba técnica de Avio Trade Group. Trabajamos en la rama `fase-2`.
- La rama `fase-1` es código escrito a mano: **nunca** hacer checkout, commit ni push en ella.
- Objetivo de la Fase 2: edición colaborativa en tiempo real sobre el sistema existente.

## Stack
- Backend: Python 3.11, Django 5.2, DRF, SimpleJWT, drf-spectacular, PostgreSQL 16, pytest.
- Frontend: React + Vite + TypeScript, Mantine, TanStack Query, react-router-dom.
- Entorno: Docker Compose con servicios `db`, `backend` y `frontend`.

## Comandos
- Levantar todo: `docker compose up --build`
- Pruebas backend: `docker compose exec backend pytest -v`
- Lint frontend: `cd frontend && npm run lint`
- Build frontend: `cd frontend && npm run build`

## Arquitectura (respetar siempre)
- La lógica de negocio vive en `services.py`; las vistas son delgadas.
- **Única fuente de permisos:** `documents/services.py` (`obtener_nivel`, `tiene_nivel`, `documentos_visibles`). No duplicar esa lógica en ningún otro lugar, tampoco en el canal en tiempo real.
- Jerarquía: LECTURA < EDICION < ADMINISTRACION. El Gestor del espacio siempre tiene ADMINISTRACION.
- Aislamiento: un recurso de otro espacio responde **404**, no 403. Sin el nivel suficiente: **403**.
- Las versiones son **inmutables**: crearlas siempre con `guardar_version()` (usa `select_for_update` y registra en la bitácora). Nunca editar ni borrar una `VersionDocumento`.
- Toda acción relevante se registra con `registrar_evento()` de `audit/services.py`.
- Borrado lógico con `eliminado_en`; los documentos eliminados no son accesibles.
- Los permisos se validan **en el servidor**. El frontend solo oculta controles.

## Convenciones
- Nombres de modelos, funciones y variables en **español**, como el código existente.
- Commits con Conventional Commits, en español.
- Trabajar en pasos pequeños. Proponer un plan antes de cambios grandes.
- No hacer commits por iniciativa propia: los hago yo después de revisar.
- No agregar dependencias sin explicar antes por qué hacen falta.
- Todo cambio de backend lleva su prueba. Los 10 tests existentes deben seguir pasando.

## Decisiones de la Fase 2
- Tiempo real con **Django Channels** (WebSockets) y **Redis** como channel layer (servicio nuevo en Compose).
- El WebSocket se autentica con el JWT y los permisos se verifican al conectar y en cada mensaje.
- Un usuario con LECTURA recibe cambios pero el servidor rechaza lo que intente emitir.
- Conflictos: **turno de edición** (un editor a la vez, los demás ven quién edita) + **control optimista** por número de versión como red de seguridad. Nunca perder datos en silencio.