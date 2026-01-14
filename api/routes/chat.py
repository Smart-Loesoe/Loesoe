from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Tuple
import uuid
import base64
import json
import logging
import os
import importlib

import asyncpg

from api.auth.dependencies import get_current_user
from api.model_router import generate_reply

logger = logging.getLogger("loesoe.chat")
router = APIRouter(tags=["chat"])


# -----------------------------
# Env (runtime truth)
# -----------------------------
MEMORY_RETRIEVAL_ENABLED = os.getenv("MEMORY_RETRIEVAL_ENABLED", "1").lower() in ("1", "true", "yes", "on")
MEMORY_TOP_K = int(os.getenv("MEMORY_TOP_K", "6"))
MEMORY_MAX_DISTANCE = float(os.getenv("MEMORY_MAX_DISTANCE", "1.15"))
MEMORY_MAX_CHARS = int(os.getenv("MEMORY_MAX_CHARS", "1600"))
ALLOW_TEST_MEMORIES = os.getenv("ALLOW_TEST_MEMORIES", "0").lower() in ("1", "true", "yes", "on")

_DATABASE_URL = os.getenv("DATABASE_URL")
_pool: Optional[asyncpg.Pool] = None


class ChatRequest(BaseModel):
    message: str
    # Optional: for testing without auth header
    user_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    analysis: Optional[dict] = None
    scores: Optional[dict] = None


def _uuid_from_jwt_user_id(user_id: int) -> str:
    """Maak een stabiele UUID op basis van auth user.id"""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"loesoe-user:{user_id}"))


def _extract_user_id_from_jwt(request: Request) -> Optional[int]:
    """
    Fallback: decode JWT payload (zonder signature check).
    We gebruiken dit alleen als get_current_user niet genoeg info geeft.
    """
    auth = request.headers.get("authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None

    token = auth.split(" ", 1)[1]
    try:
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("id")
    except Exception as e:
        logger.warning(f"JWT decode failed: {e}")
        return None


async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool

    if not _DATABASE_URL:
        raise RuntimeError("DATABASE_URL ontbreekt (env).")

    _pool = await asyncpg.create_pool(dsn=_DATABASE_URL, min_size=1, max_size=5)
    return _pool


def _vector_literal(vec: List[float]) -> str:
    # pgvector literal: [0.1,0.2,...]
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


async def _embed_query(text: str) -> Optional[List[float]]:
    """
    Best-effort: probeer een bestaande embed-functie in je codebase te gebruiken.
    Zo crasht Loesoe niet als helpers verplaatst zijn.
    """
    candidates: List[Tuple[str, str]] = [
        ("api.routes.embeddings_debug", "embed_text"),
        ("api.routes.embeddings_debug", "create_embedding"),
        ("api.model_router", "embed_text"),
    ]

    for mod_name, fn_name in candidates:
        try:
            mod = importlib.import_module(mod_name)
            fn = getattr(mod, fn_name, None)
            if fn is None:
                continue

            res = fn(text)  # kan sync/async zijn
            if hasattr(res, "__await__"):
                res = await res

            # verwacht list[float]
            if isinstance(res, list) and res and isinstance(res[0], (float, int)):
                return [float(x) for x in res]
        except Exception:
            continue

    return None


async def _retrieve_memory_context(user_uuid: str, user_message: str) -> Tuple[str, Dict[str, Any]]:
    """
    Haal top-k nearest memories op (pgvector) en bouw injectieblok.
    """
    if not MEMORY_RETRIEVAL_ENABLED:
        return "", {"enabled": False}

    pool = await _get_pool()

    qvec = await _embed_query(user_message)
    if not qvec:
        return "", {"enabled": True, "error": "No embedding function available"}

    vec_lit = _vector_literal(qvec)

    # Filter debug/test memories als ALLOW_TEST_MEMORIES=0
    test_filter_sql = ""
    if not ALLOW_TEST_MEMORIES:
        # metadata is jsonb; we filter source=debug
        test_filter_sql = "AND COALESCE(metadata->>'source','') <> 'debug'"

    sql = f"""
        SELECT
            content,
            metadata::text AS metadata,
            (embedding <-> $1::vector) AS distance
        FROM memory_embeddings
        WHERE user_id = $2::uuid
          AND embedding IS NOT NULL
          {test_filter_sql}
        ORDER BY embedding <-> $1::vector
        LIMIT $3
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, vec_lit, user_uuid, MEMORY_TOP_K)

    kept: List[Dict[str, Any]] = []
    for r in rows:
        dist = float(r["distance"]) if r["distance"] is not None else 999.0
        if dist <= MEMORY_MAX_DISTANCE:
            kept.append(
                {
                    "content": (r["content"] or "").strip(),
                    "distance": dist,
                    "metadata": r["metadata"] or "{}",
                }
            )

    debug = {
        "enabled": True,
        "top_k": MEMORY_TOP_K,
        "max_distance": MEMORY_MAX_DISTANCE,
        "max_chars": MEMORY_MAX_CHARS,
        "allow_test_memories": ALLOW_TEST_MEMORIES,
        "candidates": len(rows),
        "kept": len(kept),
        "kept_distances": [round(x["distance"], 4) for x in kept[:10]],
    }

    if not kept:
        return "", debug

    # cap chars
    lines: List[str] = []
    total = 0
    for item in kept:
        line = item["content"]
        if not line:
            continue
        # afstand erbij is chill voor tuning/debug
        chunk = f"- (d={item['distance']:.4f}) {line}\n"
        if total + len(chunk) > MEMORY_MAX_CHARS:
            break
        lines.append(chunk)
        total += len(chunk)

    if not lines:
        return "", debug

    injected = (
        "\n[LOESOE_MEMORY_CONTEXT]\n"
        + "".join(lines)
        + "[/LOESOE_MEMORY_CONTEXT]\n\n"
    )
    return injected, debug


@router.post("/chat", response_model=ChatResponse)
@router.post("/chat/send", response_model=ChatResponse)
async def chat_endpoint(
    req: ChatRequest,
    request: Request,
    current_user=Depends(get_current_user),
):
    # 1) user_uuid bepalen
    user_uuid: Optional[str] = None

    if req.user_id:
        # allow direct uuid string for testing
        user_uuid = req.user_id.strip()

    if not user_uuid:
        # current_user kan dict/object zijn; we willen id int
        auth_id = None
        try:
            if isinstance(current_user, dict):
                auth_id = current_user.get("id")
            else:
                auth_id = getattr(current_user, "id", None)
        except Exception:
            auth_id = None

        if not auth_id:
            auth_id = _extract_user_id_from_jwt(request)

        if not auth_id:
            raise HTTPException(status_code=401, detail="User not authenticated")

        user_uuid = _uuid_from_jwt_user_id(int(auth_id))

    # 2) memory retrieval → inject
    injected, retrieval_debug = "", {}
    try:
        injected, retrieval_debug = await _retrieve_memory_context(user_uuid, req.message)
    except Exception as e:
        logger.warning(f"[memory-retrieval] failed (non-fatal): {e}")
        retrieval_debug = {"enabled": True, "error": str(e)}

    user_message = f"{injected}{req.message}" if injected else req.message

    # 3) AI antwoord
    reply, analysis, scores = await generate_reply(
        user_message=user_message,
        user_id=user_uuid,
    )

    if analysis is None:
        analysis = {}
    analysis["memory_retrieval"] = retrieval_debug

    return ChatResponse(reply=reply, analysis=analysis, scores=scores)
