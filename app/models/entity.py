
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from app.db.base import Base

class EntityDocument(Base):
    __tablename__ = "entity_documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # Basic entity data (extracted from sanction lists)
    name: Mapped[str] = mapped_column(String, index=True)
    source: Mapped[str] = mapped_column(String) # e.g., "OFAC", "UIF"
    
    # Full textual content for RAG context generation
    content: Mapped[str] = mapped_column(Text)
    
    # Vector embedding (1536 dimensions for OpenAI text-embedding-3-small)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))

    def __repr__(self):
        return f"<EntityDocument(name={self.name}, source={self.source})>"
