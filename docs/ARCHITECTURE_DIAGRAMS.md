# Arquitectura del Sistema: Diagram-as-Code (DaC)

Este documento implementa el paradigma de **Diagram-as-Code (DaC)** para el backend de PLD-FT, garantizando que la documentación visual sea versionable y se mantenga sincronizada con el código fuente.

---

## 1. Diagrama de Contenedores y Flujos (Mermaid)

Este diagrama representa cómo interactúan los componentes principales del backend con los usuarios, la base de datos y los servicios externos de Inteligencia Artificial y listas de sanciones.

```mermaid
graph TD
    %% Usuarios y Presentación
    User((Usuario Final)) -->|HTTPS/JSON| API[FastAPI Backend]
    Admin((Administrador)) -->|CLI| Scripts[Scripts/CLI]

    subgraph "Infraestructura Local (Docker/On-Prem)"
        API -->|SQL/vector| DB[(PostgreSQL + pgvector)]
        API -->|Tasks| Broker(Redis)
        
        Broker -->|Queue| Worker[Celery Worker]
        Worker -->|Metadata/Embeddings| DB
        
        Scripts -->|Direct Access| DB
    end

    subgraph "Servicios de Inteligencia (Generativo)"
        API <-->|Embeddings/LLM| OpenAI[OpenAI API]
        Worker <-->|RAG Pre-processing| OpenAI
    end

    subgraph "Fuentes de Datos (External Sanctions)"
        Worker -->|Fetch XML| UN[UN Sanctions]
        Worker -->|Fetch CSV| SAT[SAT 69-B]
        Worker -->|Fetch CSV| MEX[Mexico SABG]
    end

    %% Estilos
    style API fill:#f9f,stroke:#333,stroke-width:2px
    style DB fill:#77f,stroke:#333,stroke-width:2px
    style OpenAI fill:#fa0,stroke:#333,stroke-width:2px
    style Worker fill:#9f9,stroke:#333,stroke-width:2px
```

---

## 2. Flujo de Procesamiento RAG (Retrieval-Augmented Generation)

Visualización del proceso de búsqueda semántica y enriquecimiento de inteligencia para el análisis de entidades.

```mermaid
sequenceDiagram
    participant User as Usuario
    participant API as API v1/Intelligence
    participant PG as PostgreSQL (pgvector)
    participant LLM as OpenAI (GPT-4)

    User->>API: POST /sessions/{sid}/messages (Prompt)
    API->>LLM: Crear Embedding de la Consulta
    LLM-->>API: Vector de Consulta
    API->>PG: Búsqueda Semántica (vector similarity <->)
    PG-->>API: Documentos Relevantes (Sanctions/Entities)
    API->>LLM: Prompt Enriquecido (Contexto + Pregunta)
    LLM-->>API: Respuesta Generada (Análisis PLD)
    API-->>User: Respuesta JSON con Evidencia
```

---

## 3. Estrategia de Implementación DaC con Python

Siguiendo la guía técnica redactada, el proyecto adopta las siguientes herramientas para la automación de diagramas:

1.  **Diagrams (Python Library):** Utilizada para generar diagramas de infraestructura de alto nivel mediante código Python.
    - Script: `scripts/generate_architecture.py`
    - Requerimientos: `pip install diagrams` y `graphviz` instalado en el sistema.
2.  **Mermaid.js:** Integrado directamente en este documento Markdown para visualización rápida en plataformas como GitHub/GitLab sin dependencias externas.
3.  **Docker-Compose-Diagram:** Recomendado para visualizar automáticamente la topología de contenedores a partir de `docker-compose.yml`.

---

## 4. Generación Programática con "Diagrams"

Para generar el diagrama de infraestructura oficial dentro del contenedor:

**IMPORTANTE:** Si recibes un error de `Permission denied: '/nonexistent'`, es necesario recrear el contenedor primero para aplicar el fix del `Dockerfile` (que crea un $HOME válido):

```bash
docker-compose up --build -d
```

Una vez reconstruido:

```bash
# 1. Instalar dependencias de Python necesarias (vía --user por seguridad)
docker-compose exec backend pip install --user diagrams graphviz mermaid-py

# 2. Ejecutar el script generador
docker-compose exec backend python scripts/generate_architecture.py
```

*Nota:* He actualizado el [Dockerfile](/home/drachenbc/programacion/TEZCA-LABS/PLD-FT-BACKEND/Dockerfile) para incluir el binario de los servicios de sistema (`graphviz`) y configurar una ruta de usuario persistente (`/home/appuser`).

---

## 5. Análisis de Mitigación de Entropía Documental

Siguiendo el informe técnico, la implementación de este ecosistema en **PLD-FT-BACKEND** aborda los siguientes puntos críticos:

### A. Sincronización con el Ciclo de Vida (CI/CD)
Al definir la infraestructura en Python (`scripts/generate_architecture.py`), el diagrama se convierte en un artefacto que se valida y actualiza en cada **Pull Request**. Los cambios en el `docker-compose.yml` deben reflejarse en el script de diagramas para que la documentación nunca quede obsoleta ("doc-rot").

### B. Mapeo del Ecosistema Docker
El uso de `docker-compose-diagram` permite extraer la topología real declarada para los servicios `db`, `redis`, `backend` y `worker`, visualizando puertos y dependencias de red de forma automática.

### C. Visualización de Inteligencia (RAG)
Dada la complejidad del módulo RAG (`app/services/intelligence_service.py`), el uso de **Mermaid** permite documentar los flujos de secuencia que involucran a `pgvector` y `OpenAI` detallando la latencia y la procedencia de datos (Groundedness), lo cual es vital para el cumplimiento regulatorio (Explainability).

### D. Modelo C4 para Auditoría
Para los stakeholders de cumplimiento (compliance), se recomienda el uso de **Buildzr** para generar vistas de Contexto que muestren cómo el sistema se integra legalmente con las listas de la ONU y el SAT, eliminando el ruido técnico innecesario para estas áreas mediante una abstracción de alto nivel.
