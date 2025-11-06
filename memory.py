from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, constr

from . import db

router = APIRouter(prefix="/memory", tags=["memory"])

# ======================
# Pydantic modellen
# ======================

class MemorySaveRequest(BaseModel):
    session_id: constr(min_length=8, max_length=128)
    label: constr(min_length=1, max_length=200)
    # text is optioneel; als data leeg is, slaan we op als data={"text": text}
    text: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)


class MemoryItem(BaseModel):
    id: int
    label: str
    data: Dict[str, Any]
    created_at: str
    # afgeleid of opgeslagen tekst, handig voor UI
    text: Optional[str] = None


class MemoryList(BaseModel):
    session_id: str
    items: List[MemoryItem]
    next_before_id: Optional[int] = None

# ======================
# Helpers
# ======================

def _derive_text(data: Dict[str, Any], given_text: Optional[str] = None) -> Optional[str]:
    """
    Eén uniforme tekst-waarde bepalen:
    - Prefer 'given_text' (direct aangeleverd)
    - Anders uit data: .text, .value, .note
    """
    if isinstance(given_text, str) and given_text.strip():
        return given_text
    if isinstance(data, dict):
        for k in ("text", "value", "note"):
            v = data.get(k)
            if isinstance(v, str) and v.strip():
                return v
    return None


def _has_text(data: Dict[str, Any]) -> bool:
    """True als data een bruikbare tekst bevat in text/value/note."""
    if not isinstance(data, dict):
        return False
    for k in ("text", "value", "note"):
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            return True
    return False

# ======================
# Routes
# ======================

@router.post("/save", response_model=MemoryItem, summary="Save")
def save(req: MemorySaveRequest):
    """
    Slaat een geheugen-item op. Als 'data' leeg is maar 'text' aanwezig,
    slaan we consistent op als data={"text": text}.
    """
    try:
        # zorg dat de sessie bestaat (no-op als al aanwezig)
        db.upsert_session(req.session_id)

        payload_data: Dict[str, Any] = dict(req.data or {})
        if not payload_data and isinstance(req.text, str):
            payload_data = {"text": req.text}

        ins = db.insert_memory(req.session_id, req.label, payload_data)

        return MemoryItem(
            id=ins["id"],
            label=req.label,
            data=payload_data,
            created_at=ins["created_at"],
            text=_derive_text(payload_data, req.text),
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database niet beschikbaar: {e}")


@router.get("", response_model=MemoryList, summary="List Memories")
def list_memories(
    session_id: constr(min_length=8, max_length=128) = Query(...),
    limit: int = Query(50, ge=1, le=200),
    before_id: Optional[int] = Query(None),
):
    """
    Retourneert items; naast 'data' geven we ook een afgeleid veld 'text'
    mee zodat de UI geen '{}' hoeft te tonen.
    """
    try:
        items_raw = db.fetch_memories(session_id, limit=limit, before_id=before_id)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database niet beschikbaar: {e}")

    items: List[MemoryItem] = []
    for m in items_raw:
        data = m.get("data") or {}
        items.append(
            MemoryItem(
                id=m["id"],
                label=m["label"],
                data=data,
                created_at=m["created_at"],
                text=_derive_text(data),
            )
        )

    next_before_id = items[0].id if items else None
    return MemoryList(session_id=session_id, items=items, next_before_id=next_before_id)


@router.delete("/{memory_id}", summary="Delete One")
def delete_one(
    memory_id: int,
    session_id: constr(min_length=8, max_length=128) = Query(...),
):
    try:
        ok = db.delete_memory(session_id, memory_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Niet gevonden")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database niet beschikbaar: {e}")


@router.delete("", summary="Clear All")
def clear_all(
    session_id: constr(min_length=8, max_length=128) = Query(...),
):
    try:
        n = db.clear_memories(session_id)
        return {"ok": True, "deleted": n}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database niet beschikbaar: {e}")


@router.post("/cleanup", summary="Verwijder lege memory-items")
def cleanup_empty(
    session_id: constr(min_length=8, max_length=128) = Query(...),
    delete: bool = Query(False, description="Voer daadwerkelijk delete uit (anders alleen tellen)"),
):
    """
    Verwijdert items die geen (afleidbare) tekst hebben:
    - data is {} of None
    - én er is geen data.text/value/note
    Standaard: dry-run (alleen tellen). Zet ?delete=true om echt te verwijderen.
    """
    try:
        items = db.fetch_memories(session_id, limit=10000, before_id=None)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database niet beschikbaar: {e}")

    to_delete = [m["id"] for m in items if not _has_text(m.get("data") or {})]

    if delete:
        n = 0
        for mid in to_delete:
            if db.delete_memory(session_id, mid):
                n += 1
        return {"ok": True, "deleted": n, "checked": len(items)}
    else:
        return {"ok": True, "would_delete": len(to_delete), "checked": len(items)}
