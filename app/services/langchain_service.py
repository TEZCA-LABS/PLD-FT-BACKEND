from typing import List, Dict, Any
import logging
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.core.config import settings

logger = logging.getLogger(__name__)

async def analyze_search_results(query: str, results: List[Any]) -> str:
    """
    Analyzes the search results using an LLM to provide a natural language summary.
    """
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "sk-placeholder":
        return "LLM analysis unavailable (API Key not set)."

    if not results:
        return f"No results found for '{query}'. The individual/entity does not appear in the sanctions list based on the search criteria."

    try:
        # Format results for the prompt
        results_text = ""
        for i, res in enumerate(results, 1):
            results_text += f"{i}. Name: {res.get('entity_name')}, Source: {res.get('source')}, Program: {res.get('program')}, ID: {res.get('reference_number')}\n"

        # Initialize LLM
        llm = ChatOpenAI(
            model="gpt-4o-mini", # Cost-effective model
            temperature=0,
            api_key=settings.OPENAI_API_KEY
        )

        # Create Prompt
        prompt = ChatPromptTemplate.from_messages([
                        ("system", "Eres un Asistente de Cumplimiento Normativo especializado en PLD/FT. "
                                             "Analiza únicamente los resultados entregados, sin inferir hechos externos ni afirmar delitos. "
                                             "Distingue el estatus SAT 69-B cuando aparezca (Presunto, Definitivo, Desvirtuado, Sentencia favorable). "
                                             "Si hay homónimos o falta de identificador, indica que el resultado no es concluyente y solicita RFC o referencia."),
            ("user", "Consulta del Usuario: {query}\n\n"
                     "Resultados de Búsqueda:\n{results}\n\n"
                                         "Entrega una respuesta concisa en ESPAÑOL y formato de 3 bloques:\n"
                                         "1) Resultado de screening (probable / no concluyente / sin coincidencias).\n"
                                         "2) Evidencia clave (fuente y referencia principal).\n"
                                         "3) Riesgo preliminar (alto/medio/bajo) con nota de cautela si aplica.\n"
                                         "Máximo 140 palabras.")
        ])

        # Chain
        chain = prompt | llm | StrOutputParser()

        # Execute
        response = await chain.ainvoke({"query": query, "results": results_text})
        
        return response

    except Exception as e:
        logger.error(f"Error in LLM analysis: {e}")
        return f"Error generating analysis: {str(e)}"
