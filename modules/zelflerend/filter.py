# modules/zelflerend/filter.py

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Tuple, Optional

BASE_DIR = Path(__file__).resolve().parents[2]  # .../loesoe
MEMORY_DIR = BASE_DIR / "data" / "memory"
ZELFLEREN_FILE = MEMORY_DIR / "zelfleren.json"

DEFAULT_STATE: Dict[str, Any] = {
    "version": 1,
    "users": {}
}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_file() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    if not ZELFLEREN_FILE.exists():
        ZELFLEREN_FILE.write_text(
            json.dumps(DEFAULT_STATE, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def _load_state() -> Dict[str, Any]:
    _ensure_file()
    try:
        return json.loads(ZELFLEREN_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # backup corrupte file
        backup = ZELFLEREN_FILE.with_suffix(".bak")
        ZELFLEREN_FILE.replace(backup)
        ZELFLEREN_FILE.write_text(
            json.dumps(DEFAULT_STATE, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return DEFAULT_STATE.copy()


def _save_state(state: Dict[str, Any]) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    ZELFLEREN_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _get_user_state(state: Dict[str, Any], user_id: int | str) -> Dict[str, Any]:
    uid = str(user_id)
    if "users" not in state:
        state["users"] = {}
    if uid not in state["users"]:
        state["users"][uid] = {
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "preferences": [],      # lijst van {text, created_at}
            "patterns": {},         # pattern → count
            "mood": {
                "last": None,       # "positief" / "neutraal" / "negatief"
                "last_updated": None,
            },
            "stats": {
                "total_prompts": 0,
                "last_prompt_at": None,
            },
        }
    return state["users"][uid]


def _detect_preferences(prompt_lower: str, original: str) -> Optional[str]:
    """
    Herken zinnen zoals:
    - 'vanaf nu ...'
    - 'voortaan wil ik dat ...'
    - 'ik wil dat je ...'
    """
    triggers = ["vanaf nu", "voortaan", "ik wil dat", "ik wil graag dat", "ik wil dat je", "altijd als ik zeg"]
    if any(t in prompt_lower for t in triggers):
        return original.strip()
    return None


def _detect_mood(prompt_lower: str) -> Optional[str]:
    """
    Super simpele mood-detectie. Later kun je dit uitbouwen.
    """
    negatieve = ["kut", "fk", "fucking", "stress", "gestrest", "boos", "woest", "geneukt", "klote"]
    positieve = ["nice", "lekker", "top", "chill", "rustig", "relaxed", "blij", "trots"]

    if any(w in prompt_lower for w in negatieve):
        return "negatief"
    if any(w in prompt_lower for w in positieve):
        return "positief"
    return "neutraal"


def _update_patterns(user_state: Dict[str, Any], prompt_lower: str) -> None:
    """
    Telt hoe vaak jij bepaalde dingen vraagt (gewoontes).
    Denk aan:
    - 'loesoe time'
    - 'crypto update'
    - 'heb je een crypto update'
    - 'ghost', 'spook', 'health', etc.
    """
    patterns = {
        "loesoe_time": ["loesoe time"],
        "crypto_update": ["crypto update", "heb je een crypto update"],
        "ghost_module": ["ghost", "spook", "dwaallicht"],
        "health_module": ["health", "intake", "vragenlijst"],
        "dev_mode": ["dev modus", "dev-modus", "developer", "code"],
    }

    if "patterns" not in user_state:
        user_state["patterns"] = {}

    for key, triggers in patterns.items():
        if any(t in prompt_lower for t in triggers):
            user_state["patterns"][key] = user_state["patterns"].get(key, 0) + 1


def _clean_prompt(original: str) -> str:
    """
    Haalt 'onthoud dit', 'vanaf nu' etc een beetje uit de prompt zodat GPT-5
    minder ruis ziet, maar jouw wens blijft wel duidelijk.
    """
    replacements = [
        "vanaf nu",
        "voortaan",
        "ik wil dat je",
        "ik wil dat",
        "ik wil graag dat",
        "onthoud dit",
        "mag je onthouden",
    ]
    cleaned = original
    for r in replacements:
        cleaned = cleaned.replace(r, "")
        cleaned = cleaned.replace(r.capitalize(), "")
    cleaned = " ".join(cleaned.split())
    return cleaned if cleaned.strip() else original


def leer_filter(
    user_id: int | str,
    prompt: str,
    meta: Optional[Dict[str, Any]] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Hoofdfunctie voor de zelflerende laag.

    - user_id: ID uit JWT (bijv. 1)
    - prompt: originele gebruikersinput
    - meta: optioneel dict met extra info, bijv:
        {
          "source": "chat",
          "module": "dashboard",
          "timestamp": "...",
        }

    Return:
    - cleaned_prompt: string die door mag naar GPT-5 / model_router
    - insight: dict met info voor logging / dashboard / slimheidsmeter
    """
    if meta is None:
        meta = {}

    state = _load_state()
    user_state = _get_user_state(state, user_id)

    prompt_lower = prompt.lower()
    now = _now_iso()

    # Stats updaten
    stats = user_state.setdefault("stats", {})
    stats["total_prompts"] = int(stats.get("total_prompts", 0)) + 1
    stats["last_prompt_at"] = now

    # Patterns / gewoontes
    _update_patterns(user_state, prompt_lower)

    # Voorkeuren
    new_preference = _detect_preferences(prompt_lower, prompt)
    if new_preference:
        prefs = user_state.setdefault("preferences", [])
        prefs.append(
            {
                "text": new_preference,
                "created_at": now,
            }
        )

    # Mood
    new_mood = _detect_mood(prompt_lower)
    mood_state = user_state.setdefault("mood", {})
    mood_state["last"] = new_mood
    mood_state["last_updated"] = now

    user_state["updated_at"] = now

    # Opslaan
    _save_state(state)

    insight = {
        "user_id": str(user_id),
        "saved_at": now,
        "has_new_preference": bool(new_preference),
        "last_mood": new_mood,
        "total_prompts": stats["total_prompts"],
        "patterns": user_state.get("patterns", {}),
    }

    cleaned_prompt = _clean_prompt(prompt)
    return cleaned_prompt, insight


def get_user_state(user_id: int | str) -> Dict[str, Any]:
    """
    Handige helper voor dashboard / API om de ruwe user-state op te vragen.
    """
    state = _load_state()
    return _get_user_state(state, user_id)
