from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from ..interfaces import MLContext, MLExplain, MLInputRef, MLModule, MLResult


class PatternsVolumeAnomaly(MLModule):
    """
    Deterministische anomaly flag op basis van aantal patterns.
    Read-only: gebruikt alleen ctx.patterns.
    """

    name = "patterns_volume_anomaly"
    version = "0.1.0"

    # thresholds: bewust simpel en transparant
    MIN_EXPECTED = 1
    HIGH_VOLUME = 100

    def compute(self, ctx: MLContext) -> MLResult:
        now = datetime.now(timezone.utc).isoformat()

        patterns = ctx.patterns or []
        total = len(patterns)

        # Type breakdown (transparant)
        by_type: Dict[str, int] = {}
        for p in patterns:
            t = str(p.get("pattern_type") or "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        low = total < self.MIN_EXPECTED
        high = total >= self.HIGH_VOLUME

        # score: 0..1, puur indicatief (geen "AI")
        # low -> 0.0, normal -> 0.5, high -> 1.0
        if low:
            score = 0.0
            status = "warn"
            msg = f"Weinig patterns gevonden ({total}). Mogelijk nog weinig learning data."
        elif high:
            score = 1.0
            status = "warn"
            msg = f"Veel patterns gevonden ({total}). Check of ingest/derive te agressief is."
        else:
            score = 0.5
            status = "ok"
            msg = f"Patterns volume normaal ({total})."

        return MLResult(
            module=self.name,
            version=self.version,
            computed_at_utc=now,
            kind="flags",
            status=status,  # ok/warn
            inputs=[MLInputRef(source="learning_patterns", note="count patterns + breakdown by type")],
            score=score,
            flags={
                "low_volume": low,
                "high_volume": high,
                "normal_volume": (not low) and (not high),
            },
            payload={
                "total_patterns": total,
                "by_type": by_type,
                "thresholds": {"min_expected": self.MIN_EXPECTED, "high_volume": self.HIGH_VOLUME},
            },
            explain=MLExplain(
                text=msg,
                debug={"total": total, "by_type": by_type},
            ),
        )
