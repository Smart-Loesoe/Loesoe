from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api.db.database import get_pool

router = APIRouter(prefix="/events", tags=["events"])


class EventIn(BaseModel):
    event_type: str = Field(..., min_length=2, max_length=64)
    source: str = Field(default="api", min_length=2, max_length=32)

    user_id: Optional[str] = None
    session_id: Optional[str] = None

    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/log")
async def log_event(e: EventIn) -> dict[str, Any]:
    pool = get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="DB pool not ready")

    tags = [t.strip() for t in e.tags if t and t.strip()]
    if len(tags) > 50:
        tags = tags[:50]

    payload_json = json.dumps(e.payload or {}, ensure_ascii=False)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO learning_events (user_id, session_id, event_type, source, confidence, tags, payload)
            VALUES ($1, $2, $3, $4, $5, $6::text[], $7::jsonb)
            RETURNING id, created_at
            """,
            e.user_id,
            e.session_id,
            e.event_type,
            e.source,
            e.confidence,
            tags,
            payload_json,
        )

    return {
        "ok": True,
        "id": int(row["id"]),
        "created_at": row["created_at"].isoformat(),
    }


@router.get("/recent")
async def recent_events(limit: int = 25, event_type: Optional[str] = None) -> dict[str, Any]:
    limit = max(1, min(200, limit))

    pool = get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="DB pool not ready")

    async with pool.acquire() as conn:
        if event_type:
            rows = await conn.fetch(
                """
                SELECT id, created_at, user_id, session_id, event_type, source, confidence, tags, payload
                FROM learning_events
                WHERE event_type = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                event_type,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, created_at, user_id, session_id, event_type, source, confidence, tags, payload
                FROM learning_events
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )

    items = []
    for r in rows:
        d = dict(r)
        if d.get("created_at"):
            d["created_at"] = d["created_at"].isoformat()
        items.append(d)

    return {"ok": True, "count": len(items), "items": items}


# =========================================================
# FASE 23.1 / 23.2 — Learning aggregation + pattern store
# =========================================================

@dataclass
class Pattern:
    subject: str               # "user" | "system"
    pattern_type: str          # "preference" | "habit" | "anomaly"
    key: str
    value: dict[str, Any]
    confidence: float
    evidence: dict[str, Any]
    last_seen: datetime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _fetch_events(
    conn,
    limit: int,
    window_minutes: int,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    event_type: Optional[str] = None,
    tag: Optional[str] = None,
) -> list[dict[str, Any]]:
    end = _utcnow()
    start = end - timedelta(minutes=window_minutes)

    where = ["created_at >= $1", "created_at <= $2"]
    params: list[Any] = [start, end]
    p = 3

    if user_id:
        where.append(f"user_id = ${p}")
        params.append(user_id)
        p += 1
    if session_id:
        where.append(f"session_id = ${p}")
        params.append(session_id)
        p += 1
    if event_type:
        where.append(f"event_type = ${p}")
        params.append(event_type)
        p += 1
    if tag:
        # tags is TEXT[]
        where.append(f"${p} = ANY(tags)")
        params.append(tag)
        p += 1

    sql = f"""
        SELECT id, created_at, user_id, session_id, event_type, source, confidence, tags, payload
        FROM learning_events
        WHERE {" AND ".join(where)}
        ORDER BY created_at DESC
        LIMIT {int(limit)}
    """

    rows = await conn.fetch(sql, *params)
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": int(r["id"]),
                "created_at": r["created_at"],
                "user_id": r["user_id"],
                "session_id": r["session_id"],
                "event_type": r["event_type"],
                "source": r["source"],
                "confidence": float(r["confidence"]) if r["confidence"] is not None else None,
                "tags": list(r["tags"] or []),
                "payload": r["payload"] or {},
            }
        )
    return out


def _aggregate_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    by_type: dict[str, int] = {}
    by_tag: dict[str, int] = {}
    last_ts: Optional[datetime] = None

    for e in events:
        et = e.get("event_type") or "unknown"
        by_type[et] = by_type.get(et, 0) + 1

        for t in (e.get("tags") or []):
            t = (t or "").strip()
            if not t:
                continue
            by_tag[t] = by_tag.get(t, 0) + 1

        ts = e.get("created_at")
        if ts and (last_ts is None or ts > last_ts):
            last_ts = ts

    top_types = sorted(by_type.items(), key=lambda x: x[1], reverse=True)[:10]
    top_tags = sorted(by_tag.items(), key=lambda x: x[1], reverse=True)[:15]

    return {
        "total": len(events),
        "last_created_at": last_ts.isoformat() if last_ts else None,
        "top_event_types": [{"event_type": k, "count": v} for k, v in top_types],
        "top_tags": [{"tag": k, "count": v} for k, v in top_tags],
    }


def _derive_patterns(events: list[dict[str, Any]]) -> list[Pattern]:
    """
    Deterministische rules (uitlegbaar) gebaseerd op:
    - event_type
    - tags[]
    - payload.action
    """
    now = _utcnow()

    def has_tag(e: dict[str, Any], wanted: str) -> bool:
        return wanted in (e.get("tags") or [])

    def is_type(e: dict[str, Any], wanted: str) -> bool:
        return (e.get("event_type") or "") == wanted

    patterns: list[Pattern] = []

    # Rule 1 — explain preference
    ask_explain = sum(
        1
        for e in events
        if is_type(e, "ask_explain") or has_tag(e, "ask_explain") or has_tag(e, "pref:explain")
    )
    if ask_explain >= 4:
        conf = min(0.95, 0.55 + (ask_explain - 4) * 0.08)
        patterns.append(
            Pattern(
                subject="user",
                pattern_type="preference",
                key="explain_level",
                value={"level": "high"},
                confidence=float(conf),
                evidence={"count": ask_explain, "threshold": 4, "signals": ["ask_explain", "pref:explain"]},
                last_seen=now,
            )
        )

    # Rule 2 — search habit
    search_use = 0
    last_seen = None
    for e in events:
        payload = e.get("payload") or {}
        action = payload.get("action") if isinstance(payload, dict) else None

        if has_tag(e, "tool:search") or action == "search":
            search_use += 1
            ts = e.get("created_at")
            if ts and (last_seen is None or ts > last_seen):
                last_seen = ts

    if search_use >= 5:
        conf = min(0.92, 0.50 + (search_use - 5) * 0.07)
        patterns.append(
            Pattern(
                subject="user",
                pattern_type="habit",
                key="tool_usage:search",
                value={"count": search_use},
                confidence=float(conf),
                evidence={"count": search_use, "threshold": 5, "signals": ["tool:search", "payload.action=search"]},
                last_seen=last_seen or now,
            )
        )

    # Rule 3 — high friction anomaly
    friction = sum(
        1
        for e in events
        if is_type(e, "correction")
        or is_type(e, "frustration")
        or has_tag(e, "correction")
        or has_tag(e, "frustration")
        or has_tag(e, "anomaly:friction")
    )
    if friction >= 6:
        conf = min(0.90, 0.60 + (friction - 6) * 0.05)
        patterns.append(
            Pattern(
                subject="user",
                pattern_type="anomaly",
                key="interaction:high_friction",
                value={"count": friction},
                confidence=float(conf),
                evidence={"count": friction, "threshold": 6, "signals": ["correction", "frustration"]},
                last_seen=now,
            )
        )

    return patterns


async def _upsert_patterns(conn, patterns: list[Pattern]) -> int:
    if not patterns:
        return 0

    sql = """
    INSERT INTO learning_patterns (subject, pattern_type, key, value, confidence, evidence, last_seen)
    VALUES ($1, $2, $3, $4::jsonb, $5, $6::jsonb, $7)
    ON CONFLICT (subject, pattern_type, key)
    DO UPDATE SET
        value = EXCLUDED.value,
        confidence = EXCLUDED.confidence,
        evidence = EXCLUDED.evidence,
        last_seen = EXCLUDED.last_seen
    """

    n = 0
    for p in patterns:
        await conn.execute(
            sql,
            p.subject,
            p.pattern_type,
            p.key,
            json.dumps(p.value, ensure_ascii=False),
            float(p.confidence),
            json.dumps(p.evidence, ensure_ascii=False),
            p.last_seen,
        )
        n += 1
    return n


@router.get("/learning/summary")
async def learning_summary(
    limit: int = Query(500, ge=1, le=2000),
    window_minutes: int = Query(1440, ge=5, le=60 * 24 * 30),
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    event_type: Optional[str] = None,
    tag: Optional[str] = None,
) -> dict[str, Any]:
    pool = get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="DB pool not ready")

    async with pool.acquire() as conn:
        events = await _fetch_events(
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
        "summary": _aggregate_summary(events),
    }


@router.post("/learning/derive")
async def learning_derive(
    limit: int = Query(500, ge=1, le=2000),
    window_minutes: int = Query(1440, ge=5, le=60 * 24 * 30),
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> dict[str, Any]:
    pool = get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="DB pool not ready")

    async with pool.acquire() as conn:
        events = await _fetch_events(
            conn,
            limit=limit,
            window_minutes=window_minutes,
            user_id=user_id,
            session_id=session_id,
        )
        patterns = _derive_patterns(events)
        written = await _upsert_patterns(conn, patterns)

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
