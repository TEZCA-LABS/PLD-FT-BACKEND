#!/usr/bin/env python
"""
Quick test script to validate PDF export functionality
"""
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.intelligence_service import build_pdf_from_payload

def test_pdf_export():
    """Test PDF export with sample data"""
    
    # Sample payload with test data
    test_payload = {
        "session": {
            "id": 1,
            "title": "Análisis de Entidades - Juan Carlos Araiza",
            "status": "completed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "initial_context": "Búsqueda de sanciones OFAC para persona natural mexicana"
        },
        "messages": [
            {
                "id": 1,
                "role": "user",
                "content": "¿Está Juan Carlos Araiza Arambula en las listas de sanciones internacionales?",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "model_version": "gpt-4-turbo"
            },
            {
                "id": 2,
                "role": "assistant",
                "content": """Según las búsquedas realizadas en las bases de datos de sanciones internacionales:

**Resultados de Búsqueda:**
- OFAC (Oficina de Control de Activos Extranjeros - EE.UU.): No se encontraron coincidencias directas
- Lista de Sanciones de la UE: No aparece en los registros
- ONU (Naciones Unidas): No presente en listas UNSC
- Banco de Datos Nacional: Se encontraron 3 registros con información fiscal relacionada

**Conclusión:** No se ha encontrado evidencia de que esta persona esté sometida a sanciones internacionales. Se recomienda realizar búsquedas periódicas y validar la información con fuentes oficiales.""",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "model_version": "gpt-4-turbo",
                "context": {
                    "source": {
                        "name": "OFAC Database",
                        "organization": "U.S. Treasury",
                        "date": "2025-05-10",
                        "snippet": "Search result from OFAC SDN list",
                        "url": "https://www.treasury.gov/ofac"
                    },
                    "related_entities": [
                        {"name": "Araiza Holdings S.A.", "relation": "Empresa Asociada", "type": "corporate"},
                        {"name": "Carlos Araiza Moreno", "relation": "Familiar", "type": "person"}
                    ]
                }
            },
            {
                "id": 3,
                "role": "user",
                "content": "¿Hay conexiones con empresas vinculadas a lavado de dinero?",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "model_version": "gpt-4-turbo"
            },
            {
                "id": 4,
                "role": "assistant",
                "content": """Análisis de conexiones empresariales:

**Empresas Asociadas Identificadas:**
1. Araiza Holdings S.A. - Establecida 2015, Sector: Importaciones
2. Comercio Internacional Araiza - Establecida 2018, Sector: Trading
3. Soluciones Logísticas CA - Establecida 2017, Sector: Logística

**Indicadores de Riesgo:**
- Bajo: Empresas operan en sectores de comercio internacional
- Moderado: Múltiples cambios de directivos en 2022
- Bajo: Cumplimiento tributario consistente

**Recomendación:** Se sugiere monitoreo periódico y validación de documentación de origen de fondos en transacciones mayores a USD 100,000.""",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "model_version": "gpt-4-turbo"
            }
        ],
        "sources": [
            {
                "name": "OFAC SDN List",
                "organization": "U.S. Treasury Department",
                "date": "2025-05-10",
                "url": "https://www.treasury.gov/ofac/sdn"
            },
            {
                "name": "EU Consolidated List",
                "organization": "European Commission",
                "date": "2025-05-10",
                "url": "https://ec.europa.eu/info/business-economy-euro/banking-and-finance/international-relations/sanctions_en"
            },
            {
                "name": "Registro Público Mercantil",
                "organization": "SERCOMEX México",
                "date": "2025-05-09",
                "url": "https://www.sercomex.gob.mx"
            }
        ],
        "entities": [
            {
                "name": "Juan Carlos Araiza Arambula",
                "relation": "Sujeto Principal",
                "type": "person"
            },
            {
                "name": "Araiza Holdings S.A.",
                "relation": "Empresa Controlada",
                "type": "corporate"
            },
            {
                "name": "Comercio Internacional Araiza",
                "relation": "Empresa Asociada",
                "type": "corporate"
            },
            {
                "name": "Carlos Araiza Moreno",
                "relation": "Familiar - Padre",
                "type": "person"
            },
            {
                "name": "Soluciones Logísticas CA",
                "relation": "Empresa del Grupo",
                "type": "corporate"
            }
        ],
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "module": "intelligence"
        }
    }
    
    print("=" * 60)
    print("TEST: PDF Export with FPDF2")
    print("=" * 60)
    
    try:
        print("\n1. Generando PDF con datos de prueba...")
        pdf_bytes = build_pdf_from_payload(test_payload)
        
        print("OK - PDF generado exitosamente")
        print(f"  Tamano: {len(pdf_bytes)} bytes")
        
        # Save to file for manual inspection
        output_path = Path(__file__).parent / "test_output.pdf"
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        
        print(f"OK - PDF guardado en: {output_path}")
        print(f"\n2. Validaciones:")
        print(f"  - Tipo de contenido: {type(pdf_bytes)}")
        print(f"  - Primeros bytes (PDF header): {pdf_bytes[:4]}")
        
        # Check PDF header
        if pdf_bytes.startswith(b'%PDF'):
            print(f"  OK - PDF header valido")
        else:
            print(f"  ERROR - PDF header invalido")
            return False
        
        # Check for common PDF structures
        if b'%EOF' in pdf_bytes:
            print(f"  OK - EOF marker encontrado")
        
        print("\n" + "=" * 60)
        print("OK - TEST COMPLETADO EXITOSAMENTE")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_pdf_export()
    sys.exit(0 if success else 1)
