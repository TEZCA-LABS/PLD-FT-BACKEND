from celery.utils.log import get_task_logger
import asyncio
import httpx
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.celery_app import celery_app
from app.core.config import settings
# from app.db.session import engine # Removed global engine import
from app.services.sanction_service import sync_sanctions_data

logger = get_task_logger(__name__)

@celery_app.task(name="sync_un_sanctions_task")
def sync_un_sanctions_task():
    """
    Celery task to:
    1. Download the UN Sanctions XML.
    2. Run the async synchronization service.
    """
    logger.info("Starting UN Sanctions Sync Task...")
    
    try:
        # Download XML
        response = httpx.get(settings.UN_SANCTIONS_XML_URL, timeout=60.0, follow_redirects=True)
        response.raise_for_status()
        xml_content = response.content
        logger.info(f"Downloaded XML successfully. Size: {len(xml_content)} bytes")
        
        # Run Async Logic in Sync Task
        asyncio.run(run_sync_logic(xml_content))
        
        logger.info("UN Sanctions Sync Task Completed Successfully.")
        return "Sync Successful"
        
    except Exception as e:
        logger.error(f"Error in UN Sanctions Sync Task: {e}")
        # In a real scenario, you might want to retry:
        # raise self.retry(exc=e)
        raise e

from sqlalchemy.ext.asyncio import create_async_engine

# ... (imports)

async def run_sync_logic(xml_content: bytes):
    """
    Helper to run async service logic from sync task.
    Creates a dedicated engine to avoid event loop conflicts in Celery.
    """
    # Create a fresh engine for this task execution
    # This prevents "Future attached to a different loop" errors because
    # the global engine's pool might be tied to a closed loop.
    local_engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI, future=True, echo=True)
    
    local_async_session = sessionmaker(
        local_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    try:
        async with local_async_session() as session:
            result = await sync_sanctions_data(session, xml_content)
            logger.info(f"Sync Result: {result}")
    finally:
        # Crucial: Dispose the engine to close connections
        await local_engine.dispose()
