#!/usr/bin/env python
"""
Database seed script - populates initial test data
Usage: python scripts/seed_database.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import async_session
from app.models.user import User
from app.core.security import get_password_hash
from sqlalchemy import select


async def seed_users():
    """Create initial test users"""
    async with async_session() as session:
        try:
            # Check if users already exist
            result = await session.execute(select(User))
            existing_users = result.scalars().all()

            if existing_users:
                print(f"✓ Database already has {len(existing_users)} users. Skipping seed.")
                return

            print("Creating seed users...")

            # Superuser
            superuser = User(
                email="admin@example.com",
                hashed_password=get_password_hash("password123"),
                is_active=True,
                is_superuser=True,
                role="admin",
            )

            # Regular analyst
            analyst = User(
                email="analyst@example.com",
                hashed_password=get_password_hash("password456"),
                is_active=True,
                is_superuser=False,
                role="consultant",
            )

            # Auditor
            auditor = User(
                email="auditor@example.com",
                hashed_password=get_password_hash("password789"),
                is_active=True,
                is_superuser=False,
                role="auditor",
            )

            session.add(superuser)
            session.add(analyst)
            session.add(auditor)

            await session.commit()

            print("✓ Seed users created:")
            print(f"  - Admin: admin@example.com / password123")
            print(f"  - Analyst: analyst@example.com / password456")
            print(f"  - Auditor: auditor@example.com / password789")
            print("\n⚠️  Change these passwords in production!")

        except Exception as e:
            await session.rollback()
            print(f"✗ Error creating seed users: {e}")
            raise


async def main():
    print("PLD-FT Backend - Database Seeding")
    print("=" * 50)
    
    try:
        await seed_users()
        print("\n✓ Database seeding completed successfully!")
    except Exception as e:
        print(f"\n✗ Seeding failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
