"""
Unified CLI for database maintenance, data sync, verification, and admin tasks.

Usage:
    python -m scripts.cli --help
    python -m scripts.cli data-sync sat
    python -m scripts.cli maint embeddings
    python -m scripts.cli verify users
"""
import sys
import os
import asyncio
import click
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import select, text
from app.core.config import settings
from app.models.sanction import Sanction
from app.models.user import User
from app.services.sat_service import sync_sat_sanctions_data
from app.services.search_service import search_sanctions, get_embedding
from app.services.user_service import (
    get_user_by_email, create_user, delete_user,
    get_multi_users
)
from app.services.entity_resolution_service import cluster_entities
from app.schemas.user_schema import UserCreate
from app.core.security import get_password_hash
from app.tasks.sanctions_tasks import sync_un_sanctions_task, sync_mex_sanctions_task

from scripts.utils import (
    setup_asyncio_policy,
    get_async_session_maker,
    logger
)


@click.group()
def cli():
    """PLD-FT Backend CLI - Database maintenance, data sync, verification & admin."""
    setup_asyncio_policy()


# ============================================================================
# DATA SYNC COMMANDS
# ============================================================================
@cli.group('data-sync')
def data_sync():
    """Synchronize data from external sources (UN, MEX, SAT sanctions)."""
    pass


@data_sync.command('sat')
@click.option('--verbose', is_flag=True, help='Show detailed logs')
def sync_sat(verbose):
    """Download and sync SAT 69-B sanctions list (direct async)."""
    async def run():
        logger.info("🚀 Starting SAT 69-B Sync...")
        
        try:
            logger.info(f"Downloading from: {settings.SAT_69B_CSV_URL}")
            async with httpx.AsyncClient() as client:
                response = await client.get(settings.SAT_69B_CSV_URL, timeout=60.0)
                response.raise_for_status()
                csv_content = response.content
            
            logger.info(f"✅ Downloaded {len(csv_content) / 1024 / 1024:.2f} MB")
            
            async_session, engine = get_async_session_maker()
            async with async_session() as session:
                result = await sync_sat_sanctions_data(session, csv_content)
                logger.info(f"✅ Sync Result: {result}")
            
            await engine.dispose()
            
        except Exception as e:
            logger.error(f"❌ Error during SAT sync: {e}")
            raise click.ClickException(str(e))
    
    asyncio.run(run())
    click.secho("✅ SAT sync completed successfully.", fg='green')


@data_sync.command('sanctions')
@click.option('--source', type=click.Choice(['un', 'mex', 'all']), default='all',
              help='Sync UN, MEX, or all sanctions')
def sync_sanctions(source):
    """Sync UN and/or Mexican sanctions lists using Celery workers."""
    try:
        tasks = []
        
        if source in ['un', 'all']:
            logger.info("📤 Dispatching UN Sanctions sync to Celery worker...")
            task = sync_un_sanctions_task.delay()
            tasks.append(('UN', task.id))
            logger.info(f"✅ UN Task ID: {task.id}")
        
        if source in ['mex', 'all']:
            logger.info("📤 Dispatching MEX Sanctions sync to Celery worker...")
            task = sync_mex_sanctions_task.delay()
            tasks.append(('MEX', task.id))
            logger.info(f"✅ MEX Task ID: {task.id}")
        
        click.secho("\n✅ Tasks dispatched to workers:", fg='green')
        for name, task_id in tasks:
            click.echo(f"   {name}: {task_id}")
        
        click.echo("\nTo monitor progress, run:")
        click.secho("   docker-compose logs -f worker", fg='cyan')
        
    except Exception as e:
        logger.error(f"❌ Failed to dispatch tasks: {e}")
        raise click.ClickException(f"Redis/Celery unavailable: {e}")


@data_sync.command('cluster')
def cluster_entities_cmd():
    """Cluster entities using entity resolution service (direct async)."""
    async def run():
        logger.info("🚀 Starting Entity Clustering...")
        try:
            async_session, engine = get_async_session_maker()
            async with async_session() as session:
                await cluster_entities(session)
            await engine.dispose()
            logger.info("✅ Clustering complete.")
        except Exception as e:
            logger.error(f"❌ Clustering failed: {e}")
            raise
    
    asyncio.run(run())
    click.secho("✅ Entity clustering completed successfully.", fg='green')


# ============================================================================
# MAINTENANCE COMMANDS
# ============================================================================
@cli.group('maint')
def maint():
    """Database maintenance tasks (backfills, cleanups)."""
    pass


@maint.command('embeddings')
@click.option('--limit', type=int, default=None, help='Limit records to process')
@click.option('--batch-size', type=int, default=10, help='Batch size for commits')
def backfill_embeddings(limit, batch_size):
    """Backfill missing embeddings for sanctions records."""
    async def run():
        logger.info("🚀 Starting embedding backfill...")
        async_session, engine = get_async_session_maker()
        
        try:
            async with async_session() as db:
                stmt = select(Sanction).filter(Sanction.embedding.is_(None))
                if limit:
                    stmt = stmt.limit(limit)
                
                result = await db.execute(stmt)
                sanctions = result.scalars().all()
                logger.info(f"Found {len(sanctions)} records missing embeddings.")
                
                count = 0
                for s in sanctions:
                    count += 1
                    if not s.entity_name:
                        continue
                    
                    try:
                        if count % 5 == 0:
                            logger.info(f"Progress: [{count}/{len(sanctions)}] Processing {s.entity_name}")
                        
                        embedding = await get_embedding(s.entity_name)
                        if embedding:
                            s.embedding = embedding
                        
                        if count % batch_size == 0:
                            await db.commit()
                    except Exception as e:
                        logger.warning(f"Failed for {s.entity_name}: {e}")
                
                await db.commit()
                logger.info(f"✅ Backfill complete. Processed {count} records.")
        finally:
            await engine.dispose()
    
    asyncio.run(run())
    click.secho("✅ Embedding backfill completed successfully.", fg='green')


@maint.command('roles')
def backfill_roles():
    """Backfill NULL user roles with 'consultant' default."""
    async def run():
        logger.info("🚀 Backfilling user roles...")
        async_session, engine = get_async_session_maker()
        
        try:
            async with async_session() as session:
                await session.execute(
                    text('UPDATE "user" SET role = \'consultant\' WHERE role IS NULL')
                )
                await session.commit()
                logger.info("✅ User roles updated.")
        finally:
            await engine.dispose()
    
    asyncio.run(run())
    click.secho("✅ Role backfill completed successfully.", fg='green')


@maint.command('alembic-clean')
@click.confirmation_option(prompt='This will clear the Alembic version table. Continue?')
def clean_alembic():
    """Clear Alembic version table (use before re-stamping migrations)."""
    async def run():
        logger.info("🔧 Cleaning alembic_version table...")
        async_session, engine = get_async_session_maker()
        
        try:
            async with async_session() as session:
                await session.execute(text("DELETE FROM alembic_version"))
                await session.commit()
                logger.info("✅ Alembic version table cleared.")
        finally:
            await engine.dispose()
    
    asyncio.run(run())
    click.secho("✅ Alembic cleaned successfully.", fg='green')


# ============================================================================
# VERIFICATION COMMANDS
# ============================================================================
@cli.group('verify')
def verify():
    """Verify data integrity and functionality."""
    pass


@verify.command('users')
def verify_users_cmd():
    """Verify user CRUD operations."""
    async def run():
        logger.info("🔍 Verifying user operations...")
        async_session, engine = get_async_session_maker()
        
        try:
            async with async_session() as session:
                test_email = "verify_test@example.com"
                
                # Cleanup
                existing = await get_user_by_email(session, test_email)
                if existing:
                    await delete_user(session, user_id=existing.id)
                    logger.info(f"Cleaned up existing user {test_email}")
                
                # Create
                logger.info(f"Creating test user: {test_email}")
                new_user_in = UserCreate(
                    email=test_email,
                    password="testpass123",
                    is_superuser=False,
                    role="consultant"
                )
                created_user = await create_user(session, user=new_user_in)
                logger.info(f"✅ Created: {created_user.email} (ID: {created_user.id})")
                
                # List
                users = await get_multi_users(session, limit=5)
                found = any(u.id == created_user.id for u in users)
                logger.info(f"✅ Listed {len(users)} users. Test user found: {found}")
                
                # Delete
                deleted = await delete_user(session, user_id=created_user.id)
                logger.info(f"✅ Deleted: {deleted.email}")
                
        finally:
            await engine.dispose()
    
    asyncio.run(run())
    click.secho("✅ User verification completed successfully.", fg='green')


@verify.command('search')
def verify_search_cmd():
    """Verify exact-match sanctions search."""
    async def run():
        logger.info("🔍 Verifying search functionality...")
        async_session, engine = get_async_session_maker()
        
        try:
            async with async_session() as session:
                # Test with common entity
                test_query = "GUZMAN"
                logger.info(f"Searching for: '{test_query}'")
                
                results = await search_sanctions(session, test_query)
                logger.info(f"✅ Found {len(results)} results")
                
                if results:
                    for r in results[:3]:
                        logger.info(f"   - {r.entity_name} ({r.source})")
                
        finally:
            await engine.dispose()
    
    asyncio.run(run())
    click.secho("✅ Search verification completed successfully.", fg='green')


@verify.command('embeddings')
@click.option('--id', type=int, multiple=True, help='Check specific record IDs')
def verify_embeddings(id):
    """Verify embeddings exist for sanctions records."""
    async def run():
        logger.info("🔍 Verifying embeddings...")
        async_session, engine = get_async_session_maker()
        
        try:
            async with async_session() as session:
                if id:
                    ids = list(id)
                    stmt = select(Sanction).filter(Sanction.id.in_(ids))
                else:
                    # Sample 5 random records
                    stmt = select(Sanction).limit(5)
                
                result = await session.execute(stmt)
                sanctions = result.scalars().all()
                
                logger.info(f"Checking {len(sanctions)} records:")
                for s in sanctions:
                    has_embedding = s.embedding is not None
                    status = "✅" if has_embedding else "❌"
                    logger.info(
                        f"{status} ID: {s.id}, Name: {s.entity_name}, "
                        f"Has Embedding: {has_embedding}"
                    )
                
        finally:
            await engine.dispose()
    
    asyncio.run(run())


# ============================================================================
# ADMIN COMMANDS
# ============================================================================
@cli.group('admin')
def admin():
    """Administrative operations (passwords, etc)."""
    pass


@admin.command('reset-password')
@click.argument('email')
@click.argument('new_password')
@click.confirmation_option(prompt=f'Reset password for {{email}}? Continue?')
def reset_password(email, new_password):
    """Reset a user's password."""
    async def run():
        logger.info(f"Resetting password for {email}...")
        async_session, engine = get_async_session_maker()
        
        try:
            async with async_session() as session:
                user = await get_user_by_email(session, email)
                
                if not user:
                    raise click.ClickException(f"User '{email}' not found")
                
                user.hashed_password = get_password_hash(new_password)
                session.add(user)
                await session.commit()
                
                logger.info(f"✅ Password reset for {email}")
        finally:
            await engine.dispose()
    
    asyncio.run(run())
    click.secho(f"✅ Password reset for {email} completed successfully.", fg='green')


# ============================================================================
# MAIN
# ============================================================================
if __name__ == '__main__':
    cli()
