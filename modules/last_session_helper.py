from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json


DATA_DIR = Path("data") / "memory"
LAST_SESSION_PATH = DATA_DIR / "last_session.json"


@dataclass
class UserSessionState:
    last_login: Optional[str] = None
    last_logout: Optional[str] = None
    last_action: Optional[str] = None
    last_modules: List[str] = field(default_factory=list)
    estimated_dev_minutes: int = 0


def _load_state() -> Dict[str, Any]:
    if not LAST_SESSION_PATH.exists():
        return {
            "version": 1,
            "users": {}
        }
    try:
        return json.loads(LAST_SESSION_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[last_session] load failed, resetting: {e.__class__.__name__}: {e}")
        return {
            "version": 1,
            "users": {}
        }


def _save_state(state: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LAST_SESSION_PATH.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    # Kleine debug-log
    print(f"[last_session] saved to {LAST_SESSION_PATH} for users={list((state.get('users') or {}).keys())}")


def _ensure_user_state(state: Dict[str, Any], user_id: int) -> UserSessionState:
    users = state.setdefault("users", {})
    key = str(user_id)

    raw = users.get(key) or {}
    return UserSessionState(
        last_login=raw.get("last_login"),
        last_logout=raw.get("last_logout"),
        last_action=raw.get("last_action"),
        last_modules=raw.get("last_modules") or [],
        estimated_dev_minutes=int(raw.get("estimated_dev_minutes", 0) or 0),
    )


def _write_user_state(state: Dict[str, Any], user_id: int, user_state: UserSessionState) -> None:
    users = state.setdefault("users", {})
    key = str(user_id)

    users[key] = {
        "last_login": user_state.last_login,
        "last_logout": user_state.last_logout,
        "last_action": user_state.last_action,
        "last_modules": user_state.last_modules,
        "estimated_dev_minutes": int(user_state.estimated_dev_minutes),
    }


def mark_action(
    user_id: int,
    action: str = "action",
    modules_used: Optional[List[str]] = None,
    add_dev_minutes: int = 0,
) -> None:
    """
    Algemene helper om de laatste activiteit van een gebruiker bij te werken.

    - zet last_action op nu
    - voegt optioneel modules_used toe
    - verhoogt estimated_dev_minutes
    """
    state = _load_state()
    user_state = _ensure_user_state(state, user_id)

    now = datetime.now(timezone.utc).isoformat()

    user_state.last_action = now

    if modules_used:
        user_state.last_modules = list(modules_used)

    if add_dev_minutes > 0:
        user_state.estimated_dev_minutes += add_dev_minutes

    _write_user_state(state, user_id, user_state)
    _save_state(state)
    print(f"[last_session] mark_action user={user_id} action={action}")


def mark_login(user_id: int) -> None:
    """
    Helper om specifiek logins te loggen.
    """
    state = _load_state()
    user_state = _ensure_user_state(state, user_id)
    now = datetime.now(timezone.utc).isoformat()

    user_state.last_login = now
    user_state.last_action = now

    _write_user_state(state, user_id, user_state)
    _save_state(state)
    print(f"[last_session] mark_login user={user_id}")


def mark_logout(user_id: int) -> None:
    """
    Optioneel: logout loggen.
    """
    state = _load_state()
    user_state = _ensure_user_state(state, user_id)
    now = datetime.now(timezone.utc).isoformat()

    user_state.last_logout = now
    user_state.last_action = now

    _write_user_state(state, user_id, user_state)
    _save_state(state)
    print(f"[last_session] mark_logout user={user_id}")
