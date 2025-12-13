
from sqlalchemy import select
from openai import AsyncOpenAI
from app.db.session import async_session
from app.models.entity import EntityDocument
from app.core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

async def ingest_entity(name: str, description: str, source: str):
    """
    Generate embedding and save entity to database.
    """
    text_to_embed = f"{name}: {description}"
    
    # 1. Call OpenAI to get the vector
    response = await client.embeddings.create(
        input=text_to_embed,
        model="text-embedding-3-small"
    )
    vector_data = response.data[0].embedding # List of 1536 floats

    # 2. Save to Postgres
    async with async_session() as session:
        new_doc = EntityDocument(
            name=name,
            source=source,
            content=text_to_embed,
            embedding=vector_data
        )
        session.add(new_doc)
        await session.commit()

async def search_similar_entities(query_text: str, limit: int = 5):
    """
    Search for similar entities using pgvector.
    """
    # 1. Convert user query to vector
    response = await client.embeddings.create(
        input=query_text,
        model="text-embedding-3-small"
    )
    query_vector = response.data[0].embedding

    async with async_session() as session:
        # 2. Query using pgvector to order by similarity (L2 distance)
        stmt = select(EntityDocument).order_by(
            EntityDocument.embedding.l2_distance(query_vector)
        ).limit(limit)
        
        result = await session.execute(stmt)
        return result.scalars().all()

async def get_retriever(query: str):
    """
    Adapter for LangChain retriever interface if needed, 
    or just return the search results directly.
    For LangChain integration, we might need a custom retriever class,
    but for now we can just use the search function in the chain.
    """
    # This function is a placeholder if we want to use it as a dependency
    return search_similar_entities
