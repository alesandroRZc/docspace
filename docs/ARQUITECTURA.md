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

## 

## **2\. Estructura del Proyecto**

```
docspace/
├── backend/
│   ├── config/          # Configuración principal de Django y enrutador base
│   ├── accounts/        # Gestión de usuarios y autenticación JWT
│   ├── workspaces/      # Espacios de trabajo y control de membresías
│   ├── documents/       # Documentos, control de versiones inmutables y permisos
│   ├── audit/           # Bitácora de auditoría transaccional
│   └── tests/           # Suite de pruebas automatizadas con pytest
├── frontend/
│   └── src/
│       ├── api/         # Servicios de integración HTTP con el backend
│       ├── components/  # Componentes UI reutilizables
│       ├── hooks/       # Custom hooks para lógica compartida
│       └── pages/       # Vistas principales de la SPA
├── docs/                # Diagramas DER y documentación de arquitectura
├── docker-compose.yml   # Orquestación del entorno (PostgreSQL, Django y Frontend)
└── README.md            # Instrucciones de configuración y despliegue
```

**Capa de Servicios:** Dentro de cada aplicación del backend, la lógica de negocio compleja (crear versiones, validar permisos, registrar auditoría) se aísla en archivos services.py. Las vistas (controllers) actúan únicamente como puntos de entrada que reciben la petición y devuelven la respuesta HTTP.

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