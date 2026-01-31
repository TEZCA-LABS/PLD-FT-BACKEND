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
            ("system", "Eres un Asistente de Cumplimiento Normativo (AI Compliance Assistant) especializado en PLD/FT (Prevención de Lavado de Dinero / Financiamiento al Terrorismo). "
                       "Tu tarea es analizar los resultados de búsqueda de las siguientes listas de sanciones:\n"
                       "1. Lista Consolidada del Consejo de Seguridad de las Naciones Unidas (Fuente: UN_CONSOLIDATED)\n"
                       "2. Lista de Personas Bloqueadas de México (Fuente: MEX_SANCIONADOS)\n\n"
                       "Analiza los resultados proporcionados contra la consulta del usuario."),
            ("user", "Consulta del Usuario: {query}\n\n"
                     "Resultados de Búsqueda:\n{results}\n\n"
                     "Por favor, proporciona un resumen conciso en ESPAÑOL.\n"
                     "1. Indica si hay una coincidencia probable basada en la similitud del nombre y la fuente.\n"
                     "2. Si hay coincidencias, resalta la más relevante, indicando claramente la fuente (ONU o México) y el programa/causa.\n"
                     "3. Asume que el usuario es un oficial de cumplimiento verificando a un cliente.\n"
                     "Mantén un tono profesional y breve.")
        ])

        # Chain
        chain = prompt | llm | StrOutputParser()

        # Execute
        response = await chain.ainvoke({"query": query, "results": results_text})
        
        return response

    except Exception as e:
        logger.error(f"Error in LLM analysis: {e}")
        return f"Error generating analysis: {str(e)}"
