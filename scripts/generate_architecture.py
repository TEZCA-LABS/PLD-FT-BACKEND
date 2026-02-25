"""
Script de Generación de Diagrama de Arquitectura (Diagram-as-Code)
Para el backend de PLD-FT (Prevención de Lavado de Dinero).

Requisitos:
    - pip install diagrams
    - Instalación de Graphviz en el sistema (ej. apt install graphviz)
"""

from diagrams import Diagram, Cluster, Edge
from diagrams.onprem.database import PostgreSQL
from diagrams.onprem.inmemory import Redis
from diagrams.onprem.compute import Server
from diagrams.onprem.queue import Celery
from diagrams.programming.framework import Fastapi
from diagrams.programming.language import Python
from diagrams.onprem.client import Users
from diagrams.custom import Custom

def generate_diagram():
    # Atributos del gráfico (Graphviz)
    graph_attr = {
        "fontsize": "20",
        "bgcolor": "white"
    }

    with Diagram("Arquitectura Backend PLD-FT", 
                 show=False, 
                 filename="docs/architecture_diagram", 
                 direction="LR", 
                 graph_attr=graph_attr):
        
        user = Users("Usuarios Finales")
        cli = Python("Administrador (CLI)")

        with Cluster("Ecosistema de Contenedores (Docker)"):
            api = Fastapi("FastAPI Backend")
            worker = Celery("Celery Worker")
            db = PostgreSQL("PostgreSQL + pgvector")
            broker = Redis("Redis (Broker)")

            # Flujos internos
            api >> Edge(label="SQL / vector search") >> db
            api >> Edge(label="Push Task") >> broker
            broker >> Edge(label="Pop Task") >> worker
            worker >> Edge(label="Update Metadata/Embeddings") >> db

        with Cluster("Servicios de Inteligencia y External APIs"):
            # Usar iconos genéricos para evitar dependencias de archivos locales inexistentes
            openai = Python("OpenAI (LLM/Embeddings)") 
            
            # Fuentes de Datos Externas
            with Cluster("Fuentes de Sanciones"):
                un = Server("UN Sanctions (XML)")
                sat = Server("SAT 69-B (CSV)")
                mex = Server("MEX SABG (CSV)")

        # Conexiones externas
        user >> api
        cli >> db # Acceso directo para scripts de mantenimiento
        
        # Inteligencia Artificial
        api >> Edge(color="orange", style="dashed", label="RAG / Chat") << openai
        worker >> Edge(color="orange", style="dashed") << openai
        
        # Sincronización de Datos
        worker >> Edge(label="Sync") << [un, sat, mex]

if __name__ == "__main__":
    try:
        generate_diagram()
        print("Diagrama generado exitosamente en 'docs/architecture_diagram.png'")
    except ImportError:
        print("Error: La librería 'diagrams' no está instalada. Ejecute 'pip install diagrams' e instale Graphviz.")
    except Exception as e:
        print(f"Error generando diagrama: {e}")
