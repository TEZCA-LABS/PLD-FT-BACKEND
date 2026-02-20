"""
Shared utilities for CLI scripts.
Centralized setup for database, logging, and async handling.
"""
import sys
import os
import asyncio
import logging
from typing import Callable

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Logger setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def setup_asyncio_policy():
    """Fix Windows asyncio event loop policy."""
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def get_async_session_maker():
    """Create AsyncSession maker for scripts."""
    engine = create_async_engine(
        settings.SQLALCHEMY_DATABASE_URI,
        future=True,
        echo=False
    )
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    return async_session, engine


def async_runner(func: Callable) -> Callable:
    """Decorator to run async function with proper event loop setup."""
    def wrapper(*args, **kwargs):
        setup_asyncio_policy()
        return asyncio.run(func(*args, **kwargs))
    return wrapper


async def get_db_session():
    """Context manager to get a fresh DB session."""
    async_session, engine = get_async_session_maker()
    try:
        async with async_session() as session:
            yield session
    finally:
        await engine.dispose()
