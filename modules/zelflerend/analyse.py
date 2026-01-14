# modules/zelflerend/analyse.py

from __future__ import annotations

from pathlib import Path
import json
from typing import Any, Dict

from .filter import _load_state  # type: ignore


def _score_single_user(user_state: Dict[str, Any]) -> float:
    """
    Berekent een simpele score 0–100 op basis van:
    - aantal prompts
    - aantal patterns
    - aantal voorkeuren

    Later kun je dit vervangen door een slimmer model.
    """
    stats = user_state.get("stats", {})
    patterns = user_state.get("patterns", {})
    prefs = user_state.get("preferences", [])

    total_prompts = int(stats.get("total_prompts", 0))
    pattern_count = sum(patterns.values())
    pref_count = len(prefs)

    score = 0.0

    # prompts tellen mee tot max 40 punten
    score += min(total_prompts / 10.0, 40.0)  # elke 10 prompts ≈ 1 punt

    # patterns max 30
    score += min(pattern_count * 2.0, 30.0)

    # voorkeuren max 30
    score += min(pref_count * 3.0, 30.0)

    return max(0.0, min(score, 100.0))


def get_global_self_learning_summary() -> Dict[str, Any]:
    """
    Wordt gebruikt door dashboard.py om:
    - slimheidsmeter v2 te voeden
    - zelflerend-blok te vullen
    """
    state = _load_state()
    users = state.get("users", {})

    user_scores: Dict[str, float] = {}
    for uid, u_state in users.items():
        user_scores[uid] = _score_single_user(u_state)

    if user_scores:
        avg_score = sum(user_scores.values()) / len(user_scores)
    else:
        avg_score = 0.0

    return {
        "version": state.get("version", 1),
        "user_scores": user_scores,
        "avg_score": round(avg_score, 1),
        "has_data": bool(users),
    }
