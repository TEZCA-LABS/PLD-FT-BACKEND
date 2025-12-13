
from sqlalchemy import Column, Integer, String, Date
from app.db.base import Base

class Sanction(Base):
    id = Column(Integer, primary_key=True, index=True)
    entity_name = Column(String, index=True)
    program = Column(String) # e.g. SDNTK
    source = Column(String) # e.g. OFAC
    sanction_date = Column(Date, nullable=True)
    nationality = Column(String, nullable=True)
    remarks = Column(String, nullable=True)
