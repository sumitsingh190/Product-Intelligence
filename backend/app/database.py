from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, MappedColumn, mapped_column
from sqlalchemy import DateTime, func
from datetime import datetime

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_size = settings.db_pool_size,
    max_overflow = settings.db_max_overflow,
    pool_timeout = settings.db_pool_timeout,
    pool_recycle = settings.db_pool_recycle,
    echo = settings.debug,
    future = True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit = False,
    autocommit=False,
    autoflush=False,
)

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at : MappedColumn[datetime] = mapped_column(
        DateTime(timezone=True), server_default = func.now(), nullable = False
    )

    updated_at : MappedColumn[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def drop_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)