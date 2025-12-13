
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from app.core.config import settings
from app.services.rag.vectorstore import search_similar_entities

# Prompt designed to reduce hallucinations
RAG_PROMPT = """
Eres un analista experto en PLD (Prevención de Lavado de Dinero).
Responde la consulta basándote ÚNICAMENTE en el siguiente contexto proporcionado.
Si la información no está en el contexto, indica que no hay registros.

Contexto:
{context}

Consulta: {question}
"""

async def retrieve_context(question: str):
    """
    Retrieve context from vector store and format it as a string.
    """
    results = await search_similar_entities(question)
    if not results:
        return "No hay registros encontrados."
    
    context_str = "\n\n".join([f"Nombre: {doc.name}\nFuente: {doc.source}\nDetalle: {doc.content}" for doc in results])
    return context_str

def get_rag_chain():
    llm = ChatOpenAI(model="gpt-4-turbo", temperature=0, api_key=settings.OPENAI_API_KEY)
    prompt = ChatPromptTemplate.from_template(RAG_PROMPT)
    
    # We construct the chain manually to handle the async retrieval
    # In a full LangChain setup, we would wrap search_similar_entities in a Retriever
    
    chain = (
        prompt
        | llm
        | StrOutputParser()
    )
    return chain
