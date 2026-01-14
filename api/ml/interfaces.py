from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


MLStatus = Literal["ok", "warn", "error"]
MLResultKind = Literal["score", "flags", "suggestion", "summary"]


@dataclass(frozen=True)
class MLInputRef:
    """
    Verwijzing naar een bron die gebruikt is voor een ML-resultaat.
    Dit maakt outputs auditbaar en uitlegbaar.
    """
    source: Literal["learning_patterns", "learning_events", "memory", "custom"]
    id: Optional[str] = None
    key: Optional[str] = None
    note: Optional[str] = None


@dataclass(frozen=True)
class MLExplain:
    """
    Menselijke uitleg + (optioneel) technische details.
    """
    text: str
    debug: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MLResult:
    """
    Standaard output van één ML-module.
    Alleen data — geen side effects.
    """
    module: str
    version: str
    computed_at_utc: str  # ISO8601 UTC string

    kind: MLResultKind
    status: MLStatus = "ok"

    # Input bronnen die zijn gebruikt (audit trail)
    inputs: List[MLInputRef] = field(default_factory=list)

    # Resultaten (alleen data)
    score: Optional[float] = None              # 0..1 of 0..100 (module definieert, maar moet uitleggen)
    flags: Dict[str, bool] = field(default_factory=dict)
    suggestion: Optional[str] = None           # bijv. "Wil je X doen?"
    payload: Dict[str, Any] = field(default_factory=dict)

    # Uitleg verplicht
    explain: MLExplain = field(default_factory=lambda: MLExplain(text=""))


@dataclass(frozen=True)
class MLContext:
    """
    Context die aan ML-modules wordt meegegeven.
    LET OP: alleen read-only data, geen clients met side effects.
    """
    user_id: Optional[str] = None
    now_utc: Optional[str] = None

    # Snapshot van patterns (bijv. uit DB opgehaald door caller)
    patterns: List[Dict[str, Any]] = field(default_factory=list)

    # Extra (optioneel) – caller bepaalt wat erin zit
    meta: Dict[str, Any] = field(default_factory=dict)


class MLModule:
    """
    Interface (contract) voor een ML-module.
    Implementaties moeten deterministisch zijn.
    """

    name: str = "unnamed"
    version: str = "0.0.0"

    def compute(self, ctx: MLContext) -> MLResult:
        """
        Compute is pure: input -> output.
        - Geen DB writes
        - Geen netwerk calls
        - Geen state
        """
        raise NotImplementedError
