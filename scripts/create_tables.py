"""
Script to create all database tables in Neon or any PostgreSQL database.
Supports both async (asyncpg) and sync (psycopg2) modes.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def create_tables_sync(database_url: str):
    """Create tables using synchronous SQLAlchemy (psycopg2)."""
    from sqlalchemy import create_engine
    from app.models import Base
    
    sync_url = database_url.replace('+asyncpg', '')
    if "ssl=require" in sync_url:
        sync_url = sync_url.replace("ssl=require", "sslmode=require")
    
    print(f"Connecting to database (sync mode)...")
    engine = create_engine(sync_url, echo=False)
    
    print("Creating all tables...")
    Base.metadata.create_all(engine)
    print("[SUCCESS] All tables created successfully!")
    
    engine.dispose()


async def create_tables_async(database_url: str):
    """Create tables using async SQLAlchemy (asyncpg)."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.models import Base
    
    print(f"Connecting to database (async mode)...")
    connect_args = {}
    if "asyncpg" in database_url:
        connect_args["statement_cache_size"] = 0

    engine = create_async_engine(database_url, echo=False, connect_args=connect_args)
    
    async with engine.begin() as conn:
        print("Creating all tables...")
        await conn.run_sync(Base.metadata.create_all)
        print("[SUCCESS] All tables created successfully!")
    
    await engine.dispose()


def main():
    from app.config import settings
    
    database_url = settings.database_url
    
    print(f"\n{'='*50}")
    print("Insightyfy - Database Table Creator")
    print(f"{'='*50}\n")
    
    use_sync = '--sync' in sys.argv or 'psycopg2' in sys.argv
    
    if use_sync:
        print("Using SYNC mode (psycopg2)...")
        create_tables_sync(database_url)
    else:
        print("Using ASYNC mode (asyncpg)...")
        import asyncio
        asyncio.run(create_tables_async(database_url))


if __name__ == "__main__":
    main()
