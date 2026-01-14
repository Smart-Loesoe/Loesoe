from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Verdeling:
# - Modules:       max 35 punten
# - Self-learning: max 50 punten (incl. emotie)
# - Usage:         max 15 punten
MAX_MODULE_POINTS = 35.0
MAX_SELF_POINTS = 50.0
MAX_USAGE_POINTS = 15.0


@dataclass
class ModuleStatus:
    key: str
    status: str  # "ok", "warn", "off"
    note: Optional[str] = None


@dataclass
class SelfLearningStatus:
    has_data: bool
    avg_score: Optional[float] = None  # 0–10
    user_score: Optional[float] = None
    preferences_count: int = 0
    patterns: Optional[Any] = None
    last_mood: Optional[str] = None    # 🔥 nieuw: emotie


@dataclass
class LastSessionStatus:
    last_action: Optional[datetime] = None
    estimated_dev_minutes: int = 0


def _score_modules(modules: List[ModuleStatus]) -> float:
    """
    0–35 punten op basis van systeemstatus.
    Kernmodules krijgen iets meer gewicht.
    """
    if not modules:
        return 0.0

    core_keys = {
        "auth",
        "database",
        "database_conn",
        "dashboard_api",
        "model_router",
        "chat_api",
        "zelflerend_geheugen",
    }

    score = 0.0
    base_per_module = MAX_MODULE_POINTS / max(len(modules), 1)

    for m in modules:
        weight = 1.3 if m.key in core_keys else 1.0
        status = (m.status or "off").lower()

        if status == "ok":
            score += base_per_module * weight
        elif status == "warn":
            score += base_per_module * 0.5 * weight

    return min(score, MAX_MODULE_POINTS)


def _score_emotion(last_mood: Optional[str]) -> float:
    """
    Kleine bonus/malus (-5 tot +5) op basis van laatste emotie.
    We gaan uit van een simpele tekstwaarde, bijv.:
    - 'rustig', 'kalm', 'relaxed', 'blij', 'gemotiveerd' -> bonus
    - 'stress', 'gestrest', 'overprikkeld', 'boos', 'bang' -> malus
    Alles wat we niet herkennen -> 0.
    """
    if not last_mood:
        return 0.0

    mood = last_mood.strip().lower()

    positieve_triggers = [
        "rustig", "kalm", "relaxed", "blij", "tevreden",
        "gemotiveerd", "gefocust", "in balans", "chill",
    ]
    negatieve_triggers = [
        "stress", "gestrest", "overprikkeld", "boos", "bang",
        "angstig", "onrustig", "moe", "op", "overwhelmed",
    ]

    if any(t in mood for t in positieve_triggers):
        return 4.0  # stevige maar niet extreme bonus
    if any(t in mood for t in negatieve_triggers):
        return -4.0  # stevige maar niet extreme malus

    return 0.0


def _score_self_learning(sl: SelfLearningStatus) -> float:
    """
    0–50 punten op basis van zelflerend geheugen & gedrag.
    Dit is de zwaarste factor. Emotie geeft een kleine +/- correctie.
    """
    base_score = 0.0

    # 1) Heeft Loesoe überhaupt self-learning data?
    if sl.has_data:
        base_score += 10.0  # basisbonus

    # 2) Gemiddelde self-learning score 0–10 → max 30 punten
    if sl.avg_score is not None:
        clamped = max(0.0, min(sl.avg_score, 10.0))
        base_score += (clamped / 10.0) * 30.0

    # 3) Aantal voorkeuren / patronen (max 10 tellen mee) → max 10 punten
    prefs = max(0, min(sl.preferences_count, 10))
    base_score += (prefs / 10.0) * 10.0

    # 4) Emotie-factor (-5 tot +5) als lichte correctie
    emo_bonus = _score_emotion(sl.last_mood)

    score = base_score + emo_bonus
    return max(0.0, min(score, MAX_SELF_POINTS))


def _score_usage(last_session: LastSessionStatus) -> float:
    """
    0–15 punten op basis van recent gebruik + dev-minuten.
    Minder belangrijk dan self-learning; meer fine-tuning.
    """
    score = 0.0

    if last_session.last_action is None:
        return 0.0

    now = datetime.now(timezone.utc)
    diff = now - last_session.last_action
    hours = diff.total_seconds() / 3600.0

    if hours <= 6:
        score += 13.0
    elif hours <= 24:
        score += 10.0
    elif hours <= 72:
        score += 7.0
    elif hours <= 168:
        score += 4.0

    if last_session.estimated_dev_minutes >= 60:
        score = min(score + 2.0, MAX_USAGE_POINTS)

    return min(score, MAX_USAGE_POINTS)


def _extract_last_session(last_session_raw: Dict[str, Any]) -> LastSessionStatus:
    """
    Pakt de meest recente user uit last_session.users.
    """
    users = (last_session_raw or {}).get("users") or {}
    if not users:
        return LastSessionStatus(last_action=None, estimated_dev_minutes=0)

    target_user: Optional[Dict[str, Any]] = None
    target_dt: Optional[datetime] = None

    for _uid, u in users.items():
        ts = u.get("last_action")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts)
        except Exception:
            continue
        if target_dt is None or dt > target_dt:
            target_dt = dt
            target_user = u

    if target_user is None:
        first = next(iter(users.values()))
        ts = first.get("last_action")
        try:
            dt = datetime.fromisoformat(ts) if ts else None
        except Exception:
            dt = None
        est = int(first.get("estimated_dev_minutes", 0) or 0)
        return LastSessionStatus(last_action=dt, estimated_dev_minutes=est)

    est = int(target_user.get("estimated_dev_minutes", 0) or 0)
    return LastSessionStatus(last_action=target_dt, estimated_dev_minutes=est)


def calculate_slimheidsmeter(
    modules_raw: List[Dict[str, Any]],
    self_learning_raw: Dict[str, Any],
    last_session_raw: Dict[str, Any],
) -> float:
    """
    Hoofdfunctie: rekent alles om naar een score tussen 0.0 en 100.0
    met nadruk op zelflerend geheugen + lichte emotie-correctie.
    """

    modules = [
        ModuleStatus(
            key=m.get("key", ""),
            status=str(m.get("status", "off")).lower(),
            note=m.get("note"),
        )
        for m in modules_raw
    ]

    sl = SelfLearningStatus(
        has_data=bool(self_learning_raw.get("has_data", False)),
        avg_score=self_learning_raw.get("avg_score"),
        user_score=self_learning_raw.get("user_score"),
        preferences_count=int(self_learning_raw.get("preferences_count", 0) or 0),
        patterns=self_learning_raw.get("patterns"),
        last_mood=self_learning_raw.get("last_mood"),  # 🔥 emotie erin
    )

    ls = _extract_last_session(last_session_raw or {})

    modules_score = _score_modules(modules)          # 0–35
    self_learning_score = _score_self_learning(sl)   # 0–50
    usage_score = _score_usage(ls)                  # 0–15

    total = modules_score + self_learning_score + usage_score
    total = max(0.0, min(total, 100.0))
    return round(total, 1)
