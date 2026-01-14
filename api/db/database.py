# api/db/database.py
from __future__ import annotations

import logging
import os
from typing import Optional

import asyncpg

logger = logging.getLogger("loesoe.db")

# ------------------------------------------------------------
# pgvector is OPTIONAL: als package ontbreekt mag Loesoe niet crashen
# ------------------------------------------------------------
try:
    from pgvector.asyncpg import register_vector  # type: ignore
    _PGVECTOR_OK = True
except Exception:
    register_vector = None  # type: ignore
    _PGVECTOR_OK = False


def _normalize_dsn(dsn: str) -> str:
    """
    asyncpg accepteert alleen:
      - postgresql://
      - postgres://

    SQLAlchemy async gebruikt vaak:
      - postgresql+asyncpg://

    Deterministisch normalizen (geen magic fallback).
    """
    dsn = (dsn or "").strip()
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = "postgresql://" + dsn.split("postgresql+asyncpg://", 1)[1]
    return dsn


async def _init_conn(conn: asyncpg.Connection) -> None:
    """
    Wordt aangeroepen voor ELKE nieuwe connection in de pool.
    Hier registreren we pgvector, maar alleen als het beschikbaar is.
    """
    if _PGVECTOR_OK and register_vector is not None:
        try:
            await register_vector(conn)  # type: ignore[misc]
            logger.info("[db] pgvector registered")
        except Exception as e:
            logger.warning("[db] pgvector register failed (continuing): %s", e)


class Database:
    def __init__(self, dsn: str, min_size: int = 1, max_size: int = 10):
        self.dsn = _normalize_dsn(dsn)
        self.min_size = min_size
        self.max_size = max_size
        self.pool: Optional[asyncpg.pool.Pool] = None

    async def connect(self) -> None:
        """
        Init pool. Safe om meerdere keren te callen.
        """
        if self.pool is not None:
            return

        self.dsn = _normalize_dsn(self.dsn)

        if not self.dsn:
            raise RuntimeError("DATABASE_URL/DSN is empty")

        if not (self.dsn.startswith("postgresql://") or self.dsn.startswith("postgres://")):
            scheme = self.dsn.split("://", 1)[0] if "://" in self.dsn else self.dsn
            raise RuntimeError(
                f"invalid DSN: scheme is expected to be either 'postgresql' or 'postgres', got '{scheme}'"
            )

        self.pool = await asyncpg.create_pool(
            dsn=self.dsn,
            min_size=self.min_size,
            max_size=self.max_size,
            command_timeout=60,
            init=_init_conn,
        )
        logger.info("[db] pool ready (min=%s max=%s)", self.min_size, self.max_size)

    async def close(self) -> None:
        """
        Close pool bij shutdown.
        """
        if self.pool is not None:
            await self.pool.close()
            self.pool = None
            logger.info("[db] pool closed")

    def get_pool(self) -> Optional[asyncpg.pool.Pool]:
        return self.pool

    def acquire(self):
        """
        Compat:
        'async with db.acquire() as conn:'
        """
        if self.pool is None:
            raise RuntimeError("DB pool not initialized. Call connect() first.")
        return self.pool.acquire()


# ------------------------------------------------------------
# Global helpers (legacy compat)
# ------------------------------------------------------------
_db: Optional[Database] = None


async def init_database(
    dsn: Optional[str] = None,
    min_size: Optional[int] = None,
    max_size: Optional[int] = None,
) -> Database:
    """
    Initialiseer (eenmalig) het globale Database-object + bouw de pool.
    .env blijft leidend.
    """
    global _db

    if dsn is None:
        dsn = os.getenv("DATABASE_URL", "").strip()
    dsn = _normalize_dsn(dsn)

    if min_size is None:
        min_size = int(os.getenv("DB_POOL_MIN", "1"))
    if max_size is None:
        max_size = int(os.getenv("DB_POOL_MAX", "10"))

    if _db is None:
        _db = Database(dsn=dsn, min_size=min_size, max_size=max_size)
    else:
        # update DSN deterministisch (bij env changes)
        _db.dsn = dsn
        _db.min_size = min_size
        _db.max_size = max_size

    await _db.connect()
    return _db


async def close_database() -> None:
    global _db
    if _db is None:
        return
    await _db.close()


def get_db() -> Database:
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _db


def get_pool() -> Optional[asyncpg.pool.Pool]:
    return get_db().get_pool()
