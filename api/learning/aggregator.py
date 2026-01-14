from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

@dataclass
class Pattern:
    subject: str               # "user" | "system"
    pattern_type: str          # "preference" | "habit" | "anomaly"
    key: str
    value: dict[str, Any]
    confidence: float
    evidence: dict[str, Any]
    last_seen: datetime

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

async def fetch_events(
    conn,
    limit: int = 500,
    window_minutes: int = 1440,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    event_type: Optional[str] = None,
    tag: Optional[str] = None,
) -> list[dict[str, Any]]:
    end = utcnow()
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
    return [
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
        for r in rows
    ]

def aggregate_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
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

def derive_patterns(events: list[dict[str, Any]]) -> list[Pattern]:
    """
    Deterministische regels:
    - explain_level preference: veel ask_explain events
    - tool_usage:search habit: payload.action == "search" of tag tool:search
    - high_friction anomaly: veel correction/frustration
    """
    now = utcnow()

    def has_tag(e: dict[str, Any], wanted: str) -> bool:
        return wanted in (e.get("tags") or [])

    def is_type(e: dict[str, Any], wanted: str) -> bool:
        return (e.get("event_type") or "") == wanted

    patterns: list[Pattern] = []

    ask_explain = sum(1 for e in events if is_type(e, "ask_explain") or has_tag(e, "ask_explain"))
    if ask_explain >= 4:
        conf = min(0.95, 0.55 + (ask_explain - 4) * 0.08)
        patterns.append(Pattern(
            subject="user",
            pattern_type="preference",
            key="explain_level",
            value={"level": "high"},
            confidence=float(conf),
            evidence={"event_type_or_tag": "ask_explain", "count": ask_explain, "threshold": 4},
            last_seen=now,
        ))

    search_use = 0
    for e in events:
        payload = e.get("payload") or {}
        action = payload.get("action") if isinstance(payload, dict) else None
        if has_tag(e, "tool:search") or action == "search":
            search_use += 1
    if search_use >= 5:
        conf = min(0.92, 0.50 + (search_use - 5) * 0.07)
        patterns.append(Pattern(
            subject="user",
            pattern_type="habit",
            key="tool_usage:search",
            value={"count": search_use},
            confidence=float(conf),
            evidence={"signals": ["tool:search", "payload.action=search"], "count": search_use, "threshold": 5},
            last_seen=now,
        ))

    friction = sum(1 for e in events if is_type(e, "correction") or is_type(e, "frustration")
                   or has_tag(e, "correction") or has_tag(e, "frustration"))
    if friction >= 6:
        conf = min(0.90, 0.60 + (friction - 6) * 0.05)
        patterns.append(Pattern(
            subject="user",
            pattern_type="anomaly",
            key="interaction:high_friction",
            value={"count": friction},
            confidence=float(conf),
            evidence={"signals": ["correction", "frustration"], "count": friction, "threshold": 6},
            last_seen=now,
        ))

    return patterns

async def upsert_patterns(conn, patterns: list[Pattern]) -> int:
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
