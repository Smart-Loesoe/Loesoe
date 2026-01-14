# api/memory/embeddings.py
from __future__ import annotations

import os
import logging
from typing import Optional, List

logger = logging.getLogger("loesoe.memory.embeddings")


DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


def normalize_db_dsn(dsn: str) -> str:
    """
    asyncpg verwacht postgresql://
    SQLAlchemy gebruikt soms postgresql+asyncpg://
    """
    dsn = (dsn or "").strip()
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    return dsn


def get_embedding_model() -> str:
    return (os.getenv("EMBEDDING_MODEL") or "").strip() or DEFAULT_EMBEDDING_MODEL


def get_openai_api_key() -> str:
    return (os.getenv("OPENAI_API_KEY") or "").strip()


def embeddings_enabled() -> bool:
    return bool(get_openai_api_key())


def get_embedding(text: str) -> Optional[List[float]]:
    """
    Returns embedding vector for text, or None if missing key / fails.
    Sync call (OpenAI python client is sync); fine for debug/backfill.
    """
    if not text or not text.strip():
        return None

    api_key = get_openai_api_key()
    if not api_key:
        logger.warning("OPENAI_API_KEY missing -> embeddings disabled")
        return None

    model = get_embedding_model()

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.embeddings.create(model=model, input=text)
        return resp.data[0].embedding
    except Exception as e:
        logger.warning("get_embedding failed: %s: %s", type(e).__name__, e)
        return None
