from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..interfaces import MLContext, MLExplain, MLInputRef, MLModule, MLResult


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _to_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        if isinstance(x, bool):
            return float(int(x))
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, str):
            x = x.strip().replace(",", ".")
            return float(x)
        return default
    except Exception:
        return default


def _normalize_confidence(conf_raw: Any) -> float:
    c = _to_float(conf_raw, default=0.0)
    if c > 1.0:
        c = c / 100.0
    return _clamp01(c)


def _try_parse_json_object(s: str) -> Optional[Dict[str, Any]]:
    s = s.strip()
    if not (s.startswith("{") and s.endswith("}")):
        return None
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _extract_level(value: Any) -> str:
    """
    Value kan zijn:
    - dict: {"level":"high"}
    - string: "high"
    - stringified JSON: '{"level":"high"}'
    - anders: unknown
    """
    # dict direct
    if isinstance(value, dict):
        lvl = value.get("level")
        if isinstance(lvl, str) and lvl.strip():
            return lvl.strip().lower()
        return "unknown"

    # string: eerst proberen JSON object
    if isinstance(value, str) and value.strip():
        s = value.strip()

        obj = _try_parse_json_object(s)
        if obj is not None:
            lvl = obj.get("level")
            if isinstance(lvl, str) and lvl.strip():
                return lvl.strip().lower()
            return "unknown"

        # anders plain string
        return s.lower()

    return "unknown"


def _level_to_base(level: str) -> float:
    m = {
        "high": 1.0,
        "medium": 0.6,
        "low": 0.2,
    }
    return float(m.get(level, 0.0))


def _find_explain_level_pattern(patterns: list[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for p in patterns:
        if p.get("pattern_type") == "preference" and p.get("key") == "explain_level":
            return p
    return None


class ExplainPreferenceScore(MLModule):
    name = "explain_preference_score"
    version = "0.2.1"

    def compute(self, ctx: MLContext) -> MLResult:
        now = datetime.now(timezone.utc).isoformat()
        patterns = ctx.patterns or []

        p = _find_explain_level_pattern(patterns)

        if not p:
            return MLResult(
                module=self.name,
                version=self.version,
                computed_at_utc=now,
                kind="score",
                status="warn",
                inputs=[
                    MLInputRef(
                        source="learning_patterns",
                        key="explain_level",
                        note="no matching preference pattern found",
                    )
                ],
                score=0.0,
                flags={"has_preference": False},
                payload={"level": None, "confidence": 0.0, "base_score": 0.0},
                explain=MLExplain(
                    text="Geen explain_level voorkeur gevonden in learning patterns; score blijft 0.0.",
                    debug={"searched": {"pattern_type": "preference", "key": "explain_level"}},
                ),
            )

        conf_raw = p.get("confidence", 0)
        conf = _normalize_confidence(conf_raw)

        raw_value = p.get("value")
        level = _extract_level(raw_value)
        base = _level_to_base(level)

        score = round(_clamp01(base * conf), 4)

        return MLResult(
            module=self.name,
            version=self.version,
            computed_at_utc=now,
            kind="score",
            status="ok",
            inputs=[
                MLInputRef(
                    source="learning_patterns",
                    id=str(p.get("id")) if p.get("id") is not None else None,
                    key="explain_level",
                    note="preference pattern used for deterministic score",
                )
            ],
            score=score,
            flags={
                "has_preference": True,
                "pref_high": level == "high",
                "pref_medium": level == "medium",
                "pref_low": level == "low",
            },
            payload={
                "level": level,
                "raw_value": raw_value,
                "base_score": base,
                "confidence": conf,
                "raw_confidence": conf_raw,
                "subject": p.get("subject"),
                "last_seen": p.get("last_seen"),
            },
            explain=MLExplain(
                text=f"Explain preference '{level}' met confidence {conf:.2f} → score {score:.2f} (base {base:.2f} × confidence).",
                debug={
                    "pattern": {
                        "id": p.get("id"),
                        "pattern_type": p.get("pattern_type"),
                        "key": p.get("key"),
                        "value": raw_value,
                        "confidence": p.get("confidence"),
                        "last_seen": p.get("last_seen"),
                    }
                },
            ),
        )
