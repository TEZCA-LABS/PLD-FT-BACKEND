# Architecture Decision Records (ADRs)

Este documento registra las decisiones arquitectónicas clave del proyecto PLD-FT Backend.

---

## ADR-001: Stack de Desarrollo - FastAPI, PostgreSQL, Redis, Celery

### Status: Accepted ✓

### Context
Necesitábamos un stack web moderno que permitiera:
- Desarrollo rápido de APIs RESTful
- Manejo escalable de requests asincrónico
- Base de datos relacional con capacidades vectoriales (para RAG)
- Queue de tareas para procesamiento en background

### Decision
Elegimos:
- **FastAPI** para el framework web
- **PostgreSQL + pgvector** para DB relacional + vectorial
- **Redis** como message broker  
- **Celery** para task queue distribuida

### Rationale
- FastAPI: Soporte nativo async/await, validación automática con Pydantic, excelente para microservicios
- PostgreSQL: ACID compliance, extensible (pgvector), no requiere DB separada para embeddings
- Redis + Celery: Patrón proven para task queues, baja latencia, fácil scaling

### Consequences
- ✓ Arquitectura moderna y escalable
- ✓ Menos overhead operacional (una BD vs múltiples)
- ⚠️ Complejidad adicional con async (requiere cuidado en queries)
- ⚠️ Curva de aprendizaje para pgvector vs vectorDBs especializadas

---

## ADR-002: Containerización con Docker Multi-Stage Build

### Status: Accepted ✓

### Context
Necesitábamos despliegue reproducible y consistente en dev/staging/prod.

### Decision
Usar Docker multi-stage build con:
- Stage 1: Compilación (instalar dependencias)
- Stage 2: Runtime (copiar artifacts, no build tools)
- Usuario no-root para seguridad
- Volumen para datos persistentes

### Rationale
- Multi-stage: Reduce tamaño de imagen final (~70% más pequeña)
- No-root user: Mitiga vulnerabilidades de contenedor
- Composable: Mismo Dockerfile para backend y worker

### Consequences
- ✓ Imágenes pequeñas y seguras
- ✓ Build reproducible
- ⚠️ Multi-stage añade complejidad a Dockerfile

---

## ADR-003: Migraciones de BD con Alembic (vs Flyway/Liquibase)

### Status: Accepted ✓

### Context
Necesitábamos versionado de schema de BD con rollback automático.

### Decision
Usar Alembic porque:
- Soporta async SQLAlchemy
- Python-native (menos dependencias externas)
- Autogenerate de migraciones
- Fácil integración con SQLAlchemy ORM

### Rationale
- **Async support**: Crítico para nuestro stack async-first
- **Python**: Consistencia de lenguaje (no otra JVM/Java)
- **Autogenerate**: Reduce boilerplate en nuevas migraciones

### Consequences
- ✓ Migraciones versioadas y reproducibles
- ⚠️ Alembic autogenerate a veces genera cambios incorrectos (requiere revisión)
- ⚠️ Curva de aprendizaje para los nuevos desarrolladores

---

## ADR-004: CLI Unificada con Click vs Scripts Individuales

### Status: Accepted ✓

### Context
Teníamos 11 scripts separados (`trigger_sat_sync.py`, `fix_alembic.py`, etc.) con:
- Código duplicado
- Incompatibles entre sí
- Mantenimiento difícil

### Decision
Consolidar en CLI única con `click` framework:
- 4 command groups: `data-sync`, `maint`, `verify`, `admin`
- 14 subcommands unificados
- Shared utilities (`setup_asyncio_policy`, `get_async_session_maker`)

### Rationale
- **DRY**: Elimina 60% de code duplication
- **Discoverabilidad**: `--help` integrado
- **Consistencia**: Interface estándar para todos los comandos
- **Testeable**: Servicios separados de CLI

### Consequences
- ✓ Mantenimiento más fácil
- ✓ Mejor UX para operadores
- ⚠️ Necesita documentación de migration de scripts antiguos
- ⚠️ Requiere testing de todos los comandos

---

## ADR-005: Seguridad - JWT Tokens + Role-Based Access Control

### Status: Accepted ✓

### Context
Necesitábamos autenticación y autorización con requerimientos PLD/FT:
- Auditoría inmutable de acciones
- Control granular por rol (admin, auditor, consultant, superuser)
- Compliance con regulaciones

### Decision
- **JWT stateless** para autenticación
- **Role-based access control (RBAC)** en endpoints
- **Audit logs** inmutables en cada acción
- **Superuser + Master Password** para creación de nuevos admins

### Rationale
- JWT: Escalable, sin estado, estándar industria
- RBAC: Flexible, explícito, fácil de auditar
- Audit logs: Compliance PLD/FT requiere trazabilidad

### Consequences
- ✓ Seguridad robusta
- ✓ Compliance ready
- ⚠️ Implementación compleja
- ⚠️ Requiere cuidado con expiración de tokens

---

## ADR-006: RAG con LangChain vs Alternativas

### Status: Accepted ✓

### Context
Necesitábamos retrieval-augmented generation para análisis contextual de entidades.

### Decision
Usar LangChain porque:
- Abstrae complejidad de LLMs (OpenAI, local models, etc.)
- Soporta document loaders, vector stores, embeddings
- Comunidad activa y bien documentada
- Python-first

vs. Alternativas descartadas:
- **DSPy**: Todavía en alpha, menos maduro
- **LlamaIndex**: Más enfocado en indexing que en orchestration
- **Custom implementation**: Demasiado overhead

### Rationale
- LangChain es el estándar de facto para RAG
- Extensible (podemos cambiar LLM backend)
- Soporta async operations

### Consequences
- ✓ Implementación rápida de RAG
- ✓ Flexible para cambiar providers
- ⚠️ Overhead de dependencia grande
- ⚠️ API inestable entre versiones

---

## ADR-007: PostgreSQL + pgvector vs Separate Vector Database

### Status: Accepted ✓

### Context
Necesitábamos search semántico (embeddings) junto con datos relacionales.

### Decision
Usar PostgreSQL + pgvector vs bases de datos vectoriales separadas (Pinecone, Weaviate, etc.).

### Rationale
- **Operacional simplicity**: Menos componentes
- **Transactions**: ACID guarantees para consistency
- **Cost**: Menos infraestructura
- **Integridad referencial**: Embeddings siempre sync con datos

vs. Contras:
- ⚠️ Menos optimizado para búsqueda pure-vector a escala
- ⚠️ Escalado horizontal más complejo

### Consequences
- ✓ Arquitectura simple
- ✓ Governance de datos centralizado
- ⚠️ Performance en queries muy grandes puede degradarse
- ⚠️ Migration a VectorDB separada sería compleja

---

## ADR-008: Deployment Automation con Bash Scripts vs Terraform/Helm

### Status: Accepted ✓

### Context
Necesitábamos despliegue reproducible con:
- Backup automático
- Migration management  
- Rollback en caso de fallo

### Decision
Usar bash scripts (`deploy.sh`, `rollback.sh`) en lugar de:
- Terraform (IaaC - demasiado para Docker local)
- Helm (K8s - prematura para esta escala)
- Manual deployment

### Rationale
- Bash: Simple, portable, sin dependencias externas
- Fácil de entender y modificar
- Suficiente para docker-compose deployments
- Transitorio hacia K8s en el futuro

### Consequences
- ✓ Setup deployment en 30 minutos
- ✓ Fácil para pequeños equipos
- ⚠️ No portátil a cloud providers (requeriría Terraform después)
- ⚠️ Escalado manual

**Nota**: Migración a Terraform/K8s podría ser ADR-009

---

## ADR-009: Monitoreo - Logs en stdout vs Centralized Logging

### Status: Pending 🔄

### Context
Actualmente logs van solo a stdout (capturado por docker-compose/container orchestrator).

### Recommended Implementation
Para producción:
- Cambiar a structured logging (JSON format)
- Exportar a central logging (ELK, Datadog, CloudWatch)
- Implementar distributed tracing

### Consequences
- ✓ Observabilidad en producción
- ✓ Debugging más fácil
- ⚠️ Costo adicional de infraestructura
- ⚠️ Complejidad de setup

---

## ADR-010: Rate Limiting

### Status: Pending 🔄

### Context
Actualmente sin protección contra abuso API.

### Recommended Implementation
Agregar slowapi (rate limiter para FastAPI):

```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@app.get("/search")
@limiter.limit("10/minute")
async def search():
    pass
```

### Consequences
- ✓ Protección contra DoS
- ✓ Fair usage entre clientes
- ⚠️ Overhead mínimo de performance

---

## Matriz de Decisiones Futuras

| ADR | Título | Status | Timeline |
|-----|--------|--------|----------|
| 009 | Centralized Logging (ELK/Datadog) | Pending | Q2 2026 |
| 010 | Rate Limiting | Pending | Q1 2026 |
| 011 | Kubernetes Migration | Proposed | Q3 2026 |
| 012 | Multi-tenant Support | Proposed | Q4 2026 |
| 013 | Sharding Strategy | Proposed | 2027+ |

---

## Cambios de Decisiones Anteriores

### Cambio: pgvector vs Pinecone (ADR-007)

**Original (Descartado):** Separar base de datos vectorial a Pinecone
**Razón del cambio:** Complejidad operacional + costo
**Nueva decisión:** pgvector en PostgreSQL (ADR-007 actual)

### Cambio: Scripts Individuales vs CLI Unificada (ADR-004)

**Original (Descartado):** Mantener 11 scripts separados
**Razón del cambio:** Duplicación de código + mantenimiento difícil
**Nueva decisión:** CLI unificada con Click (ADR-004 actual)

---

## Cómo Proponer Nuevas ADRs

1. Crear issue en GitHub: "ADR-XXX: [Título]"
2. Seguir template:
   - Status (Proposed/Pending/Accepted/Rejected)
   - Context
   - Decision
   - Rationale
   - Consequences
3. Revisar con equipo
4. Actualizar este documento

---

**Última Actualización:** 20 de Febrero, 2026  
**Maintainer:** PLD-FT Backend Team
