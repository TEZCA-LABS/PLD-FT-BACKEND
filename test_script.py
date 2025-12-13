
import asyncio
import sys
from app.db.session import async_session
from app.services.user_service import create_user
from app.schemas.user_schema import UserCreate

async def main():
    print("Starting test...", flush=True)
    async with async_session() as db:
        try:
            print("Creating user...", flush=True)
            user_in = UserCreate(email='test_debug@test.com', password='admin')
            print(f"UserIn password: {user_in.password}", flush=True)
            await create_user(db, user_in)
            print("User created successfully!", flush=True)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr, flush=True)
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
