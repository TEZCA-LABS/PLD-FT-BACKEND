# Documentación de Endpoints para Frontend

Esta guía documenta **todos los endpoints actuales** del backend para integrarlos correctamente desde frontend.

## 1) Base URL y convenciones

- Base API v1: `/api/v1`
- Endpoint raíz (fuera de v1): `/`
- Formato de errores habitual:

```json
{
  "detail": "mensaje de error"
}
```

## 2) Autenticación y autorización

### 2.1 Obtener token

- Endpoint: `POST /api/v1/auth/login/access-token`
- Tipo de body: `application/x-www-form-urlencoded`
- Campos:
  - `username` (string): correo del usuario
  - `password` (string)

Respuesta exitosa:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

### 2.2 Enviar token en requests protegidas

Header:

```http
Authorization: Bearer <access_token>
```

### 2.3 Reglas de permisos usadas por la API

- **Usuario activo**: `is_active = true`
- **Superuser/Admin para endpoints administrativos**:
  - válido si `is_superuser = true` **o** `role = "admin"`
- **Privilegiado para lectura sensible**:
  - válido si `is_superuser = true` **o** `role in ["admin", "auditor"]`

## 3) Resumen rápido de endpoints

| Método | Ruta | Auth | Uso principal |
|---|---|---|---|
| GET | `/` | No | Mensaje de bienvenida |
| POST | `/api/v1/auth/login/access-token` | No | Login y obtención de JWT |
| GET | `/api/v1/auth/me` | Sí (activo) | Datos del usuario autenticado |
| POST | `/api/v1/users/` | Sí (superuser/admin) | Crear usuario |
| PUT | `/api/v1/users/{user_id}` | Sí (superuser/admin) | Actualizar usuario |
| GET | `/api/v1/users/` | Sí (superuser/admin) | Listar usuarios |
| GET | `/api/v1/users/{user_id}` | Sí (admin/auditor/superuser) | Obtener usuario por id |
| DELETE | `/api/v1/users/{user_id}` | Sí (superuser/admin) | Eliminar usuario |
| GET | `/api/v1/entities/` | No | Listar entidades |
| POST | `/api/v1/entities/` | No | Crear entidad (dispara ETL async) |
| POST | `/api/v1/intelligence/analyze-entity` | Sí (usuario activo) | Análisis RAG por consulta (legacy compatible) |
| GET | `/api/v1/intelligence/sessions` | Sí (usuario activo) | Listar sesiones de chat IA |
| POST | `/api/v1/intelligence/sessions` | Sí (usuario activo) | Crear sesión de investigación |
| PATCH | `/api/v1/intelligence/sessions/{session_id}` | Sí (owner/admin/auditor/superuser) | Actualizar metadatos de sesión |
| DELETE | `/api/v1/intelligence/sessions/{session_id}` | Sí (owner/admin/auditor/superuser) | Archivado lógico de sesión |
| GET | `/api/v1/intelligence/sessions/{session_id}/messages` | Sí (owner/admin/auditor/superuser) | Historial de mensajes |
| POST | `/api/v1/intelligence/sessions/{session_id}/messages` | Sí (owner/admin/auditor/superuser) | Enviar prompt y persistir respuesta IA |
| POST | `/api/v1/intelligence/sessions/{session_id}/attachments` | Sí (owner/admin/auditor/superuser) | Cargar evidencia al caso |
| GET | `/api/v1/intelligence/sessions/{session_id}/attachments` | Sí (owner/admin/auditor/superuser) | Listar evidencias del caso |
| POST | `/api/v1/intelligence/sessions/{session_id}/export` | Sí (owner/admin/auditor/superuser) | Exportar expediente (PDF/JSON) |
| POST | `/api/v1/sanctions/upload-xml` | Sí (superuser/admin) | Cargar XML de sanciones |
| GET | `/api/v1/search/sanctions` | Sí (usuario activo) | Búsqueda híbrida en sanciones |
| GET | `/api/v1/audit/history` | Sí (admin/auditor/superuser) | Historial de auditoría |
| POST | `/api/v1/audit/ai-events` | Sí (usuario activo) | Registrar evento IA explícito |
| GET | `/api/v1/roles/permissions` | Sí (admin/auditor/superuser) | Obtener matriz de permisos por rol |
| PUT | `/api/v1/roles/permissions` | Sí (superuser/admin) | Actualizar matriz de permisos por rol |

---

## 4) Detalle por endpoint

## 4.1 Sistema

### GET `/`

Descripción: saludo del servicio.

Respuesta 200:

```json
{
  "message": "Welcome to PLD-FT Backend API"
}
```

---

## 4.2 Auth

### POST `/api/v1/auth/login/access-token`

Descripción: login OAuth2 compatible y generación de JWT.

Body (`application/x-www-form-urlencoded`):

- `username`: string (email)
- `password`: string

Respuesta 200:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

Errores comunes:

- `400` -> `"Incorrect email or password"`
- `400` -> `"Inactive user"`

### GET `/api/v1/auth/me`

Descripción: devuelve el usuario autenticado.

Auth: Bearer token requerido.

Respuesta 200 (`User`):

```json
{
  "id": 1,
  "email": "admin@example.com",
  "is_active": true,
  "is_superuser": false,
  "role": "admin",
  "created_at": "2026-02-19T12:00:00",
  "created_by_id": 1
}
```

Errores comunes:

- `403` -> `"Could not validate credentials"`
- `400` -> `"Inactive user"`
- `404` -> `"User not found"`

---

## 4.3 Usuarios

### Modelo `UserCreate`

```json
{
  "email": "user@company.com",
  "password": "secret123",
  "is_active": true,
  "is_superuser": false,
  "role": "consultant",
  "master_password": "opcional"
}
```

Valores válidos de `role`:

- `admin`
- `auditor`
- `consultant`
- `user`

### POST `/api/v1/users/`

Descripción: crea usuario (solo superuser/admin).

Regla especial:

- Si `is_superuser=true`, debes enviar `master_password` y debe coincidir con la del backend.

Respuesta 200 (`User`).

Errores comunes:

- `400` -> `"Master password is required to create a superuser."`
- `400` -> `"Invalid master password."`
- `400` -> `"The user with this username already exists in the system."`
- `400` -> `"The user doesn't have enough privileges"`

### PUT `/api/v1/users/{user_id}`

Descripción: actualiza un usuario (solo superuser/admin).

Path params:

- `user_id` (int)

Body (`UserUpdate`):

```json
{
  "email": "updated@company.com",
  "password": "optional-new-pass",
  "is_active": true,
  "is_superuser": false,
  "role": "auditor"
}
```

Respuesta 200 (`User`).

Errores comunes:

- `404` -> `"The user with this id does not exist in the system"`
- `400` -> `"The user doesn't have enough privileges"`

### GET `/api/v1/users/`

Descripción: lista usuarios (solo superuser/admin).

Query params:

- `skip` (int, default `0`)
- `limit` (int, default `100`)

Respuesta 200: `User[]`.

### GET `/api/v1/users/{user_id}`

Descripción: detalle de usuario por id (admin/auditor/superuser).

Path params:

- `user_id` (int)

Respuesta 200 (`User`).

Errores comunes:

- `404` -> `"The user with this id does not exist in the system"`
- `403` -> `"Not authorized to view audit logs."`

### DELETE `/api/v1/users/{user_id}`

Descripción: elimina usuario (solo superuser/admin).

Path params:

- `user_id` (int)

Respuesta 200 (`User` eliminado).

Errores comunes:

- `404` -> `"The user with this id does not exist in the system"`
- `400` -> `"You cannot delete yourself."`

---

## 4.4 Entidades

### GET `/api/v1/entities/`

Descripción: lista entidades.

Query params:

- `skip` (int, default `0`)
- `limit` (int, default `100`)

Respuesta 200 (`Entity[]`):

```json
[
  {
    "id": 10,
    "name": "Entidad Demo",
    "source": "manual",
    "content": "texto de la entidad"
  }
]
```

### POST `/api/v1/entities/`

Descripción: crea entidad y dispara procesamiento ETL/vectorización asíncrona.

Body (`EntityCreate`):

```json
{
  "name": "Entidad Demo",
  "source": "manual",
  "content": "texto de entrada"
}
```

Respuesta 200 (`Entity`):

```json
{
  "id": 0,
  "name": "Entidad Demo",
  "source": "manual",
  "content": "texto de entrada"
}
```

> Nota frontend: `id=0` es una respuesta placeholder inmediata; el procesamiento real sucede en background.

---

## 4.5 Inteligencia (RAG)

### POST `/api/v1/intelligence/analyze-entity`

Descripción: consulta en lenguaje natural para análisis de listas de sanciones (compatibilidad legacy).

Auth: usuario activo.

Body (`AnalysisRequest`):

```json
{
  "query": "¿Qué riesgos hay para Empresa X?"
}
```

Respuesta 200 (`AnalysisResponse`):

```json
{
  "analysis": "Resultado del análisis generado por la cadena RAG",
  "context": {
    "source": {
      "name": "Entidad Demo",
      "organization": "UN",
      "date": null,
      "snippet": "Detalle relevante",
      "url": null
    },
    "related_entities": [
      {
        "name": "Entidad Demo",
        "relationship": "posible coincidencia",
        "type": "entity"
      }
    ]
  },
  "usage": {
    "prompt_tokens": null,
    "completion_tokens": null,
    "latency_ms": null
  },
  "model_version": "gpt-4-turbo"
}
```

### GET `/api/v1/intelligence/sessions`

Descripción: obtiene sesiones del usuario autenticado (admin/auditor/superuser puede ver todas).

Query params:

- `skip` (int, default `0`)
- `limit` (int, default `20`, máximo `100`)
- `status` (opcional: `open | closed | archived`)

### POST `/api/v1/intelligence/sessions`

Descripción: crea una sesión de investigación.

Body:

```json
{
  "title": "Investigación cliente ACME",
  "initial_context": {
    "entity_id": "ent_991",
    "search_query": "ACME Holdings"
  }
}
```

Respuesta 201:

```json
{
  "id": 124,
  "title": "Investigación cliente ACME",
  "status": "open",
  "created_at": "2026-02-19T16:00:00Z"
}
```

### PATCH `/api/v1/intelligence/sessions/{session_id}`

Descripción: actualiza `title` y/o `status` de la sesión.

### DELETE `/api/v1/intelligence/sessions/{session_id}`

Descripción: archivado lógico de la sesión (`status = archived`).

### GET `/api/v1/intelligence/sessions/{session_id}/messages`

Descripción: historial de mensajes persistidos.

Query params: `skip`, `limit`.

### POST `/api/v1/intelligence/sessions/{session_id}/messages`

Descripción: guarda prompt del usuario y respuesta IA persistida.

Body:

```json
{
  "query": "Genera resumen ejecutivo para comité de cumplimiento",
  "options": {
    "model": "compliance-v4",
    "temperature": 0.2,
    "redact_pii": true
  }
}
```

Respuesta 201:

```json
{
  "message_id": 8,
  "analysis": "Resumen ejecutivo...",
  "context": {
    "source": {
      "name": "Lista OFAC SDN",
      "organization": "OFAC",
      "date": null,
      "snippet": "MATCH: ...",
      "url": null
    },
    "related_entities": []
  },
  "usage": {
    "prompt_tokens": null,
    "completion_tokens": null,
    "latency_ms": 1800
  },
  "model_version": "compliance-v4",
  "created_at": "2026-02-19T16:05:10Z"
}
```

### POST `/api/v1/intelligence/sessions/{session_id}/attachments`

Descripción: sube evidencia para enriquecer el análisis.

Content-Type: `multipart/form-data`.

Campo requerido: `file`.

### GET `/api/v1/intelligence/sessions/{session_id}/attachments`

Descripción: lista archivos asociados a la sesión.

Query params: `skip`, `limit`.

### POST `/api/v1/intelligence/sessions/{session_id}/export`

Descripción: exporta expediente del caso.

Body:

```json
{
  "format": "pdf",
  "include": ["messages", "sources", "entities", "metadata"]
}
```

Respuesta:

- `application/pdf` como adjunto, o
- `application/json` como adjunto.

---

## 4.6 Sanciones

### POST `/api/v1/sanctions/upload-xml`

Descripción: sube archivo XML de sanciones UN, inserta/actualiza registros.

Auth: superuser/admin.

Content-Type: `multipart/form-data`

Campo requerido:

- `file`: archivo `.xml`

Respuesta 201:

```json
{
  "message": "XML processed successfully",
  "total_processed": 120,
  "created": 100,
  "updated": 20
}
```

Errores comunes:

- `400` -> `"File must be an XML file"`
- `400` -> error de parseo XML (mensaje variable)
- `500` -> `"Error saving data to database"`

---

## 4.7 Búsqueda

### GET `/api/v1/search/sanctions`

Descripción: búsqueda híbrida (exacta, fuzzy, vectorial) con resumen IA.

Auth: usuario activo.

Query params:

- `q` (string, requerido, mínimo 2 caracteres)
- `limit` (int, opcional, default `10`, máximo `50`)

Respuesta 200:

```json
{
  "query": "empresa x",
  "summary": "Resumen generado con LangChain",
  "results": [
    {
      "id": 123,
      "entity_name": "EMPRESA X",
      "reference_number": "REF-001",
      "program": "UN",
      "source": "UN_CONSOLIDATED",
      "score": "N/A"
    }
  ]
}
```

Notas frontend:

- El backend intenta auditar cada búsqueda, pero si falla el audit log, **la búsqueda igual responde 200**.
- `score` hoy es string fijo `"N/A"`.

---

## 4.8 Auditoría

### GET `/api/v1/audit/history`

Descripción: historial de auditoría del sistema.

Auth: admin/auditor/superuser.

Query params:

- `skip` (int, default `0`)
- `limit` (int, default `50`)

Respuesta 200 (`AuditLog[]`):

```json
[
  {
    "id": 1,
    "user_id": 5,
    "action": "search",
    "details": {
      "query": "empresa x",
      "results_count": 3
    },
    "timestamp": "2026-02-19T18:22:00"
  }
]
```

Errores comunes:

- `403` -> `"Not authorized to view audit logs."`

### POST `/api/v1/audit/ai-events`

Descripción: registra eventos IA de alto valor para trazabilidad.

Auth: usuario activo.

Body:

```json
{
  "session_id": 124,
  "event_type": "analysis_generated",
  "metadata": {
    "message_id": 8,
    "model": "compliance-v4",
    "pii_redaction": true
  }
}
```

---

## 4.9 Roles

### GET `/api/v1/roles/permissions`

Descripción: obtiene la matriz completa de permisos por rol para administración frontend.

Auth: admin/auditor/superuser.

Respuesta 200 (`RolePermissionsResponse`):

```json
{
  "roles": [
    { "key": "admin", "label": "Admin" },
    { "key": "consultant", "label": "Analista" },
    { "key": "auditor", "label": "Auditor" }
  ],
  "permissions": [
    {
      "id": "query_llm",
      "module": "consultas",
      "label": "Consultar LLM (IA Generativa)",
      "description": "Permite enviar consultas al asistente IA.",
      "allowed_roles": ["admin", "consultant"]
    }
  ],
  "updated_at": "2026-03-21T12:34:56.000000+00:00"
}
```

Errores comunes:

- `403` -> `"Not authorized to view audit logs."`

### PUT `/api/v1/roles/permissions`

Descripción: actualiza los roles permitidos por cada permiso de la matriz.

Auth: superuser/admin.

Body (`RolePermissionsUpdateRequest`):

```json
{
  "permissions": [
    {
      "id": "query_llm",
      "allowed_roles": ["admin", "consultant", "auditor"]
    },
    {
      "id": "upload_sanctions_xml",
      "allowed_roles": ["admin"]
    }
  ]
}
```

Respuesta 200 (`RolePermissionsResponse`):

```json
{
  "roles": [
    { "key": "admin", "label": "Admin" },
    { "key": "consultant", "label": "Analista" },
    { "key": "auditor", "label": "Auditor" }
  ],
  "permissions": [
    {
      "id": "query_llm",
      "module": "consultas",
      "label": "Consultar LLM (IA Generativa)",
      "description": "Permite enviar consultas al asistente IA.",
      "allowed_roles": ["admin", "consultant", "auditor"]
    }
  ],
  "updated_at": "2026-03-21T12:40:00.000000+00:00"
}
```

Errores comunes:

- `400` -> `"Invalid roles for permission '<permission_id>': ..."`
- `400` -> `"The user doesn't have enough privileges"`

---

## 5) Ejemplos frontend (fetch)

### Login

```ts
const body = new URLSearchParams({
  username: email,
  password,
});

const res = await fetch('/api/v1/auth/login/access-token', {
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  body,
});

const data = await res.json();
localStorage.setItem('token', data.access_token);
```

### Request autenticada

```ts
const token = localStorage.getItem('token');

const res = await fetch('/api/v1/auth/me', {
  headers: { Authorization: `Bearer ${token}` },
});

const me = await res.json();
```

### Upload XML

```ts
const form = new FormData();
form.append('file', fileInput.files[0]);

await fetch('/api/v1/sanctions/upload-xml', {
  method: 'POST',
  headers: { Authorization: `Bearer ${token}` },
  body: form,
});
```

## 6) Checklist de implementación frontend

- Guardar `access_token` y enviarlo como `Bearer` en rutas protegidas.
- Manejar `400`, `403`, `404`, `500` leyendo `detail` del error.
- En formularios de usuarios, incluir selector de `role` con valores permitidos.
- Si se crea superusuario, pedir `master_password`.
- En búsqueda, validar `q.length >= 2` antes de consultar.
- En carga XML, validar extensión `.xml` del archivo en cliente.
