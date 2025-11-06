from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict

from ..memory.preferences import get_preferences, set_preferences, clear_preferences
from ..memory.feedback import apply_signals

# 👇 Nieuwe, eigen prefix → geen clash met /memory/{key}
router = APIRouter(prefix="/prefs", tags=["preferences"])

class PreferencesPatch(BaseModel):
    diff: Dict[str, Any] = Field(default_factory=dict)

class FeedbackIn(BaseModel):
    text: str

@router.get("/preferences")
def get_prefs() -> Dict[str, Any]:
    """Lees alle voorkeuren (tone, verbosity, emojis, etc.)."""
    return get_preferences()

@router.post("/preferences")
def patch_prefs(payload: PreferencesPatch) -> Dict[str, Any]:
    """Patch/merge voorkeuren. Voorbeeld diff:
    {"style":{"tone":"zakelijk","emojis":false}}
    """
    if not isinstance(payload.diff, dict):
        raise HTTPException(status_code=400, detail="diff must be an object")
    return set_preferences(payload.diff)

@router.post("/feedback")
def give_feedback(payload: FeedbackIn) -> Dict[str, Any]:
    """Leer van tekst-signalen (bijv. 'korter', 'straattaal', 'jip en janneke')."""
    return apply_signals(payload.text or "")

@router.post("/clear-prefs")
def clear_prefs() -> Dict[str, str]:
    """Wis alléén de voorkeuren (niet ST/MT/LT memory)."""
    clear_preferences()
    return {"status": "ok"}
