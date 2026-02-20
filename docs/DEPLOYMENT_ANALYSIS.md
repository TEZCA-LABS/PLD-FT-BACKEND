# 📋 Análisis de Despliegue y Mantenimiento - PLD-FT Backend

**Fecha:** 2026-02-20  
**Estado:** Funcional pero requiere mejoras para producción

---

## 1. 🚨 PROBLEMAS CRÍTICOS (Must Fix)

### 1.1 Versionado de Dependencias
**Problema:** `requirements.txt` NO tiene versiones pinned
```txt
fastapi          # ❌ Cualquier versión
sqlalchemy       # ❌ Puede romper migraciones
asyncpg          # ❌ Incompatibilidad con PostgreSQL
```

**Impacto:** 
- Builds no reproducibles (diferente imagen cada vez)
- Compatibilidad rota entre componentes
- Imposible diagnosticar problemas en producción

**Solución:** Usar `pip freeze` + versionado semántico

---

### 1.2 Credenciales Hardcoded en Configuración
**Problema:** `config.py` tiene valores inseguros por defecto
```python
SECRET_KEY: str = "key"                    # ❌ Predecible
MASTER_PASSWORD: str = "admin_master_secret"    # ❌ En código fuente
FIRST_SUPERUSER_PASSWORD: str = "admin"   # ❌ Contraseña trivial
```

**Impacto:**
- Vulnerabilidad de seguridad en desarrollo
- Riesgo de exfiltración si código se filtra
- No hay protección en primer despliegue

**Solución:** 
- Variables de entorno obligatorias
- Validación que fuerza cambio en producción
- `.env.example` sin credenciales

---

### 1.3 Sin Gestión de Variables `.env`
**Problema:** No hay archivo `.env` o `.env.example`

**Impacto:**
- Desarrolladores no saben qué variables configurar
- Fácil perder configuración entre deployments
- Docker variables en `docker-compose.yml` sin documentación

**Solución:** Crear `.env.example` con todas las variables requeridas

---

### 1.4 Migraciones Alembic Sin Rollback Automático
**Problema:** Migraciones fallidas no se revierten automáticamente

**Impacto:**
- Estado inconsistente de BD después de fallo de migración
- Difícil recuperarse en producción
- Sin manera clara de revertir cambios

**Solución:**
- Script pre-deployment de validación
- Documentar rollback procedure
- Health checks post-migración

---

## 2. ⚠️ PROBLEMAS MAYORES (Should Fix)

### 2.1 Health Checks Faltantes
**Problema:** Ni Dockerfile ni docker-compose tienen health checks

**Impacto:**
- Contenedor "running" pero servicio no disponible
- Docker Swarm/Kubernetes no detectan fallos
- Deploys fallidos se resuelven solos
- Sin métricas de disponibilidad

**Solución:**
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
```

---

### 2.2 Sin Reinicio Automático en `docker-compose.yml`
**Problema:** Si contenedor crashea, no se reinicia

```yaml
# ❌ Sin restart policy
backend:
  build: .
  ports:
    - "8000:8000"
```

**Solución:**
```yaml
restart_policy:
  condition: on-failure
  delay: 5s
  max_attempts: 3
```

---

### 2.3 Port Conflicts y Networking
**Problema:** Todos los servicios exponen puertos al host
```yaml
ports:
  - "5432:5432"  # ❌ DB accesible desde afuera
  - "6379:6379"  # ❌ Redis accesible desde afuera
  - "8000:8000"  # ✅ API (correcto)
```

**Impacto:**
- Riesgos de seguridad (acceso no autorizado a DB interna)
- Conflictos de puertos entre proyectos
- Configuración no portable

**Solución:**
```yaml
services:
  db:
    expose:  # 👈 Solo red interna
      - 5432
  # backend/worker acceden vía hostname "db"
```

---

### 2.4 Sin Logging Centralizado
**Problema:** Logs solo en stdout, no hay rotación/persistencia

**Impacto:**
- Logs se pierden cuando contenedor stop
- Sin correlación entre componentes (backend/worker/db)
- Imposible auditar en producción

**Solución:**
- Usar `python-json-logger` para structured logs
- Volume para persistencia de logs
- ELK Stack o similar para centralización

---

### 2.5 Sin Monitoreo de Tareas Celery
**Problema:** No hay visibility en worker tasks

**Impacto:**
- Tasks fallidas sin detección
- Sin SLAs medibles
- Imposible saber si clustering/sync completó

**Solución:**
- Celery Flower para monitoreo
- Dead letter queues para errores
- Alertas en tareas fallidas

---

## 3. 📦 MEJORAS DE INFRAESTRUCTURA

### 3.1 CI/CD Pipeline Faltante
**Problema:** No hay automatización de tests, build, deploy

**Solución Recomendada:**
```yaml
# .github/workflows/ci-cd.yml
- Lint (pylint, black)
- Test (pytest)
- Build imagen Docker
- Push a registry
- Deploy automático a staging/production
```

---

### 3.2 Dockerfile No Optimizado
**Problemas:**
```dockerfile
FROM python:3.11-slim  # ✅ Bien (slim)
# ❌ Falta versión específica: 3.11.0 vs 3.11-latest
```

**Mejoras:**
```dockerfile
# Usar versión específica
FROM python:3.11.8-slim

# Agregar labels de metadatos
LABEL maintainer="team@example.com"
LABEL version="1.0.0"

# Optimizar capas (agrupar RUN commands)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      gcc build-essential \
    && rm -rf /var/lib/apt/lists/*

# Cachear requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```

---

### 3.3 Base de Datos sin Backups Documentados
**Problema:** `postgres_data` volume no tiene estrategia de backup

**Solución:**
- Datos en `/var/lib/postgresql/data`
- Script de backup: `pg_dump > pld_backend_$(date +%Y%m%d).sql`
- Restore procedure documentada

---

### 3.4 Sin Datos de Prueba (Seed Scripts)
**Problema:** Nuevo developer/staging sin datos iniciales

**Solución:**
```bash
scripts/seed_database.py  # Crea usuarios, datos de prueba
```

---

## 4. 🔐 SEGURIDAD

### 4.1 CORS no Configurado Correctamente
**Problema:** `BACKEND_CORS_ORIGINS` no definido en `config.py`

```python
# ❌ Falta en config.py
BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = ["*"]  # INSEGURO!
```

**Solución:**
```python
BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = [
    "http://localhost:3000",      # Desarrollo
    "https://frontend.example.com"  # Producción
]
```

---

### 4.2 Assets Sin Versionado en URLs
**Problema:** No hay SRI (Subresource Integrity) si se usan CDNs

---

### 4.3 Sin Rate Limiting
**Problema:** Endpoints sin protección contra abuso

**Solución:**
```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@app.get("/api/v1/search")
@limiter.limit("10/minute")
async def search():
    pass
```

---

## 5. 📊 OBSERVABILIDAD

### 5.1 Métricas Faltantes
**Problema:** Sin Prometheus/OpenTelemetry

**Impacto:** No hay visibilidad operacional

---

### 5.2 Tracing Distribuido Falta
**Problema:** Sin correlationID entre requests/tasks/logs

**Solución:**
- Usar `python-opentelemetry`
- Propagar X-Trace-ID en headers
- Correlacionar en ELK/Datadog

---

## 6. 🧪 TESTING

### 6.1 Sin Suite de Tests de Integración
**Problema:** Tests solo unitarios, sin cobertura E2E

---

### 6.2 Sin Load Testing
**Problema:** Sin baseline de capacidad

**Solución:** `locust` para load testing

---

## 7. 📄 PROCESOS OPERACIONALES

### 7.1 Sin Runbook de Deployment
**Problema:** Pasos manuales propensos a error

**Solución Recomendada:**
```bash
# deploy.sh
set -e
git pull origin main
docker-compose build
alembic upgrade head
docker-compose up -d
healthcheck.sh
```

---

### 7.2 Sin Documentación de Rollback
**Problema:** Cómo revertir en caso de emergencia?

**Solución:**
```bash
# Revertir última migración
alembic downgrade -1

# Revertir a versión anterior de imagen
docker-compose pull  # de registry con git tag
docker-compose up -d
```

---

### 7.3 Cambios en `docker-compose.yml` no versionados
**Problema:** Sin history de cambios de infraestructura

**Solución:** Guardar en git con changelog

---

## 8. 📋 DOCUMENTACIÓN

### 8.1 Falta Documentación de Despliegue
**Problema:** README no tiene section de "Deployment"

**Solución Recomendada:**
```markdown
## 12. Despliegue en Producción

### Ambiente
- Requerimientos: Docker 20.10+, Docker Compose 2.0+
- Variables de entorno: Ver `.env.example`

### Pre-Deployment
1. Backup de BD: `docker-compose exec db pg_dump ...`
2. Validar migraciones: `docker-compose run backend alembic current`
3. Tests: `docker-compose run backend pytest`

### Deployment
1. `git pull origin main`
2. `docker-compose build`
3. `docker-compose up -d db redis`
4. `docker-compose run backend alembic upgrade head`
5. `docker-compose up -d backend worker`

### Post-Deployment
1. Health check: `curl http://localhost:8000/health`
2. Smoke tests
3. Monitor logs: `docker-compose logs -f backend`
```

---

### 8.2 Falta Documentación de CLI
**Problema:** Scripts consolidados pero sin man pages

**Solución:** Auto-generar docs desde Click
```bash
python -m scripts.cli --help > docs/CLI_REFERENCE.md
```

---

## 9. 🛠️ QUICK FIXES (1-2 horas cada uno)

| # | Tarea | Prioridad | Esfuerzo |
|---|-------|-----------|---------|
| 1 | Pin versions en requirements.txt | 🔴 CRÍTICA | 30 min |
| 2 | Crear `.env.example` | 🔴 CRÍTICA | 20 min |
| 3 | Agregar health checks | 🟠 ALTA | 45 min |
| 4 | Agregar restart policies | 🟠 ALTA | 15 min |
| 5 | Crear deploy.sh runbook | 🟠 ALTA | 1 hora |
| 6 | Agregar rate limiting | 🟡 MEDIA | 1 hora |
| 7 | Crear `seed_database.py` | 🟡 MEDIA | 1.5 horas |
| 8 | Agregar CORS config | 🟡 MEDIA | 30 min |

---

## 10. 🏗️ ARQUITECTURA FUTURA

### 10.1 Kubernetes Ready
**Tendencia:** Migrar de Docker Compose a K8s

**Pre-requisitos:**
- Helm charts
- ConfigMaps para configuración
- Secrets para credenciales
- Resource requests/limits
- Liveness/readiness probes

### 10.2 Infrastructure as Code
**Herramientas:** Terraform/CloudFormation
- Provisionar RDS en lugar de Docker DB
- Elastic Cache para Redis
- ALB para load balancing

---

## 11. 🎯 RECOMENDACIONES PRIORIZADAS

### FASE 1 (Esta semana) 🔴
1. [ ] Pin versions `requirements.txt`
2. [ ] Create `.env.example`
3. [ ] Adicionar health checks
4. [ ] Adicionar restart policies
5. [ ] Create `deploy.sh`

### FASE 2 (Este mes) 🟠
6. Crear CI/CD pipeline básico
7. Adicionar rate limiting
8. Logging centralizado
9. Seed data scripts
10. Documentación de deployment

### FASE 3 (Q2 2026) 🟡
11. Monitoring con Prometheus
12. Tracing distribuido
13. Load testing
14. Kubernetes migration prep
15. Backup/restore automation

---

## 📚 ARCHIVOS POR CREAR/MODIFICAR

```
PLD-FT-BACKEND/
├── requirements.txt              [MODIFICAR] - agregar versiones
├── .env.example                  [CREAR] - template de variables
├── .env.production               [CREAR] - para secrets de prod
├── docker-compose.yml            [MODIFICAR] - health checks, restart policies
├── Dockerfile                    [MODIFICAR] - versión específica de Python
├── deploy.sh                     [CREAR] - deployment automation
├── scripts/backup.sh             [CREAR] - BD backup script
├── scripts/rollback.sh           [CREAR] - emergency rollback
├── scripts/seed_database.py      [CREAR] - datos de prueba
├── docs/DEPLOYMENT.md            [CREAR] - deployment runbook
├── docs/ARCHITECTURE.md          [CREAR] - tech decisions
├── .github/workflows/ci-cd.yml   [CREAR] - GitHub Actions
├── alembic.ini                   [MODIFICAR] - validations
└── app/core/config.py            [MODIFICAR] - variables obligatorias
```

---

**Próximo paso recomendado:** Implementar FASE 1 para asegurar reproducibilidad y seguridad básica en producción.
