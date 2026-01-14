from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional

from api.db.database import init_database, close_database, get_pool
from api.ml.interfaces import MLContext
from api.ml.registry import get_registry


DEFAULT_MODULES = [
    "dummy_score",
    "explain_preference_score",
    "patterns_volume_anomaly",
]


async def fetch_patterns(limit: int = 200) -> List[Dict[str, Any]]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, subject, pattern_type, key, value, confidence, evidence, last_seen, created_at, updated_at
            FROM learning_patterns
            ORDER BY COALESCE(last_seen, updated_at, created_at) DESC
            LIMIT $1
            """,
            limit,
        )
        return [dict(r) for r in rows]


def _maybe_filter_by_subject(patterns: List[Dict[str, Any]], user_id: Optional[str]) -> List[Dict[str, Any]]:
    """
    Filter alleen op subject ALS er echt matches zijn.
    Zo voorkom je dat patterns verdwijnen wanneer subject NULL/anders is.
    """
    if user_id is None:
        return patterns

    matched = [p for p in patterns if str(p.get("subject")) == str(user_id)]
    if matched:
        return matched

    # Geen matches? Dan niet filteren (subject is dan leeg/anders)
    return patterns


def _print_result(name: str, r) -> None:
    print(f"\n=== {name} ===")
    print("status:", r.status)
    print("kind:", r.kind)
    print("score:", r.score)
    print("flags:", r.flags)
    print("explain:", r.explain.text)

    # Compact extra info (handig bij DB value-format issues)
    if isinstance(getattr(r, "payload", None), dict):
        payload = r.payload
        if "level" in payload or "raw_value" in payload or "total_patterns" in payload:
            compact = {k: payload.get(k) for k in ["level", "raw_value", "confidence", "total_patterns"] if k in payload}
            print("payload:", compact)

    if r.explain.debug:
        print("debug keys:", list(r.explain.debug.keys()))


async def main(user_id: Optional[str] = None, limit: int = 200) -> int:
    await init_database()

    try:
        patterns = await fetch_patterns(limit=limit)
        patterns = _maybe_filter_by_subject(patterns, user_id)

        ctx = MLContext(user_id=user_id, patterns=patterns)
        reg = get_registry()

        ran_any = False
        missing = []

        for name in DEFAULT_MODULES:
            if name not in reg:
                missing.append(name)
                continue

            ran_any = True
            r = reg[name].compute(ctx)
            _print_result(name, r)

        if missing:
            print("\n[info] ontbrekende modules (nog niet aanwezig is ok):", missing)

        if not ran_any:
            print("[warn] geen modules gedraaid (registry leeg?)")
            return 2

        return 0

    finally:
        await close_database()


if __name__ == "__main__":
    # user_id blijft default "2" zoals jij gebruikt
    user_id = os.getenv("LOESOE_USER_ID", "2")
    raise SystemExit(asyncio.run(main(user_id=user_id, limit=200)))
