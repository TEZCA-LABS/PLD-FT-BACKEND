import asyncio
import sys
from app.db.session import async_session
from app.services.user_service import get_multi_users, create_user, delete_user, get_user_by_email
from app.schemas.user_schema import UserCreate


def log(msg):
    print(msg)
    with open("verification.log", "a", encoding="utf-8") as f:
        f.write(msg + "\n")

async def verify_user_logic():
    # Clear log file
    with open("verification.log", "w", encoding="utf-8") as f:
        f.write("Starting Verification\n")

    async with async_session() as session:
        log("--- 1. Creating Helper User for Test ---")
        test_email = "test_admin_panel@example.com"
        
        # Cleanup first if exists
        existing = await get_user_by_email(session, test_email)
        if existing:
            await delete_user(session, user_id=existing.id)
            log(f"Cleaned up existing user {test_email}")

        # Create
        new_user_in = UserCreate(email=test_email, password="testpassword123", is_superuser=False)
        created_user = await create_user(session, user=new_user_in)
        log(f"Created user: {created_user.email} (ID: {created_user.id})")

        log("\n--- 2. Testing get_multi_users ---")
        users = await get_multi_users(session, limit=5)
        log(f"Found {len(users)} users:")
        for u in users:
             log(f" - ID: {u.id}, Email: {u.email}, Superuser: {u.is_superuser}")
        
        # Verify our user is in the list
        found = any(u.id == created_user.id for u in users)
        if found:
            log("✅ Created user found in list.")
        else:
            log("❌ Created user NOT found in list.")

        log("\n--- 3. Testing delete_user ---")
        deleted_user = await delete_user(session, user_id=created_user.id)
        if deleted_user:
             log(f"✅ Deleted user: {deleted_user.email}")
        else:
             log("❌ Failed to delete user.")

        # Verify deletion
        check_user = await get_user_by_email(session, test_email)
        if not check_user:
            log("✅ Verification confirmed: User is gone from DB.")
        else:
            log("❌ Verification failed: User still exists.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify_user_logic())
