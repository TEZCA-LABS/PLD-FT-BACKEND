# Documentación Técnica: Sincronización de Sanciones ONU

## Descripción General
Este módulo implementa la descarga, parseo y sincronización automatizada de la "Lista Consolidada de Sanciones del Consejo de Seguridad de las Naciones Unidas" (UN Consolidated Sanctions List).

El objetivo es mantener una base de datos local actualizada de individuos y entidades sancionadas para realizar procesos de PLD/FT (Prevención de Lavado de Dinero y Financiamiento al Terrorismo).

## Componentes Principales

### 1. Modelo de Datos (`Sanction`)
*   **Archivo**: `app/models/sanction.py`
*   **Propósito**: Representa un registro de sanción en la base de datos.
*   **Cambios Recientes**:
    *   Se agregaron campos para almacenar la estructura XML completa: `data_id` (ID único de la ONU), `un_list_type`, `reference_number`, `designation`, `aliases`, `addresses`, `birth_dates`, `birth_places`, etc.
    *   Los campos de lista (como alias o direcciones) se almacenan como `JSON` para preservar la estructura.

### 2. Servicio de Sincronización (`SanctionService`)
*   **Archivo**: `app/services/sanction_service.py`
*   **Función Clave**: `sync_sanctions_data(db, xml_content)`
*   **Lógica de Negocio**:
    1.  **Parseo**: Utiliza `app/services/xml_handler.py` para convertir el XML en diccionarios Python.
    2.  **Upsert (Crear/Actualizar)**:
        *   Itera sobre cada registro del XML.
        *   Si el `data_id` ya existe en la BD, actualiza sus campos.
        *   Si no existe, crea un nuevo registro.
    3.  **Eliminación (Soft/Hard Delete)**:
        *   Identifica los `data_id` presentes en la base de datos pero ausentes en el XML recién descargado.
        *   Elimina estos registros para garantizar que la BD local sea un "espejo" fiel de la lista oficial.

### 3. Tarea Automatizada (Celery)
*   **Archivo**: `app/tasks/sanctions_tasks.py`
*   **Tarea**: `sync_un_sanctions_task`
*   **Flujo**:
    1.  Descarga el XML desde la URL oficial (`https://scsanctions.un.org/...`).
    2.  Maneja redirecciones HTTP (302).
    3.  Crea un motor de base de datos asíncrono dedicado (`create_async_engine`) para evitar conflictos de *event loops* dentro del worker.
    4.  Ejecuta la lógica de `SanctionService`.

### 4. Scheduler (Celery Beat)
*   **Archivo**: `app/core/celery_app.py`
*   **Configuración**: La tarea está programada para ejecutarse el **día 1 de cada mes a la medianoche**.

## Ejecución Manual
Para forzar una sincronización fuera del horario programado, se puede utilizar el script `trigger_sync.py` en la raíz del proyecto.

```bash
# Ejecutar desde el host (Windows/Linux)
# Requiere definir REDIS_URL para apuntar a localhost
$env:REDIS_URL="redis://localhost:6379/0"; python trigger_sync.py
```
