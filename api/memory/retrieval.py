# api/memory/retrieval.py
from __future__ import annotations

import os
import logging
import asyncio
from typing import Any, Dict, List, Optional
from uuid import UUID

import asyncpg

from .embeddings import get_embedding, normalize_db_dsn

logger = logging.getLogger("loesoe.memory.retrieval")

_POOL: Optional[asyncpg.Pool] = None


def _get_db_dsn() -> str:
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL ontbreekt in env")
    return normalize_db_dsn(dsn)


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Per-connection init hook (pgvector type registration)."""
    try:
        from pgvector.asyncpg import register_vector  # type: ignore
    except Exception:
        # pgvector package ontbreekt → we vallen terug op string-cast embedding
        return
    try:
        await register_vector(conn)
    except Exception:
        logger.exception("[memory] register_vector failed; falling back to string-cast embeddings")


async def _get_pool() -> asyncpg.Pool:
    global _POOL
    if _POOL is not None:
        return _POOL

    dsn = _get_db_dsn()
    _POOL = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=5, init=_init_connection)
    logger.info("[memory] asyncpg pool ready")
    return _POOL


async def retrieve_memories(
    *,
    user_id: UUID,
    query: str,
    k: int = 6,
    max_distance: float = 0.35,
    include_test: bool = False,
) -> List[Dict[str, Any]]:
    """
    Zoekt in memory_embeddings op vector distance.
    - Gebruikt cosine distance (<=>) als pgvector beschikbaar is.
    - Filtert direct in SQL op max_distance.
    Return list met: id, content, distance, created_at, metadata
    """
    if not query or not query.strip():
        return []

    # Embedding genereren (sync call) → veilig in thread
    emb = await asyncio.to_thread(get_embedding, query)
    if not emb:
        logger.warning("[memory] embedding missing (OPENAI_API_KEY?) -> retrieval disabled")
        return []

    # Probeer list[float] direct te sturen (werkt als pgvector type is geregistreerd).
    # Fallback: string-cast "[...]" (werkt altijd).
    emb_param: Any = emb
    emb_txt = "[" + ",".join(str(x) for x in emb) + "]"

    pool = await _get_pool()

    # Cosine distance in pgvector: <=>  (0 = identiek, hoger = minder vergelijkbaar)
    # NB: kolomnaam is 'text' (aligned met debug endpoints / StoreReq.text)
    sql = """
    SELECT
      id,
      text,
      COALESCE(metadata, '{}'::jsonb) AS metadata,
      created_at,
      (embedding <=> $2::vector) AS distance
    FROM memory_embeddings
    WHERE user_id = $1::uuid
      AND embedding IS NOT NULL
      AND (embedding <=> $2::vector) <= $4
      AND ($5::boolean OR COALESCE((metadata->>'is_test')::boolean, false) = false)
    ORDER BY embedding <=> $2::vector
    LIMIT $3;
    """

    try:
        async with pool.acquire() as conn:
            try:
                rows = await conn.fetch(
                    sql,
                    str(user_id),
                    emb_param,
                    int(k),
                    float(max_distance),
                    bool(include_test),
                )
            except Exception:
                logger.exception("[memory] vector param failed; retrying with string-cast embedding")
                rows = await conn.fetch(
                    sql,
                    str(user_id),
                    emb_txt,
                    int(k),
                    float(max_distance),
                    bool(include_test),
                )
    except Exception:
        logger.exception("[memory] retrieval failed")
        return []

    out: List[Dict[str, Any]] = []
    for r in rows:
        dist = float(r["distance"]) if r["distance"] is not None else 999.0
        out.append(
            {
                "id": r["id"],
                # Hou key 'content' aan zodat bestaande injectiecode niet hoeft te veranderen
                "content": str(r["text"]),
                "distance": dist,
                "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
                "metadata": r["metadata"],
            }
        )

    if out:
        logger.info("[memory] user_id=%s found=%s best_distance=%.3f", user_id, len(out), out[0]["distance"])
    else:
        logger.info("[memory] user_id=%s found=0", user_id)

    return out
