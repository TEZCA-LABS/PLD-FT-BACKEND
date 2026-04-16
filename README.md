# Documentación Técnica: Arquitectura Backend PLD/FT

**Versión:** 1.1  
**Fecha:** 13 de Diciembre, 2025 | **Actualizado:** 20 de Febrero, 2026

---

## Índice Rápido
1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Deployment Rápido](#deployment-rápido)
3. [Arquitectura del Sistema](#arquitectura-del-sistema)
4. [Guía Completa de Despliegue](#guía-completa-de-despliegue)

---

## Resumen Ejecutivo

Este documento detalla la arquitectura, decisiones de diseño y protocolos de implementación del sistema Backend para la Prevención de Lavado de Dinero y Financiamiento al Terrorismo (PLD/FT). El sistema está diseñado como una solución híbrida que integra procesamiento transaccional tradicional con capacidades avanzadas de Inteligencia Artificial (RAG - Retrieval-Augmented Generation) para el análisis de entidades y sanciones.

---

## Deployment Rápido

### Primeros pasos (5 minutos)

```bash
# 1. Clone el repositorio
git clone <repo-url>
cd PLD-FT-BACKEND

# 2. Configure variables de entorno
cp .env.example .env
# Editar .env con valores reales (API keys, credenciales, etc.)

# 3. Inicie los servicios
docker-compose up -d --build

# 4. Aplique las migraciones
docker-compose exec backend alembic upgrade head

# 5. Opcionalmente, cargue datos de prueba
docker-compose exec backend python scripts/seed_database.py

# 6. Verifique que está running
curl http://localhost:8000/health
```

### Documentos Importantes

- **[DEPLOYMENT_ANALYSIS.md](docs/DEPLOYMENT_ANALYSIS.md)** - Análisis detallado de problemas y soluciones
- **[.env.example](.env.example)** - Template de variables de entorno (REQUIERE CUSTOMIZACIÓN)
- **[scripts/deploy.sh](scripts/deploy.sh)** - Automated deployment con backups y rollback
- **[scripts/rollback.sh](scripts/rollback.sh)** - Emergency rollback procedure

---

## Arquitectura del Sistema

El sistema sigue un patrón de **Arquitectura Limpia Modular (Modular Clean Architecture)**, priorizando la separación de responsabilidades, la escalabilidad y la mantenibilidad.

### Descripción Arquitectónica General

El sistema opera bajo un modelo de **Arquitectura Limpia (Clean Architecture)** adaptada a un entorno de microservicios híbrido. El diseño se centra en la independencia de los componentes, permitiendo que la lógica de negocio (reglas PLD/FT) evolucione sin verse afectada por cambios en la interfaz de usuario o en los proveedores de infraestructura (como la base de datos o APIs externas).

#### Capas Funcionales

1.  **Capa de Presentación (Entry Point)**
    *   Actúa como la "puerta de entrada" segura al sistema. Está materializada por **FastAPI**, que gestiona todas las solicitudes HTTP entrantes.
    *   Su única responsabilidad es enrutar las peticiones, validar que los datos cumplan con los formatos esperados (usando **Pydantic**) y asegurar que solo usuarios autenticados accedan a recursos protegidos. No contiene reglas de negocio complejas.

2.  **Capa de Aplicación y Servicios (Core)**
    *   Es el "cerebro" del sistema. Aquí residen los casos de uso principales, como "Analizar una Entidad" o "Registrar una Sanción".
    *   Orquesta la interacción entre los datos almacenados y los servicios externos. Por ejemplo, cuando se solicita un análisis de riesgo, esta capa coordina la recuperación de documentos de la base de datos, los envía al motor de Inteligencia Artificial y procesa la respuesta antes de devolverla al usuario.

3.  **Capa de Infraestructura y Persistencia**
    *   Provee los recursos técnicos necesarios para que el sistema funcione. Incluye la base de datos **PostgreSQL** para guardar información estructurada (usuarios, registros) y vectorial (embeddings para IA).
    *   También incluye el bus de mensajes **Redis** y los workers de **Celery**, que actúan como un sistema de "trabajo en segundo plano", encargándose de tareas pesadas (como buscar en listas negras internacionales) sin que el usuario tenga que esperar con la pantalla congelada.

4.  **Capa de Inteligencia (RAG)**
    *   Un módulo especializado que conecta el sistema con Modelos de Lenguaje (LLMs). Utiliza una técnica llamada **Retrieval-Augmented Generation (RAG)**.
    *   En lugar de solo preguntar a la IA, el sistema primero busca información relevante en su propia base de datos (usando vectores matemáticos) y luego le entrega esa información a la IA para que genere una respuesta basada en hechos verificados, reduciendo alucinaciones y mejorando la precisión regulatoria.

### 2.2 Descripción de Módulos

1.  **Capa de Presentación (API)**: Implementada con **FastAPI**. Maneja la entrada/salida HTTP, validación de esquemas (Pydantic) y enrutamiento. Es el único punto de entrada para clientes externos.
2.  **Capa de Servicios (Business Logic)**: Contiene la lógica de negocio pura.
    *   **ETL (Extract, Transform, Load)**: Orquestado por **Celery** y **Redis**. Maneja tareas asíncronas pesadas como el web scraping y la normalización de datos para no bloquear el hilo principal de la API.
    *   **RAG (Retrieval-Augmented Generation)**: Utiliza **LangChain** para orquestar la interacción entre la base de datos vectorial y el LLM (OpenAI), permitiendo búsquedas semánticas y generación de análisis contextuales.
    *   **Entity Resolution**: Módulo de agrupamiento inteligente que identifica y unifica registros duplicados o variantes de la misma persona (ej. "J. Doe" vs "John Doe") utilizando algoritmos de similitud y reglas de negocio.
    *   **Audit Logs**: Sistema de registro inmutable que traza todas las acciones críticas (búsquedas, modificaciones de usuarios), garantizando la trazabilidad y el no repudio para cumplimiento normativo.
3.  **Capa de Persistencia**:
    *   **PostgreSQL**: Base de datos relacional principal.
    *   **pgvector**: Extensión de PostgreSQL que permite almacenar y consultar embeddings vectoriales dentro de la misma base de datos relacional, simplificando la infraestructura al evitar una base de datos vectorial separada.

## 3. Justificación Tecnológica

La selección del stack tecnológico responde a criterios de rendimiento, escalabilidad y robustez:

| Tecnología | Justificación |
| :--- | :--- |
| **FastAPI** | Framework moderno de alto rendimiento basado en Starlette y Pydantic. Su soporte nativo para asincronía (`async/await`) es crucial para manejar múltiples conexiones I/O bound (DB, API externas) eficientemente. |
| **PostgreSQL + pgvector** | PostgreSQL es el estándar de oro en bases de datos relacionales. `pgvector` permite capacidades de búsqueda vectorial (necesarias para IA) sin la complejidad operativa de mantener una base de datos vectorial dedicada (como Pinecone o Milvus), manteniendo la integridad referencial con los datos relacionales. |
| **Celery + Redis** | Para operaciones de larga duración (scraping, procesamiento de documentos), es imperativo liberar al servidor API. Celery ofrece una cola de tareas robusta y distribuida, usando Redis como broker de mensajes de baja latencia. |
| **Argon2** | Algoritmo de hashing de contraseñas ganador de la Password Hashing Competition. Ofrece resistencia superior a ataques de fuerza bruta mediante GPU/ASIC en comparación con algoritmos más antiguos como bcrypt o PBKDF2. |
| **Docker** | Garantiza la consistencia del entorno entre desarrollo, pruebas y producción. Se utiliza un **Dockerfile optimizado (Multi-Stage Build)** que separa la fase de construcción del entorno de ejecución, reduciendo el tamaño de la imagen final y mejorando la seguridad al ejecutarse como usuario no privilegiado (`appuser`). |

## 4. Protocolos de Seguridad y Control de Acceso

El sistema implementa un modelo de seguridad estricto para proteger la integridad de los datos y el acceso a funciones críticas.

### 4.1 Gestión de Identidad y Accesos (IAM)
*   **Autenticación**: Basada en **JWT (JSON Web Tokens)**. Stateless y escalable.
*   **Roles**:
    *   **Usuario Regular**: Acceso a consultas y operaciones básicas.
    *   **Superusuario**: Acceso total, incluyendo gestión de usuarios y configuración del sistema.

### 4.2 Protocolo de Alta de Usuarios (User Provisioning)
Para mitigar riesgos de seguridad interna, se han establecido las siguientes restricciones inmutables en el código:

1.  **Exclusividad de Creación**: Únicamente un usuario con rol de **Superusuario** puede crear nuevos usuarios en el sistema. Los endpoints de creación están protegidos por dependencias de seguridad (`get_current_active_superuser`).
2.  **Contraseña Maestra (Master Password)**: La creación de un *nuevo* Superusuario requiere, además de las credenciales del solicitante, una **Contraseña Maestra** definida en las variables de entorno del servidor. Esto actúa como un mecanismo de autenticación de dos factores administrativo (algo que tienes: token, algo que sabes: master password).
3.  **Auditoría Inmutable**: El modelo de datos `User` incluye campos de auditoría obligatorios:
    *   `created_at`: Timestamp automático de creación.
    *   `created_by_id`: Referencia inmutable al ID del superusuario que ejecutó la acción.

## 5. Guía de Desarrollo y Extensión

Para mantener la integridad arquitectónica, todo nuevo desarrollo debe seguir este flujo de trabajo:

### 5.1 Flujo para Nueva Funcionalidad
1.  **Definición del Modelo (Data Layer)**:
    *   Crear/Modificar modelo en `app/models/`.
    *   Generar migración: `alembic revision --autogenerate -m "descripcion"`.
    *   Aplicar migración: `alembic upgrade head`.
2.  **Esquemas de Validación (Interface Layer)**:
    *   Definir esquemas Pydantic en `app/schemas/` (Create, Update, Response).
3.  **Lógica de Negocio (Service Layer)**:
    *   Implementar funciones puras o clases en `app/services/`.
    *   *Regla*: Los servicios no deben depender de la API, solo de modelos y esquemas.
4.  **Exposición (API Layer)**:
    *   Crear endpoint en `app/api/v1/endpoints/`.
    *   Inyectar dependencias (DB, Usuario actual).
    *   Llamar a la capa de servicio.

### 5.2 Estándares de Código
*   **Tipado Estático**: Uso obligatorio de Type Hints de Python.
*   **Asincronía**: Preferir siempre `async def` para endpoints y operaciones de I/O.
*   **Inyección de Dependencias**: Utilizar el sistema de DI de FastAPI para sesiones de base de datos y autenticación.

### 6. Scripts Operativos y CLI Unificado

El proyecto utiliza un **CLI centralizado** (`scripts/cli.py`) para todas las operaciones de mantenimiento, sincronización, verificación y administración. Todos los comandos se ejecutan con:

```bash
docker-compose exec backend python -m scripts.cli [command] [subcommand] [options]
```

#### 6.1 Sincronización de Datos (data-sync)

```bash
# Sincronizar SAT 69-B (Contribuyentes Incumplidos)
docker-compose exec backend python -m scripts.cli data-sync sat

# Sincronizar sanciones UN + México vía Celery workers
docker-compose exec backend python -m scripts.cli data-sync sanctions

# Sincronizar solo UN o MEX
docker-compose exec backend python -m scripts.cli data-sync sanctions --source un
docker-compose exec backend python -m scripts.cli data-sync sanctions --source mex

# Clustering de entidades (desambiguación y unificación)
docker-compose exec backend python -m scripts.cli data-sync cluster
```

#### 6.2 Mantenimiento de Base de Datos (maint)

```bash
# Rellenar embeddings faltantes (vectorización de sanciones)
docker-compose exec backend python -m scripts.cli maint embeddings
docker-compose exec backend python -m scripts.cli maint embeddings --limit 100  # Procesar solo 100 registros
docker-compose exec backend python -m scripts.cli maint embeddings --batch-size 20  # Commit cada 20 registros

# Actualizar roles NULL de usuarios a 'consultant'
docker-compose exec backend python -m scripts.cli maint roles

# Limpiar tabla de versiones de Alembic (antes de re-estampar migraciones)
docker-compose exec backend python -m scripts.cli maint alembic-clean
```

#### 6.3 Verificación de Integridad (verify)

```bash
# Verificar operaciones CRUD de usuarios
docker-compose exec backend python -m scripts.cli verify users

# Verificar búsqueda exacta en sanciones
docker-compose exec backend python -m scripts.cli verify search

# Verificar estado de embeddings (con sample)
docker-compose exec backend python -m scripts.cli verify embeddings

# Verificar embeddings de registros específicos
docker-compose exec backend python -m scripts.cli verify embeddings --id 1454 --id 1455
```

#### 6.4 Operaciones Administrativas (admin)

```bash
# Resetear contraseña de usuario
docker-compose exec backend python -m scripts.cli admin reset-password correo@empresa.com nueva_contraseña
```

#### 6.5 Ayuda y Comandos Disponibles

```bash
# Ver todos los comandos disponibles
docker-compose exec backend python -m scripts.cli --help

# Ver subcomandos de una categoría
docker-compose exec backend python -m scripts.cli data-sync --help
docker-compose exec backend python -m scripts.cli maint --help
docker-compose exec backend python -m scripts.cli verify --help
docker-compose exec backend python -m scripts.cli admin --help
```

#### 6.6 Scripts Individuales (Deprecated)

Los scripts individuales en `scripts/` aún existen por compatibilidad, pero se recomienda usar el CLI unificado:

| Script Original | Comando Nuevo |
|---|---|
| `trigger_sat_sync.py` | `data-sync sat` |
| `trigger_sync.py` | `data-sync sanctions` |
| `trigger_clustering.py` | `data-sync cluster` |
| `backfill_embeddings.py` | `maint embeddings` |
| `backfill_roles.py` | `maint roles` |
| `fix_alembic.py` | `maint alembic-clean` |
| `verify_users.py` | `verify users` |
| `verify_search.py` | `verify search` |
| `reset_password.py` | `admin reset-password` |

---

### 7. Generacion de Diagramas para Tesis (Capitulo 3)

Se agrego un pipeline reproducible para generar 4 diagramas requeridos por `SEMINARIO2/Capitulo3.tex`:

- `fig3_01_arquitectura_global.png`
- `fig3_04_deployment_docker.png`
- `fig3_06_seq_search_hibrida.png`
- `fig3_07_seq_ai_chat.png`

Archivos fuente:

- Script principal: `scripts/generate_thesis_diagrams.py`
- Mermaid editable:
    - `docs/diagrams/fig3_06_seq_search_hibrida.mmd`
    - `docs/diagrams/fig3_07_seq_ai_chat.mmd`

Comando de ejecucion:

```bash
python scripts/generate_thesis_diagrams.py
```

Prerequisitos:

```bash
pip install -r requirements-dev.txt
npm i -g @mermaid-js/mermaid-cli
```

Salida final:

- Los PNG intermedios se generan en `docs/diagrams/out/`
- Los PNG finales se copian automaticamente a `../SEMINARIO2/Imagenes/`

---

---

## Guía Completa de Despliegue

### Ambiente de Pre-Producción

La guía anterior (`docker-compose up`) es adecuada para **desarrollo**. Para **staging y producción**, usar:

```bash
# Despliegue completamente automatizado con backups
bash scripts/deploy.sh staging
# o
bash scripts/deploy.sh production
```

**¿Qué hace `deploy.sh`?**
1. Valida prerequisitos (docker, git, .env)
2. Realiza backup automático de BD
3. Actualiza código desde git
4. Construye imágenes Docker con cambios
5. Ejecuta migraciones Alembic
6. Inicia servicios con health checks
7. Valida endpoints de API
8. Automáticamente revierte en caso de fallo

### Procedimiento de Rollback de Emergencia

Si una actualización falla, revertir usando:

```bash
# Rollback de BD a backup anterior
bash scripts/rollback.sh backups/pld_backend_20260220_040000.sql

# Rollback de código a commit anterior
bash scripts/rollback.sh HEAD~1
```

### Inicializar con Datos de Prueba

Después del primer despliegue:

```bash
docker-compose exec backend python scripts/seed_database.py
```

Usuarios de prueba creados:
- `admin@example.com` / `password123` (superuser)
- `analyst@example.com` / `password456` (consultant)
- `auditor@example.com` / `password789` (auditor)

**⚠️  Cambiar credenciales inmediatamente en producción**

### Variables de Entorno Requeridas

Ver [.env.example](.env.example) para la lista completa. Como mínimo:

```bash
# Seguridad
SECRET_KEY=your-random-secret-here
OPENAI_API_KEY=sk-your-key-here

# Base de Datos
POSTGRES_PASSWORD=your-secure-password

# Opcional - Frontend CORS
BACKEND_CORS_ORIGINS=http://localhost:3000,https://frontend.example.com
```

### Monitoreo Post-Despliegue

```bash
# Ver logs en tiempo real
docker-compose logs -f backend

# Verificar salud de servicios
docker-compose ps

# Teste de humo (smoke test)
curl http://localhost:8000/health
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/audit-logs
```

---

## 7. Gestión de Migraciones de Base de Datos (Alembic)

Las migraciones schema se gestionan con **Alembic**, garantizando versionado y reproducibilidad del estado de la BD.

### 7.1 Primeras Migraciones (Startup)

Cuando inicies por primera vez o después de resetear:

```bash
# Aplicar todas las migraciones
docker-compose exec backend alembic upgrade head

# Si hay error de "migración no encontrada", limpiar primero:
docker-compose exec backend python -m scripts.cli maint alembic-clean
docker-compose exec backend alembic upgrade head
```

### 7.2 Crear Nueva Migración (Desarrollo)

```bash
# Después de modificar modelos en `app/models/`
docker-compose exec backend alembic revision --autogenerate -m "descripcion de cambios"

# Aplicar la migración
docker-compose exec backend alembic upgrade head
```

### 7.3 Historial y Estado de Migraciones

```bash
# Ver migración actual
docker-compose exec backend alembic current

# Ver historial de migraciones
docker-compose exec backend alembic history
```

### 7.4 Problemas Comunes

| Problema | Solución |
|----------|----------|
| `relation already exists` | `docker-compose exec backend python -m scripts.cli maint alembic-clean` + `alembic upgrade head` |
| `Can't locate revision` | Tabla de migraciones corrupta, usar `alembic-clean` |
| Migraciones locales no se aplican | Recrear volumen: `docker-compose down -v` + `docker-compose up -d --build` |

---

## 8. AI Chat y Módulo de Inteligencia

El sistema incluye un módulo RAG (Retrieval-Augmented Generation) para análisis conversacional de entidades y sanciones:

### 8.1 Endpoints de Chat IA Disponibles

- `POST /api/v1/intelligence/sessions` - Crear nueva sesión de investigación
- `GET /api/v1/intelligence/sessions` - Listar sesiones del usuario
- `GET /api/v1/intelligence/sessions/{session_id}/messages` - Historial de mensajes
- `POST /api/v1/intelligence/sessions/{session_id}/messages` - Enviar prompt y recibir análisis
- `POST /api/v1/intelligence/sessions/{session_id}/attachments` - Adjuntar evidencia
- `GET /api/v1/intelligence/sessions/{session_id}/attachments` - Listar evidencias
- `POST /api/v1/intelligence/sessions/{session_id}/export` - Exportar expediente (PDF/JSON)
- `POST /api/v1/audit/ai-events` - Registrar evento IA para auditoría

### 8.2 Formato de Respuesta de Análisis

```json
{
  "message_id": 8,
  "analysis": "Análisis detallado generado por IA...",
  "context": {
    "source": {
      "name": "Lista OFAC SDN",
      "organization": "OFAC",
      "snippet": "Información relevante extraída"
    },
    "related_entities": [
      {"name": "Entity A", "relationship": "asociada", "type": "company"}
    ]
  },
  "usage": {
    "prompt_tokens": 1200,
    "completion_tokens": 350,
    "latency_ms": 2100
  },
  "model_version": "gpt-4-turbo",
  "created_at": "2026-02-19T16:05:10Z"
}
```

---

## 9. API de Búsqueda Inteligente

El sistema expone un endpoint unificado para búsqueda de sanciones:

`GET /api/v1/search/sanctions?q={nombre}`

### Estrategia de Búsqueda (3 Capas)
1.  **Exacta**: Coincidencia directa con `ILIKE`.
2.  **Difusa (Fuzzy)**: Utiliza trigramas (`pg_trgm`) para tolerar errores tipográficos (ej. "Gomez" vs "Gomes").
### 3. Vectorial (Semántica): Utiliza embeddings de OpenAI y `pgvector` para encontrar coincidencias conceptuales o variaciones complejas. *Requiere configurar `OPENAI_API_KEY`*.

## 10. Endpoints Adicionales

Además de la búsqueda, el sistema ofrece endpoints para gestión y auditoría:

*   **Auditoría (`/api/v1/audit-logs`)**: Permite a los administradores consultar el historial de acciones.
*   **Entidades (`/api/v1/entities`)**: Gestión CRUD de entidades y disparadores manuales para su procesamiento y vectorización.

## 11. Despliegue y Ejecución con Docker

El sistema está completamente contenerizado. A continuación se detallan los comandos para la gestión del ciclo de vida de los contenedores.

#### Comandos Útiles

*   **Levantar servicios**:
    ```bash
    docker-compose up -d --build
    ```
*   **Ver logs**:
    ```bash
    docker-compose logs -f
    ```
*   **Ejecutar scripts manuales (ej. Sincronización)**:
    Para ejecutar scripts que requieren acceso a la base de datos o Redis, debes correrlos **dentro** del contenedor `backend`:
    ```bash
    docker-compose exec backend python scripts/trigger_sync.py
    ```
    *Esto ejecutará la sincronización de listas sin necesidad de configuración local.*

*   **Entrar a la consola del contenedor**:
    ```bash
    docker-compose exec backend bash
    ```

*   **Iniciar el entorno (Build & Run)**:
    Este comando construye las imágenes (si hubo cambios) y levanta los servicios en segundo plano.
    ```bash
    docker-compose up --build -d
    ```

*   **Actualizar cambios**:
    Si modificas el código fuente, es necesario reconstruir los contenedores para reflejar los cambios:
    ```bash
    docker-compose up --build -d
    ```
    *Nota: Gracias al Dockerfile optimizado, solo se reconstruirán las capas que hayan cambiado.*

*   **Ver logs**:
    Para monitorear la salida de todos los servicios:
    ```bash
    docker-compose logs -f
    ```
    O de un servicio específico (ej. `worker`):
    ```bash
    docker-compose logs -f worker
    ```

*   **Detener el entorno**:
    ```bash
    docker-compose down
    ```

---

## 12. Estrategia Avanzada de Enriquecimiento (RAG para Cumplimiento)

Para aumentar la explicabilidad y reducir falsos positivos en screening PLD/FT, el backend sigue y extiende este enfoque:

1. **Enriquecimiento por Fuente y Estatus Legal**
    - **ONU**: además del match nominal, priorizar explicación de causalidad de inclusión mediante resumen narrativo del comité correspondiente.
    - **México (SABG/PDN S3)**: distinguir naturaleza de la falta, firmeza de resolución, autoridad resolutora y vigencia de inhabilitación.
    - **SAT 69-B**: tratar explícitamente estatus `Presunto`, `Definitivo`, `Desvirtuado`, `Sentencia Favorable` para separar riesgo alto vs mitigado.

2. **Contexto Recuperable para RAG (Grounded)**
    - Indexar texto enriquecido narrativo, no solo filas tabulares.
    - Incluir siempre identificador de evidencia (RFC, referencia/oficio, data_id) para trazabilidad.
    - Exigir en salida del modelo una síntesis con fuentes y advertencia de ambigüedad por homonimia.

3. **Controles Anti-Alucinación**
    - Respuestas únicamente con base en contexto recuperado.
    - Prohibición de inferir delitos no explicitados en registros oficiales.
    - Solicitar identificador único (RFC/referencia/fecha de nacimiento) cuando la búsqueda sea ambigua.

4. **Roadmap de Integración Externa (Siguiente Fase)**
    - Conector de resúmenes narrativos ONU por prefijo de referencia (QDi/QDe, TAi/TAe, etc.).
    - Conector PDN S3 para metadatos jurídicos de sanción firme.
    - Enlace DOF por número de oficio SAT para explicación de causalidad administrativa.
    - (Opcional) Agregación de entidades y vínculos con OpenSanctions para cobertura internacional y PEP.

Este enfoque permite que el sistema responda no solo **si** existe una coincidencia, sino también **por qué**, **con qué evidencia** y **con qué nivel de riesgo operativo/legal**.

---

## Enlaces relacionados

### Documento de tesis Google Docs
https://docs.google.com/document/d/1_FkgUz1kroUEUxOYc9tY1YGw7hadGMCo/edit?usp=sharing&ouid=117129143776158652215&rtpof=true&sd=true


### Figma
https://www.figma.com/design/vklVs1Dog1P2WgnDREba1h/PLD-FT?node-id=0-1&t=SXKX9OUfKaSOomU1-1

---