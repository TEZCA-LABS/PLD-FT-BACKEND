from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text
from sqlalchemy.sql import func

from app.db.base import Base


class AIChatMessage(Base):
    __tablename__ = "ai_chat_message"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("ai_chat_session.id"), nullable=False, index=True)
    role = Column(String, nullable=False, index=True)  # user | assistant
    content = Column(Text, nullable=False)
    context = Column(JSON, nullable=True)
    usage = Column(JSON, nullable=True)
    model_version = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
