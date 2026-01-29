from sqlalchemy import Column, Integer, String, Date, JSON, Text
from app.db.base import Base

class Sanction(Base):
    id = Column(Integer, primary_key=True, index=True)
    entity_name = Column(String, index=True) # Mapped from FIRST_NAME + SECOND_NAME etc
    
    # XML Specific Fields
    data_id = Column(String, unique=True, index=True, nullable=True) # DATAID
    un_list_type = Column(String, index=True, nullable=True) # UN_LIST_TYPE
    reference_number = Column(String, index=True, nullable=True) # REFERENCE_NUMBER
    listed_on = Column(Date, nullable=True) # LISTED_ON
    
    # Personal Info
    gender = Column(String, nullable=True) # GENDER
    nationality = Column(String, nullable=True) # NATIONALITY/VALUE
    
    # Details lists stored as JSON
    designation = Column(JSON, nullable=True) # DESIGNATION/VALUE list
    aliases = Column(JSON, nullable=True) # INDIVIDUAL_ALIAS list
    addresses = Column(JSON, nullable=True) # INDIVIDUAL_ADDRESS list
    birth_dates = Column(JSON, nullable=True) # INDIVIDUAL_DATE_OF_BIRTH
    birth_places = Column(JSON, nullable=True) # INDIVIDUAL_PLACE_OF_BIRTH
    documents = Column(JSON, nullable=True) # INDIVIDUAL_DOCUMENT
    
    remarks = Column(Text, nullable=True) # COMMENTS1
    
    # Metadata
    program = Column(String, nullable=True) 
    source = Column(String, default="UN_CONSOLIDATED") 
    sanction_date = Column(Date, nullable=True) # Kept for compatibility, can mirror listed_on
    last_updated = Column(Date, nullable=True) # LAST_DAY_UPDATED
    
    # Vector Search
    from pgvector.sqlalchemy import Vector
    embedding = Column(Vector(1536)) # OpenAI text-embedding-ada-002 dimension
