# api/chat.py

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List, Any
from datetime import datetime

# ✅ Auth – zelfde als dashboard/memory
try:
    from api.auth.routes import get_current_user
except ImportError:  # fallback
    from auth.routes import get_current_user  # type: ignore

# ✅ Model-router: Loesoe’s GPT-antwoord
try:
    from api.model_router import generate_reply
except Exception:
    async def generate_reply(
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        analysis: Optional[Dict[str, Any]] = None,
        memory_snapshot: Optional[Dict[str, Any]] = None,
    ) -> str:
        return f"Echo: {message}"

# ✅ Zelflerend analyse (oude 20A/20B-module) – optioneel
try:
    from modules.zelflerend.analyse import analyse_bericht as _analyse_bericht
except Exception:
    _analyse_bericht = None

# ✅ NIEUW: behavior scoring engine (20C)
try:
    from modules.zelflerend.scoring import score_message
except Exception:
    # Fallback zodat chat niet crasht als scoring ontbreekt
    def score_message(message: str, history: Optional[List[str]] = None) -> Dict[str, Any]:
        text = message or ""
        return {
            "version": 0,
            "emotion": {
                "label": "onbekend",
                "confidence": 0.0,
                "energy": 0.0,
                "stress": 0.0,
            },
            "intent": {
                "label": "smalltalk",
                "confidence": 0.0,
                "tags": [],
            },
            "behavior": {
                "importance": 0.0,
                "novelty": 0.0,
                "habit_strength": 0.0,
                "risk": 0.0,
            },
            "raw": {
                "length": len(text),
                "word_count": len(text.split()),
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
        }

# ✅ Helpers uit api.memory – zodat we hetzelfde pad/format gebruiken
try:
    from api.memory import (
        ZELFLEREN_PATH,
        _default_selflearn,
        _load_json,
        _save_json,
        _get_or_create_selflearn_user,
        _apply_scores_to_user_block,
    )
except ImportError:
    ZELFLEREN_PATH = None

    def _default_selflearn() -> Dict[str, Any]:
        return {"version": 1, "users": {}}

    def _load_json(path, default=None) -> Dict[str, Any]:
        return default or {"version": 1, "users": {}}

    def _save_json(path, data: Dict[str, Any]) -> None:
        return None

    def _get_or_create_selflearn_user(data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        users = data.setdefault("users", {})
        uid = str(user_id)
        users.setdefault(uid, {})
        return users[uid]

    def _apply_scores_to_user_block(user_block: Dict[str, Any], scores: Dict[str, Any]) -> None:
        return None


# ✅ NIEUW: last_session-helper voor Slimheidsmeter V2 usage-score
try:
    from modules.last_session_helper import mark_action
except Exception:
    # Fallback: no-op als helper ontbreekt
    def mark_action(
        user_id: int,
        action: str = "action",
        modules_used: Optional[List[str]] = None,
        add_dev_minutes: int = 0,
    ) -> None:
        return None


# ✅ NIEUW: chat-history logger
try:
    from api.chat_logger import log_chat
except Exception:
    # Fallback zodat chat niet crasht als logger ontbreekt
    def log_chat(
        message: str,
        reply: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        return None


router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    analysis: Optional[Dict[str, Any]] = None
    scores: Optional[Dict[str, Any]] = None  # behavior_scores richting frontend


def _run_analysis(message: str, user_id: Optional[int]) -> Optional[Dict[str, Any]]:
    """Oude analyse-module (20A/20B)."""
    if _analyse_bericht is None:
        return None
    try:
        return _analyse_bericht(message=message, user_id=user_id)
    except Exception:
        return None


def _update_behavior_memory(user_id: Optional[int], scores: Dict[str, Any]) -> None:
    """Schrijf behavior-scores weg naar zelfleren.json voor deze user."""
    if ZELFLEREN_PATH is None or user_id is None:
        return

    try:
        data = _load_json(ZELFLEREN_PATH, _default_selflearn())
        user_block = _get_or_create_selflearn_user(data, user_id)

        # bestaande helper uit api.memory doet al:
        # - behavior_log append
        # - emotion/intent counters
        # - behavior_summary updaten
        _apply_scores_to_user_block(user_block, scores)

        user_block["last_updated"] = datetime.utcnow().isoformat() + "Z"
        _save_json(ZELFLEREN_PATH, data)
    except Exception:
        # Geen harde crash als geheugen stuk is
        pass


@router.post("", response_model=ChatResponse)
@router.post("/send", response_model=ChatResponse)
async def chat_endpoint(
    req: ChatRequest,
    current_user=Depends(get_current_user),
):
    """
    Centrale chat-endpoint.

    Flow:
    - auth → current_user
    - user_message normaliseren
    - optioneel: analyse_bericht (20A/20B)
    - NIEUW: score_message (20C) → behavior-scores
    - scores in zelfleren.json dumpen
    - generate_reply() oproepen met analysis + behavior_scores
    - mark_action() logt activiteit naar last_session.json (20D)
    - log_chat() schrijft naar logboek/chat_history
    - reply + scores terug naar frontend
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user_id = getattr(current_user, "id", None)

    user_message = (req.message or "").strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Leeg bericht")

    # 1️⃣ Oude analyse-laag (mag ook None zijn)
    analysis = _run_analysis(user_message, user_id)

    # 2️⃣ NIEUW: behavior scoring op dit bericht
    scores = score_message(user_message, history=None)

    # 3️⃣ Wegschrijven naar zelflerend geheugen
    _update_behavior_memory(user_id, scores)

    # 4️⃣ Analysis verrijken met behavior_scores
    if analysis is None:
        combined_analysis: Optional[Dict[str, Any]] = {"behavior_scores": scores}
    else:
        combined_analysis = dict(analysis)
        combined_analysis["behavior_scores"] = scores

    # 5️⃣ GPT-antwoord via model_router
    history: List[Dict[str, str]] = []  # later kun je hier echte chatgeschiedenis doorgeven
    memory_snapshot: Optional[Dict[str, Any]] = None

    reply = await generate_reply(
        message=user_message,
        history=history,
        analysis=combined_analysis,
        memory_snapshot=memory_snapshot,
    )

    # 6️⃣ NIEUW: usage-log voor Slimheidsmeter V2
    try:
        if user_id is not None:
            mark_action(
                user_id=user_id,
                action="chat",
                modules_used=["chat_api", "zelflerend_geheugen"],
                add_dev_minutes=0,
            )
    except Exception as e:
        # dashboard mag nooit crashen omdat logging faalt
        print(f"[warn] mark_action(chat) failed: {e.__class__.__name__}: {e}")

    # 7️⃣ NIEUW: chat-history logging naar logboek/chat_history
    try:
        meta: Dict[str, Any] = {
            "source": "api:/chat",
            "user_id": user_id,
            "has_analysis": analysis is not None,
            "has_behavior_scores": scores is not None,
        }
        log_chat(
            message=user_message,
            reply=reply,
            meta=meta,
        )
    except Exception as e:
        # Logging mag nooit het antwoord blokkeren
        print(f"[warn] log_chat failed: {e.__class__.__name__}: {e}")

    return ChatResponse(
        reply=reply,
        analysis=combined_analysis,
        scores=scores,
    )
