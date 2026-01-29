import asyncio
import sys
import os

# Add parent directory to Python path to ensure 'app' module is found
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import select
from app.db.session import async_session
from app.models.user import User
from app.core.security import get_password_hash

async def reset_password(email: str, new_password: str):
    async with async_session() as session:
        result = await session.execute(select(User).filter(User.email == email))
        user = result.scalars().first()
        
        if not user:
            print(f"Error: User with email '{email}' not found.")
            return

        print(f"Found user: {user.email} (ID: {user.id})")
        
        hashed_password = get_password_hash(new_password)
        user.hashed_password = hashed_password
        
        session.add(user)
        await session.commit()
        
        print(f"Successfully reset password for {email}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python reset_password.py <email> <new_password>")
        sys.exit(1)
        
    email_arg = sys.argv[1]
    password_arg = sys.argv[2]
    
    # Run async function
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(reset_password(email_arg, password_arg))
