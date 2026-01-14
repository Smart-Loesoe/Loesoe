from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import asyncpg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("loesoe.memory")

router = APIRouter(tags=["memory"])

# -------------------------
# Helpers: DB / pool
# -------------------------

_pool: Optional[asyncpg.Pool] = None


def _dsn_for_asyncpg() -> str:
    """
    Jouw app gebruikt DATABASE_URL met postgresql+asyncpg:// ...
    asyncpg wil postgresql:// (zonder +asyncpg).
    """
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL not set")

    # strip driver suffix for asyncpg
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = "postgresql://" + dsn.split("postgresql+asyncpg://", 1)[1]
    return dsn


async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        dsn = _dsn_for_asyncpg()
        _pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=1,
            max_size=5,
            command_timeout=30,
        )
        logger.info("[memory] asyncpg pool created")
        await _ensure_schema(_pool)
    return _pool


async def _ensure_schema(pool: asyncpg.Pool) -> None:
    sql = """
    CREATE TABLE IF NOT EXISTS memory_kv (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'api',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """
    async with pool.acquire() as conn:
        await conn.execute(sql)
    logger.info("[memory] schema ensured")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# -------------------------
# Schemas
# -------------------------

class MemorySetIn(BaseModel):
    key: str = Field(..., min_length=1, max_length=200)
    value: str = Field(..., min_length=0)  # unicode-safe string (emoji OK)
    source: Optional[str] = Field(default="api", max_length=50)


class MemoryItem(BaseModel):
    key: str
    value: str
    source: str
    updated_at: str


class MemorySetOut(BaseModel):
    ok: bool
    key: str


class MemoryDeleteOut(BaseModel):
    ok: bool
    key: str


class MemoryAllOut(BaseModel):
    count: int
    items: Dict[str, MemoryItem]


# -------------------------
# Routes
# -------------------------

@router.get("/memory/all", response_model=MemoryAllOut)
async def memory_all() -> MemoryAllOut:
    pool = await _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT key, value, source, updated_at FROM memory_kv ORDER BY updated_at DESC"
        )

    items: Dict[str, MemoryItem] = {}
    for r in rows:
        items[r["key"]] = MemoryItem(
            key=r["key"],
            value=r["value"],
            source=r["source"],
            updated_at=r["updated_at"].isoformat() if r["updated_at"] else _utc_now(),
        )

    return MemoryAllOut(count=len(items), items=items)


@router.get("/memory/get/{key}", response_model=MemoryItem)
async def memory_get(key: str) -> MemoryItem:
    pool = await _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT key, value, source, updated_at FROM memory_kv WHERE key=$1",
            key,
        )

    if not row:
        raise HTTPException(status_code=404, detail="Key not found")

    return MemoryItem(
        key=row["key"],
        value=row["value"],
        source=row["source"],
        updated_at=row["updated_at"].isoformat() if row["updated_at"] else _utc_now(),
    )


@router.post("/memory/set", response_model=MemorySetOut)
async def memory_set(payload: MemorySetIn) -> MemorySetOut:
    # ⚠️ Belangrijk: FastAPI/Pydantic parseert JSON als UTF-8 → emoji blijft heel.
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO memory_kv(key, value, source, updated_at)
            VALUES ($1, $2, COALESCE($3,'api'), NOW())
            ON CONFLICT (key) DO UPDATE
            SET value=EXCLUDED.value,
                source=EXCLUDED.source,
                updated_at=NOW()
            """,
            payload.key,
            payload.value,
            payload.source,
        )

    return MemorySetOut(ok=True, key=payload.key)


@router.delete("/memory/delete/{key}", response_model=MemoryDeleteOut)
async def memory_delete(key: str) -> MemoryDeleteOut:
    pool = await _get_pool()
    async with pool.acquire() as conn:
        res = await conn.execute("DELETE FROM memory_kv WHERE key=$1", key)

    # asyncpg returns like: "DELETE 1"
    ok = res.endswith("1")
    return MemoryDeleteOut(ok=ok, key=key)
