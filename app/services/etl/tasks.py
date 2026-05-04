
import asyncio
from app.core.celery_app import celery_app
from app.services.etl.normalizer import normalize_text
# In a real scenario, you would import your scraper functions here
# from scrapers.uif_scraper.spiders import run_spider

@celery_app.task
def run_scraper_task(scraper_name: str):
    """
    Trigger a scraper by name.
    This is a placeholder. In production, you might use subprocess to call 'scrapy crawl'
    or use a library like 'scrapyd-client'.
    """
    print(f"Starting scraper: {scraper_name}")
    # Example logic:
    # subprocess.run(["scrapy", "crawl", scraper_name], cwd="scrapers/uif_scraper")
    return f"Scraper {scraper_name} started"

@celery_app.task
def process_entity_data(name: str, source: str, description: str):
    """
    Task to normalize and ingest data into the vector store.
    This should be called by the scraper pipeline.
    """
    # We need to run async code in this sync task
    from app.services.rag.vectorstore import ingest_entity
    
    clean_name = normalize_text(name)
    
    # Celery workers are sync by default; asyncio.run is the safest execution path.
    try:
        asyncio.run(ingest_entity(clean_name, description, source))
    except RuntimeError:
        # Fallback for environments that already own an event loop.
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(ingest_entity(clean_name, description, source))
        finally:
            loop.close()
    
    return f"Processed {clean_name}"
