from __future__ import annotations

from datetime import datetime, timezone

from ..interfaces import MLContext, MLExplain, MLInputRef, MLModule, MLResult


class DummyScoreModule(MLModule):
    """
    Dummy module: levert altijd een vaste score terug.
    Doel: contract + registry testen (geen logica, geen side effects).
    """

    name = "dummy_score"
    version = "0.1.0"

    def compute(self, ctx: MLContext) -> MLResult:
        now = datetime.now(timezone.utc).isoformat()

        return MLResult(
            module=self.name,
            version=self.version,
            computed_at_utc=now,
            kind="score",
            status="ok",
            inputs=[
                MLInputRef(source="custom", note="dummy module gebruikt geen echte inputs")
            ],
            score=0.0,
            flags={"active": False},
            payload={"note": "dummy score (no impact)"},
            explain=MLExplain(
                text="DummyScoreModule geeft altijd score 0.0 terug. Geen impact, alleen test."
            ),
        )
