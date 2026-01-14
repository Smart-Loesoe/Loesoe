# loesoe/modules/geheugen/zelfleren.py
from __future__ import annotations
import json, os, uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any

LEARNING_PATH = os.path.join("data", "memory", "learning.json")

def ensure_learning_store():
    os.makedirs(os.path.dirname(LEARNING_PATH), exist_ok=True)
    if not os.path.exists(LEARNING_PATH):
        with open(LEARNING_PATH, "w", encoding="utf-8") as f:
            json.dump({"events": [], "scores": {}}, f, ensure_ascii=False, indent=2)

def _load() -> Dict[str, Any]:
    ensure_learning_store()
    with open(LEARNING_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(data: Dict[str, Any]):
    with open(LEARNING_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def record_event(user_id: str, event_type: str, data: Dict[str, Any]) -> bool:
    store = _load()
    store["events"].append({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": event_type,
        "data": data,
        "ts": datetime.utcnow().isoformat(),
    })
    # eenvoudige score-update bij feedback
    if event_type == "feedback":
        sid = data.get("suggestion_id")
        act = data.get("action")
        if sid:
            scores = store.setdefault("scores", {})
            cur = scores.get(sid, 0.0)
            delta = 0.5 if act == "accept" else -0.5
            scores[sid] = max(-2.0, min(5.0, cur + delta))
    _save(store)
    return True

def get_suggestions(user_id: str, modules: Dict[str, bool]) -> List[Dict[str, Any]]:
    """
    Genereer eenvoudige, contextuele suggesties.
    Score-bonus o.b.v. historiek (accept/dismiss).
    """
    base = [
        {
            "id": "sug_enable_selflearning",
            "title": "Activeer zelflerend geheugen",
            "detail": "Zet SelfLearning aan zodat Loesoe voorkeuren en patronen leert.",
            "weight": 1.0,
            "cond": lambda m: not m.get("SelfLearning", False),
        },
        {
            "id": "sug_run_tests",
            "title": "Draai de SSE/endpoint tests",
            "detail": "Voer sse_test.ps1 en test_endpoints.ps1 uit na elke build.",
            "weight": 0.8,
            "cond": lambda m: True,
        },
        {
            "id": "sug_dev_assistant",
            "title": "Start Developer-Assistent (Fase 20)",
            "detail": "Laat Loesoe code lezen/genereren in de /workspace sandbox.",
            "weight": 1.0,
            "cond": lambda m: not m.get("DeveloperAssistant", False),
        },
        {
            "id": "sug_system_to_app",
            "title": "Probeer System-to-App (Fase 21)",
            "detail": "Converteer een bestaand project naar React Native/Flutter.",
            "weight": 0.9,
            "cond": lambda m: m.get("DeveloperAssistant", False) and not m.get("SystemToApp", False),
        },
        {
            "id": "sug_backup",
            "title": "Maak een back-up",
            "detail": "Zorg voor dagelijkse back-up van memory en uploads (Plan Fase 24).",
            "weight": 0.7,
            "cond": lambda m: True,
        },
    ]

    store = _load()
    scores = store.get("scores", {})
    out = []
    now = datetime.utcnow()
    for s in base:
        if s["cond"](modules):
            sid = s["id"]
            bonus = scores.get(sid, 0.0)
            out.append({
                "id": sid,
                "title": s["title"],
                "detail": s["detail"],
                "weight": round(s["weight"] + bonus, 2),
                "created_at": now.isoformat(),
            })
    # sorteer op gewicht (relevantie)
    out.sort(key=lambda x: x["weight"], reverse=True)
    return out
