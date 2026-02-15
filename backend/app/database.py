from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import AsyncGenerator

from app.config import settings

# Async engine (for FastAPI endpoints)
async_engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=20,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an async session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Sync engine (for Celery tasks)
sync_engine = create_engine(
    settings.sync_database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=5,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    expire_on_commit=False,
)


@contextmanager
def get_sync_db():
    """Context manager: yields a sync session for Celery tasks."""
    session: Session = SyncSessionLocal()
    try:
        yield session
    finally:
        session.close()
