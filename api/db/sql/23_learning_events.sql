from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.db.database import get_pool

router = APIRouter(prefix="/events", tags=["events"])


# =========================
# Models
# =========================

class EventIn(BaseModel):
    event_type: str = Field(..., min_length=2, max_length=64)
    source: str = Field(default="api", min_length=2, max_length=32)

    user_id: Optional[str] = None
    session_id: Optional[str] = None

    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)

    payload: dict[str, Any] = Field(default_factory=dict)


# =========================
# Routes
# =========================

@router.post("/log")
async def log_event(event: EventIn) -> dict[str, Any]:
    """
    Log een RUW event.
    Geen interpretatie.
    Geen afleiding.
    Dit is de waarheid.
    """
    pool = get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="DB pool not ready")

    tags = [t.strip() for t in event.tags if t and t.strip()]
    payload_json = json.dumps(event.payload or {}, ensure_ascii=False)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO learning_events (
                user_id,
                session_id,
                event_type,
                source,
                confidence,
                tags,
                payload
            )
            VALUES ($1, $2, $3, $4, $5, $6::text[], $7::jsonb)
            RETURNING id, created_at
            """,
            event.user_id,
            event.session_id,
            event.event_type,
            event.source,
            event.confidence,
            tags,
            payload_json,
        )

    return {
        "ok": True,
        "id": int(row["id"]),
        "created_at": row["created_at"].isoformat(),
    }


@router.get("/recent")
async def recent_events(limit: int = 25) -> dict[str, Any]:
    """
    Laat recente events zien.
    Debug / observatie / dashboard.
    """
    limit = max(1, min(200, limit))

    pool = get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="DB pool not ready")

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id,
                created_at,
                user_id,
                session_id,
                event_type,
                source,
                confidence,
                tags,
                payload
            FROM learning_events
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )

    items = []
    for r in rows:
        d = dict(r)
        d["created_at"] = d["created_at"].isoformat()
        items.append(d)

    return {
        "ok": True,
        "count": len(items),
        "items": items,
    }
