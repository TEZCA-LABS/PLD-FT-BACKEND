from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from app.db.base import Base

class AuditLog(Base):
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    action = Column(String, nullable=False, index=True) # e.g., "SEARCH_SANCTIONS"
    details = Column(JSON, nullable=True) # {"query": "...", "ip": "...", "results_count": 5}
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
