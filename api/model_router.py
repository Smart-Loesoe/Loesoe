# 📘 Loesoe — api/model_router.py
# Fase 22.2: pgvector retrieval + prompt-injectie
# ✅ Debug als apart JSON-veld (niet meer in reply geplakt)
# ✅ System rules leidend (/healthz, .env, no secrets)
# ✅ Encoding normalizer (â-rotzooi weg)
# ✅ Metric switch (l2/cosine) + cutoff via .env
# ✅ History caps (tokens onder controle)
# ✅ GPT-5 temperature guard

import os
import json
import logging
import asyncio
from typing import List, Dict, Optional, Any, Tuple
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Body
from pydantic import BaseModel
from openai import AsyncOpenAI

logger = logging.getLogger("loesoe.model_router")
router = APIRouter()

client = AsyncOpenAI()

# ==============================
# ENV / CONFIG
# ==============================
DEFAULT_MODEL = os.getenv("MODEL_DEFAULT", "gpt-5").strip()
FALLBACK_MODEL = os.getenv("MODEL_FALLBACK", "gpt-4.1-mini").strip()
MODEL_TIMEOUT_SECONDS = int(os.getenv("MODEL_TIMEOUT_SECONDS", "25"))
MODEL_MAX_RETRIES = int(os.getenv("MODEL_MAX_RETRIES", "1"))

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

MEMORY_RETRIEVAL_ENABLED = os.getenv("MEMORY_RETRIEVAL_ENABLED", "false").lower() in (
    "1",
    "true",
    "yes",
    "y",
    "on",
)
MEMORY_TOP_K = int(os.getenv("MEMORY_TOP_K", "6"))
MEMORY_MAX_DISTANCE = float(os.getenv("MEMORY_MAX_DISTANCE", "1.35"))
MEMORY_MAX_CHARS = int(os.getenv("MEMORY_MAX_CHARS", "900"))
MEMORY_MIN_CONTENT_LEN = int(os.getenv("MEMORY_MIN_CONTENT_LEN", "12"))

# distance metric (pgvector)
# l2     -> <-> (euclidean distance)
# cosine -> <=> (cosine distance)
MEMORY_DISTANCE_METRIC = os.getenv("MEMORY_DISTANCE_METRIC", "l2").strip().lower()
if MEMORY_DISTANCE_METRIC not in ("l2", "cosine"):
    MEMORY_DISTANCE_METRIC = "l2"

# history caps
HISTORY_MAX_MESSAGES = int(os.getenv("HISTORY_MAX_MESSAGES", "12"))
HISTORY_MAX_CHARS = int(os.getenv("HISTORY_MAX_CHARS", "6000"))

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# model params
MODEL_TEMPERATURE = float(os.getenv("MODEL_TEMPERATURE", "0.3"))


# ==============================
# REQUEST MODEL
# ==============================
class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, Any]]] = None
    user_id: Optional[str] = None
    debug: Optional[bool] = False


# ==============================
# HELPERS
# ==============================
def _clean(text: str) -> str:
    return (text or "").strip()


def _as_metadata_dict(md: Any) -> Dict[str, Any]:
    if md is None:
        return {}
    if isinstance(md, dict):
        return md
    if isinstance(md, str):
        try:
            parsed = json.loads(md)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _parse_uuid(value: Optional[str]) -> Optional[UUID]:
    try:
        return UUID(value) if value else None
    except Exception:
        return None


def _safe_role(role: Any) -> Optional[str]:
    r = str(role or "").strip().lower()
    if r in ("system", "user", "assistant"):
        return r
    return None


def _normalize_history(history: Optional[List[Dict[str, Any]]]) -> List[Dict[str, str]]:
    """
    Accepteert frontend history als [{role, content}, ...]
    Beperkt aantal berichten + totale chars.
    """
    if not history:
        return []

    tail = history[-HISTORY_MAX_MESSAGES:] if HISTORY_MAX_MESSAGES > 0 else history[:]
    normalized: List[Dict[str, str]] = []

    total_chars = 0
    for item in tail:
        role = _safe_role(item.get("role"))
        content = _clean(item.get("content"))
        if not role or not content:
            continue

        if total_chars + len(content) > HISTORY_MAX_CHARS:
            remaining = max(0, HISTORY_MAX_CHARS - total_chars)
            if remaining <= 0:
                break
            content = content[:remaining]

        normalized.append({"role": role, "content": content})
        total_chars += len(content)

        if total_chars >= HISTORY_MAX_CHARS:
            break

    return normalized


def _normalize_encoding(text: str) -> str:
    """
    Fix voor Windows/UTF-8 artifacts zoals: "â€‘" / "â€™" / rare dashes.
    Houdt output/logs/UI schoon.
    """
    return (
        text.replace("\u2011", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("â€‘", "-")
        .replace("â€“", "-")
        .replace("â€”", "-")
        .replace("â€™", "'")
        .replace("â€œ", '"')
        .replace("â€\u009d", '"')
        .replace("â€\u0098", "'")
        .replace("â€\u0099", "'")
    )


# ==============================
# DB
# ==============================
_db_pool: Optional[asyncpg.Pool] = None


async def _db() -> asyncpg.Pool:
    global _db_pool
    if _db_pool is not None:
        return _db_pool

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is empty")

    # normalize for asyncpg pool
    dsn = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    _db_pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=5)
    return _db_pool


# ==============================
# EMBEDDINGS / RETRIEVAL
# ==============================
async def _embed(text: str) -> List[float]:
    res = await client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return res.data[0].embedding


def _vec(v: List[float]) -> str:
    return "[" + ",".join(str(x) for x in v) + "]"


def _distance_operator() -> str:
    # pgvector operators:
    # <->  : L2 distance
    # <=>  : cosine distance
    return "<=>" if MEMORY_DISTANCE_METRIC == "cosine" else "<->"


async def _fetch_memories(user_id: str, query: str) -> Tuple[List[Dict[str, Any]], Optional[float]]:
    uid = _parse_uuid(user_id)
    if not uid:
        return [], None

    vec = await _embed(query)
    pool = await _db()
    op = _distance_operator()

    sql = f"""
        SELECT content, metadata, (embedding {op} $2::vector) AS distance
        FROM public.memory_embeddings
        WHERE user_id = $1
          AND (embedding {op} $2::vector) <= $3
        ORDER BY distance ASC
        LIMIT $4
    """

    rows = await pool.fetch(
        sql,
        str(uid),
        _vec(vec),
        MEMORY_MAX_DISTANCE,
        MEMORY_TOP_K,
    )

    out: List[Dict[str, Any]] = []
    best: Optional[float] = None

    for r in rows:
        content = _clean(r["content"])
        if len(content) < MEMORY_MIN_CONTENT_LEN:
            continue

        dist = float(r["distance"])
        if best is None or dist < best:
            best = dist

        out.append(
            {
                "content": content,
                "metadata": _as_metadata_dict(r["metadata"]),
                "distance": dist,
            }
        )

    return out, best


def _build_memory_block(memories: List[Dict[str, Any]]) -> Optional[str]:
    if not memories:
        return None

    total = 0
    lines = []
    for m in memories:
        tag = m["metadata"].get("tag")
        line = f"- [{tag}] {m['content']}" if tag else f"- {m['content']}"
        if total + len(line) > MEMORY_MAX_CHARS:
            break
        lines.append(line)
        total += len(line)

    return "Relevante herinneringen (ter verificatie):\n" + "\n".join(lines)


# ==============================
# CORE
# ==============================
async def generate_reply(
    message: str,
    history: Optional[List[Dict[str, Any]]],
    user_id: Optional[str],
) -> Tuple[str, Dict[str, Any]]:
    """
    Return:
      reply_text (clean)
      debug_info dict (altijd gevuld, maar route stuurt 'm alleen terug bij debug=true)
    """
    debug_info: Dict[str, Any] = {
        "model": None,
        "metric": MEMORY_DISTANCE_METRIC,
        "cutoff": MEMORY_MAX_DISTANCE,
        "history_used": 0,
        "memory_used": [],
        "memory_hits": 0,
        "memory_best": None,
        "memory_enabled": MEMORY_RETRIEVAL_ENABLED,
        "user_id_valid": False,
    }

    memories: List[Dict[str, Any]] = []
    best_distance: Optional[float] = None
    memory_block: Optional[str] = None

    normalized_history = _normalize_history(history)
    debug_info["history_used"] = len(normalized_history)

    if user_id and _parse_uuid(user_id):
        debug_info["user_id_valid"] = True

    if MEMORY_RETRIEVAL_ENABLED and user_id and debug_info["user_id_valid"]:
        try:
            memories, best_distance = await _fetch_memories(user_id, message)
            memory_block = _build_memory_block(memories)

            debug_info["memory_hits"] = len(memories)
            debug_info["memory_best"] = round(best_distance, 6) if best_distance is not None else None
            debug_info["memory_used"] = [
                {"content": m["content"], "distance": round(float(m["distance"]), 6)}
                for m in memories
            ]

            # retrieval stats logging (tunen!)
            logger.info(
                "memory_retrieval metric=%s hits=%s best=%s cutoff=%s user_id=%s",
                MEMORY_DISTANCE_METRIC,
                len(memories),
                f"{best_distance:.4f}" if best_distance is not None else "none",
                MEMORY_MAX_DISTANCE,
                user_id,
            )
        except Exception as e:
            logger.warning("memory retrieval failed: %s", e)
            debug_info["memory_error"] = str(e)

    # ✅ System rules (leidend)
    system_prompt = (
        "Je bent Loesoe. Antwoord kort en duidelijk in het Nederlands.\n"
        "Kernregels (leidend):\n"
        "- /healthz is de enige waarheid over status.\n"
        "- .env is de enige bron van waarheid voor configuratie.\n"
        "- Geen hardcoded secrets.\n"
    )

    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    if memory_block:
        messages.append({"role": "system", "content": memory_block})

    messages.extend(normalized_history)
    messages.append({"role": "user", "content": message})

    async def _call(model: str) -> str:
        kwargs: Dict[str, Any] = {"model": model, "messages": messages}
        # guard: gpt-5* accepteert geen temperature
        if not model.startswith("gpt-5"):
            kwargs["temperature"] = MODEL_TEMPERATURE
        r = await client.chat.completions.create(**kwargs)
        return r.choices[0].message.content or ""

    attempt = 0
    model_try = DEFAULT_MODEL

    while True:
        attempt += 1
        try:
            reply = await asyncio.wait_for(_call(model_try), timeout=MODEL_TIMEOUT_SECONDS)
            text = _normalize_encoding(_clean(reply))

            debug_info["model"] = model_try

            return text, debug_info

        except Exception as e:
            logger.warning("model call failed (%s, attempt %s): %s", model_try, attempt, e)
            debug_info["model_error"] = str(e)

            if attempt <= MODEL_MAX_RETRIES and model_try != FALLBACK_MODEL:
                model_try = FALLBACK_MODEL
                continue

            logger.exception("model failed definitief")
            debug_info["model"] = model_try
            return "Ik liep even vast bij de AI-call. Probeer het nog een keer.", debug_info


# ==============================
# ROUTES
# ==============================
@router.post("/chat")
async def chat(req: ChatRequest = Body(...)):
    reply_text, debug_info = await generate_reply(
        req.message,
        req.history,
        req.user_id,
    )

    payload: Dict[str, Any] = {"ok": True, "reply": reply_text}
    if req.debug:
        payload["debug"] = debug_info
    return payload


@router.post("/model/chat")
async def model_chat(req: ChatRequest = Body(...)):
    return await chat(req)


@router.post("/chat/send")
async def chat_send(req: ChatRequest = Body(...)):
    return await chat(req)
