from __future__ import annotations
import json
from typing import Any, Optional

from api.db.database import get_pool

async def log_event(
    event_type: str,
    source: str = "api",
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    confidence: Optional[float] = None,
    tags: Optional[list[str]] = None,
    payload: Optional[dict[str, Any]] = None,
) -> None:
    pool = get_pool()
    if pool is None:
        return

    _tags = [t.strip() for t in (tags or []) if t and t.strip()]
    if len(_tags) > 50:
        _tags = _tags[:50]

    payload_json = json.dumps(payload or {}, ensure_ascii=False)

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO learning_events (user_id, session_id, event_type, source, confidence, tags, payload)
            VALUES ($1, $2, $3, $4, $5, $6::text[], $7::jsonb)
            """,
            user_id,
            session_id,
            event_type,
            source,
            confidence,
            _tags,
            payload_json,
        )
