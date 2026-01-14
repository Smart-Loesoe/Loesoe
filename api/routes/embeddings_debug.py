# api/routes/embeddings_debug.py
from __future__ import annotations

import os
import json
import hashlib
import logging
from typing import Any, Dict, Optional
from uuid import UUID

import asyncpg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("loesoe.routes.embeddings_debug")

try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # type: ignore


router = APIRouter(prefix="/debug/embeddings", tags=["debug-embeddings"])


class StoreReq(BaseModel):
    user_id: UUID
    text: str = Field(min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    embed: bool = True  # als True: embedding direct maken + opslaan


class BackfillReq(BaseModel):
    user_id: UUID
    limit: int = 200
    model: Optional[str] = None


class QueryReq(BaseModel):
    user_id: UUID
    query: str = Field(min_length=1)
    k: int = 8
    max_distance: float = 1.60
    include_test: bool = False
    model: Optional[str] = None


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pg_dsn_from_env() -> str:
    """
    Bouwt een geldige Postgres DSN uit env.
    Let op: dit gebruikt POSTGRES_* zodat het consistent blijft met compose/.env.
    """
    # Prefer DATABASE_URL if present (we only need host/port/db; credentials from POSTGRES_*)
    # NOTE: asyncpg.connect expects 'postgresql://', not 'postgresql+asyncpg://'
    _db_url = os.getenv("DATABASE_URL") or ""
    if _db_url.startswith("postgresql+asyncpg://"):
        _db_url = _db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if _db_url.startswith("postgresql://") and "@" in _db_url:
        # If DATABASE_URL includes creds, use it directly
        return _db_url

    host = os.getenv("DB_HOST", "db")
    port = int(os.getenv("DB_PORT", "5432"))
    dbname = os.getenv("POSTGRES_DB", "loesoe")
    user = os.getenv("POSTGRES_USER", "loesoe")
    pwd = os.getenv("POSTGRES_PASSWORD") or os.getenv("POSTGRES_PASS") or ""

    if not pwd:
        raise RuntimeError("POSTGRES_PASSWORD ontbreekt in env (api container).")

    return f"postgresql://{user}:{pwd}@{host}:{port}/{dbname}"


def _get_openai_client() -> "OpenAI":
    if OpenAI is None:
        raise RuntimeError("openai package ontbreekt in container.")
    key = os.getenv("OPENAI_API_KEY") or ""
    if not key:
        raise RuntimeError("OPENAI_API_KEY ontbreekt in env (api container).")
    return OpenAI(api_key=key)


def _get_embedding_model(req_model: Optional[str] = None) -> str:
    return req_model or os.getenv("EMBEDDING_MODEL") or "text-embedding-3-small"


async def _try_register_pgvector(conn: asyncpg.Connection) -> None:
    """
    Probeert pgvector type te registreren voor asyncpg.
    Niet verplicht, want we casten '[..]'::vector in SQL.
    """
    try:
        from pgvector.asyncpg import register_vector  # type: ignore

        await register_vector(conn)
    except Exception:
        # Niet fatal; we gebruiken string-cast naar vector
        return


async def _set_embedding(conn: asyncpg.Connection, row_id: int, vector: list[float]) -> None:
    # pgvector accepteert '[1,2,3]'::vector
    emb_txt = "[" + ",".join(str(x) for x in vector) + "]"
    await conn.execute(
        "UPDATE public.memory_embeddings SET embedding = $1::vector WHERE id = $2",
        emb_txt,
        row_id,
    )


def _require_debug_enabled() -> None:
    """
    Extra safety: debug endpoints alleen als REQUIRE_EMBEDDINGS_DEBUG=1.
    (Je main.py heeft dit ook, maar dubbel is oké.)
    """
    if os.getenv("REQUIRE_EMBEDDINGS_DEBUG", "0") != "1":
        raise HTTPException(status_code=403, detail="Embeddings debug disabled (REQUIRE_EMBEDDINGS_DEBUG!=1)")


@router.post("/store")
async def store(req: StoreReq):
    """
    Slaat text op in memory_embeddings + (optioneel) maakt direct embedding.
    """
    _require_debug_enabled()

    dsn = _pg_dsn_from_env()
    content_hash = _hash_text(req.text)

    sql_upsert = """
    INSERT INTO public.memory_embeddings (user_id, content, content_hash, metadata)
    VALUES ($1, $2, $3, $4::jsonb)
    ON CONFLICT (user_id, content_hash)
    DO UPDATE SET content = EXCLUDED.content, metadata = EXCLUDED.metadata
    RETURNING id, (embedding IS NOT NULL) AS has_vec;
    """

    try:
        conn = await asyncpg.connect(dsn)
        try:
            await _try_register_pgvector(conn)

            row = await conn.fetchrow(
                sql_upsert,
                str(req.user_id),
                req.text,
                content_hash,
                json.dumps(req.metadata),
            )
            if not row:
                raise RuntimeError("Upsert gaf geen row terug.")

            row_id = int(row["id"])
            has_vec = bool(row["has_vec"])

            embedded = False
            used_model = None

            if req.embed and (not has_vec):
                client = _get_openai_client()
                model = _get_embedding_model()
                used_model = model

                emb = client.embeddings.create(model=model, input=req.text).data[0].embedding
                await _set_embedding(conn, row_id, emb)
                embedded = True

            return {
                "ok": True,
                "id": row_id,
                "content_hash": content_hash,
                "had_embedding": has_vec,
                "embedded_now": embedded,
                "embedding_model": used_model,
            }
        finally:
            await conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("store failed")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@router.post("/backfill")
async def backfill(req: BackfillReq):
    """
    Backfill embeddings voor rows waar embedding IS NULL, voor een user_id.
    """
    _require_debug_enabled()

    dsn = _pg_dsn_from_env()
    model = _get_embedding_model(req.model)

    try:
        client = _get_openai_client()
        conn = await asyncpg.connect(dsn)
        try:
            await _try_register_pgvector(conn)

            rows = await conn.fetch(
                """
                SELECT id, content
                FROM public.memory_embeddings
                WHERE user_id = $1 AND embedding IS NULL
                ORDER BY id
                LIMIT $2
                """,
                str(req.user_id),
                int(req.limit),
            )

            done = 0
            for r in rows:
                emb = client.embeddings.create(model=model, input=r["content"]).data[0].embedding
                await _set_embedding(conn, int(r["id"]), emb)
                done += 1

            return {"ok": True, "user_id": str(req.user_id), "model": model, "updated": done}
        finally:
            await conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("backfill failed")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@router.post("/query")
async def query(req: QueryReq):
    """
    Debug endpoint: berekent embedding van req.query en haalt top-K nearest memories op (pgvector).
    Handig om Fase 22.2 te testen zonder /chat aan te roepen.
    """
    _require_debug_enabled()

    dsn = _pg_dsn_from_env()
    model = _get_embedding_model(req.model)

    try:
        client = _get_openai_client()
        emb_vec = client.embeddings.create(model=model, input=req.query).data[0].embedding
        emb_txt = "[" + ",".join(str(x) for x in emb_vec) + "]"

        conn = await asyncpg.connect(dsn)
        try:
            await _try_register_pgvector(conn)
            rows = await conn.fetch(
                """
                SELECT content, metadata, (embedding <-> $2::vector) AS distance
                FROM public.memory_embeddings
                WHERE user_id = $1
                  AND embedding IS NOT NULL
                  AND (embedding <-> $2::vector) <= $3
                  AND ( $5::bool OR COALESCE(metadata->>'tag','') NOT IN ('smoketest','api') )
                ORDER BY
                  CASE
                    WHEN COALESCE(metadata->>'tag','') IN ('prefs','prefs2','prefs3','profile','goals') THEN 0
                    WHEN COALESCE(metadata->>'tag','') IN ('memory','notes') THEN 1
                    ELSE 2
                  END,
                  distance ASC
                LIMIT $4
                """,
                str(req.user_id),
                emb_txt,
                float(req.max_distance),
                int(req.k),
                bool(req.include_test),
            )

            items = []
            for r in rows:
                items.append(
                    {
                        "content": r["content"],
                        "metadata": r["metadata"],
                        "distance": float(r["distance"]),
                    }
                )

            return {
                "ok": True,
                "user_id": str(req.user_id),
                "k": int(req.k),
                "max_distance": float(req.max_distance),
                "model": model,
                "results": items,
            }
        finally:
            await conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("query failed")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
