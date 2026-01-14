from __future__ import annotations

import json
from fastapi import APIRouter, HTTPException, Query
from typing import Any, Optional, Literal

from api.db.database import get_pool
from api.learning.aggregator import (
    fetch_events,
    aggregate_summary,
    derive_patterns,
    upsert_patterns,
)

router = APIRouter(prefix="/learning", tags=["learning"])


def _as_json(v: Any) -> Any:
    """Forceer jsonb velden als echte JSON (dict/list)."""
    if v is None:
        return {}
    if isinstance(v, (dict, list)):
        return v
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return {"_raw": v}
    return {"_raw": str(v)}


@router.get("/summary")
async def learning_summary(
    limit: int = Query(500, ge=1, le=2000),
    window_minutes: int = Query(1440, ge=5, le=60 * 24 * 30),
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    event_type: Optional[str] = None,
    tag: Optional[str] = None,
) -> dict[str, Any]:
    """
    Read-only: haalt events op en geeft een samenvatting terug.
    Geen opslag, geen learning-derive.
    """
    pool = get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="DB pool not ready")

    async with pool.acquire() as conn:
        events = await fetch_events(
            conn,
            limit=limit,
            window_minutes=window_minutes,
            user_id=user_id,
            session_id=session_id,
            event_type=event_type,
            tag=tag,
        )

    return {
        "ok": True,
        "filters": {
            "limit": limit,
            "window_minutes": window_minutes,
            "user_id": user_id,
            "session_id": session_id,
            "event_type": event_type,
            "tag": tag,
        },
        "summary": aggregate_summary(events),
    }


@router.post("/derive")
async def learning_derive(
    limit: int = Query(500, ge=1, le=2000),
    window_minutes: int = Query(1440, ge=5, le=60 * 24 * 30),
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Leest events, derive patterns en schrijft ze naar learning_patterns (upsert).
    """
    pool = get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="DB pool not ready")

    async with pool.acquire() as conn:
        events = await fetch_events(
            conn,
            limit=limit,
            window_minutes=window_minutes,
            user_id=user_id,
            session_id=session_id,
        )
        patterns = derive_patterns(events)
        written = await upsert_patterns(conn, patterns)

    return {
        "ok": True,
        "events_used": len(events),
        "patterns_derived": len(patterns),
        "patterns_written": written,
        "patterns": [
            {
                "subject": p.subject,
                "pattern_type": p.pattern_type,
                "key": p.key,
                "value": p.value,
                "confidence": p.confidence,
                "evidence": p.evidence,
                "last_seen": p.last_seen.isoformat(),
            }
            for p in patterns
        ],
    }


@router.get("/patterns")
async def learning_patterns(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    pattern_type: Optional[str] = None,
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    order: Literal["confidence", "last_seen", "created_at", "updated_at"] = "confidence",
    direction: Literal["asc", "desc"] = "desc",
) -> dict[str, Any]:
    """
    ✅ Fase 23.3 — Read-only impact
    Leest bestaande patterns uit learning_patterns.
    Geen derive, geen interpretatie, geen gedrag wijzigen.

    Schema (jouw DB):
    id, subject, pattern_type, key, value(jsonb), confidence,
    evidence(jsonb), last_seen(timestamptz), created_at, updated_at
    """
    pool = get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="DB pool not ready")

    order_sql = {
        "confidence": "confidence",
        "last_seen": "last_seen",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }[order]
    dir_sql = "ASC" if direction == "asc" else "DESC"

    where = ["confidence >= $1"]
    params: list[Any] = [min_confidence]
    idx = 2

    if pattern_type:
        where.append(f"pattern_type = ${idx}")
        params.append(pattern_type)
        idx += 1

    where_sql = " AND ".join(where)

    async with pool.acquire() as conn:
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM learning_patterns WHERE {where_sql}",
            *params,
        )

        rows = await conn.fetch(
            f"""
            SELECT
                id,
                subject,
                pattern_type,
                key,
                value,
                confidence,
                evidence,
                last_seen,
                created_at,
                updated_at
            FROM learning_patterns
            WHERE {where_sql}
            ORDER BY {order_sql} {dir_sql}
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
            limit,
            offset,
        )

    items = []
    for r in rows:
        items.append(
            {
                "id": int(r["id"]),
                "subject": r["subject"],
                "pattern_type": r["pattern_type"],
                "key": r["key"],
                "value": _as_json(r["value"]),
                "confidence": float(r["confidence"] or 0.0),
                "evidence": _as_json(r["evidence"]),
                "last_seen": r["last_seen"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
        )

    return {
        "ok": True,
        "filters": {
            "limit": limit,
            "offset": offset,
            "pattern_type": pattern_type,
            "min_confidence": min_confidence,
            "order": order,
            "direction": direction,
        },
        "total": int(total or 0),
        "items": items,
    }
