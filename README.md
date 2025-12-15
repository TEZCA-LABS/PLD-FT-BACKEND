# Documentación Técnica: Arquitectura Backend PLD/FT

**Versión:** 1.0
**Fecha:** 13 de Diciembre, 2025

---

## 1. Resumen Ejecutivo

Este documento detalla la arquitectura, decisiones de diseño y protocolos de implementación del sistema Backend para la Prevención de Lavado de Dinero y Financiamiento al Terrorismo (PLD/FT). El sistema está diseñado como una solución híbrida que integra procesamiento transaccional tradicional con capacidades avanzadas de Inteligencia Artificial (RAG - Retrieval-Augmented Generation) para el análisis de entidades y sanciones.

## 2. Arquitectura del Sistema

El sistema sigue un patrón de **Arquitectura Limpia Modular (Modular Clean Architecture)**, priorizando la separación de responsabilidades, la escalabilidad y la mantenibilidad.

### 2.1 Diagrama de Componentes

### 2.1 Descripción Arquitectónica General

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
| **Docker** | Garantiza la consistencia del entorno entre desarrollo, pruebas y producción, encapsulando todas las dependencias del sistema. |

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

---
