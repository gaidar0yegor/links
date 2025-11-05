import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from .models import Base


async def create_database_schema(engine):
    """Create all database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def init_database(database_url: str):
    """
    Initialize database with schema.

    Args:
        database_url: PostgreSQL connection URL
    """
    # Create async engine
    engine = create_async_engine(database_url, echo=True)

    try:
        # Create tables
        await create_database_schema(engine)
        print("✅ Database schema created successfully")

        # Test connection
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            print("✅ Database connection test successful")

    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        raise
    finally:
        await engine.dispose()


def get_session_factory(database_url: str) -> sessionmaker:
    """Get SQLAlchemy async session factory."""
    engine = create_async_engine(database_url, echo=False)
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


if __name__ == "__main__":
    # Example usage
    DATABASE_URL = "postgresql+asyncpg://user:password@localhost/telegram_affiliate"

    print("🚀 Initializing database...")
    asyncio.run(init_database(DATABASE_URL))
    print("✅ Database initialization complete")
