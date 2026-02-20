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
| POST | `/api/v1/intelligence/analyze-entity` | No | Análisis RAG por consulta |
| POST | `/api/v1/sanctions/upload-xml` | Sí (superuser/admin) | Cargar XML de sanciones |
| GET | `/api/v1/search/sanctions` | Sí (usuario activo) | Búsqueda híbrida en sanciones |
| GET | `/api/v1/audit/history` | Sí (admin/auditor/superuser) | Historial de auditoría |

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

Descripción: consulta en lenguaje natural para análisis de listas de sanciones.

Body (`AnalysisRequest`):

```json
{
  "query": "¿Qué riesgos hay para Empresa X?"
}
```

Respuesta 200 (`AnalysisResponse`):

```json
{
  "analysis": "Resultado del análisis generado por la cadena RAG"
}
```

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
