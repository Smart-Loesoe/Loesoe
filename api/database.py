# C:\Loesoe\loesoe\api\database.py
from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv(override=True)

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy import text

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL or "+asyncpg" not in DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be set and use postgresql+asyncpg")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    future=True,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    """
    Minimal ‘auto-migratie’: creëert tabellen als ze nog niet bestaan.
    Veilig voor development; in prod vervang je dit door Alembic.
    """
    from . import models  # ensure models are imported
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
        # sanity ping
        await conn.execute(text("SELECT 1"))
