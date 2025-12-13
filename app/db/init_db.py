
import asyncio
import logging

from app.core.config import settings
from app.db.session import async_session
from app.services.user_service import create_user, get_user_by_email
from app.schemas.user_schema import UserCreate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_db() -> None:
    async with async_session() as db:
        user = await get_user_by_email(db, email=settings.FIRST_SUPERUSER)
        if not user:
            user_in = UserCreate(
                email=settings.FIRST_SUPERUSER,
                password=settings.FIRST_SUPERUSER_PASSWORD,
                is_superuser=True,
                is_active=True,
            )
            user = await create_user(db, user=user_in)
            logger.info(f"Superuser {settings.FIRST_SUPERUSER} created")
        else:
            logger.info(f"Superuser {settings.FIRST_SUPERUSER} already exists")

if __name__ == "__main__":
    asyncio.run(init_db())
