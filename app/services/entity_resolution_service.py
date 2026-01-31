from typing import List, Tuple
import logging
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text, func, or_
from app.models.sanction import Sanction
from app.models.entity_profile import EntityProfile
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.core.config import settings

logger = logging.getLogger(__name__)

async def get_potential_matches(db: AsyncSession, limit: int = 20) -> List[Tuple[Sanction, Sanction]]:
    """
    Finds pairs of Sanctions that might be the same person but are not yet linked to the same profile.
    Simple heuristic: Same RFC (strong) or fuzzy name match (weak).
    For now, we verify un-clustered records.
    """
    # 1. Strong Match: Same RFC, different source
    # This is a bit complex in pure SQL async. 
    # Let's start with a simpler approach: Find records with same RFC
    
    # We will focus on one un-clustered record at a time for this MVP service
    result = await db.execute(
        select(Sanction).where(Sanction.profile_id == None).limit(limit)
    )
    unresolved_sanctions = result.scalars().all()
    
    pairs = []
    
    for s1 in unresolved_sanctions:
        # Check for RFC match
        if s1.rfc:
            stmt = select(Sanction).where(
                Sanction.rfc == s1.rfc, 
                Sanction.id != s1.id
            )
            res = await db.execute(stmt)
            matches = res.scalars().all()
            for m in matches:
                pairs.append((s1, m))
                
        # Check for Fuzzy Name match (if available in DB)
        # For simplicity in this logic, we use ILIKE/pg_trgm if we had it.
        # Here we skip complex fuzzy DB search to avoid perf issues in loop, 
        # relying on vector search in a real batch job.
        
    return pairs

async def resolve_entity_pair(s1: Sanction, s2: Sanction) -> bool:
    """
    Uses LangChain to determine if two sanctions are the same person.
    Returns True if they are unique and same.
    """
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "sk-placeholder":
        return False
        
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=settings.OPENAI_API_KEY)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert Anti-Money Laundering (AML) analyst. "
                   "Determine if the following two Sanction entries refer to the SAME individual/entity."),
        ("user", """
        Entity A:
        Name: {name_a}
        Source: {source_a}
        RFC: {rfc_a}
        Aliases: {aliases_a}
        Program: {program_a}
        
        Entity B:
        Name: {name_b}
        Source: {source_b}
        RFC: {rfc_b}
        Aliases: {aliases_b}
        Program: {program_b}
        
        Are they the same person? Reply ONLY with 'YES' or 'NO'.
        """)
    ])
    
    chain = prompt | llm | StrOutputParser()
    
    try:
        response = await chain.ainvoke({
            "name_a": s1.entity_name, "source_a": s1.source, "rfc_a": str(s1.rfc or ""), "aliases_a": str(s1.aliases or ""), "program_a": s1.program,
            "name_b": s2.entity_name, "source_b": s2.source, "rfc_b": str(s2.rfc or ""), "aliases_b": str(s2.aliases or ""), "program_b": s2.program,
        })
        
        return "YES" in response.strip().upper()
        
    except Exception as e:
        logger.error(f"Error in entity resolution AI: {e}")
        return False

async def cluster_entities(db: AsyncSession):
    """
    Main entry point to find and cluster entities.
    """
    # 1. Simple RFC Clustering (Deterministic)
    logger.info("Starting RFC clustering...")
    await cluster_by_rfc(db)
    
    # 2. (Future) Fuzzy/AI Clustering
    # This requires iterating candidates.

async def cluster_by_rfc(db: AsyncSession):
    """
    Automatically cluster records with the same RFC.
    """
    # Find RFCs that appear in multiple records
    stmt = select(Sanction.rfc).where(Sanction.rfc != None).group_by(Sanction.rfc).having(func.count(Sanction.id) > 1)
    result = await db.execute(stmt)
    duplicate_rfcs = result.scalars().all()
    
    for rfc in duplicate_rfcs:
        # Get all records with this RFC
        sanctions = (await db.execute(select(Sanction).where(Sanction.rfc == rfc))).scalars().all()
        
        # Check if they belong to a profile
        existing_profile_id = None
        for s in sanctions:
            if s.profile_id:
                existing_profile_id = s.profile_id
                break
        
        if not existing_profile_id:
            # Create new profile
            primary = sanctions[0]
            new_profile = EntityProfile(id=uuid4(), primary_name=primary.entity_name)
            db.add(new_profile)
            await db.flush() # Get ID
            existing_profile_id = new_profile.id
            
        # Assign all to profile
        for s in sanctions:
            if s.profile_id != existing_profile_id:
                s.profile_id = existing_profile_id
                db.add(s)
                
    await db.commit()
