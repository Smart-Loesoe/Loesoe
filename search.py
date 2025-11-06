# loesoe/api/search.py
from __future__ import annotations
from fastapi import APIRouter, Query

router = APIRouter(tags=["search"])

@router.get("/search")
def search(q: str = Query(...), limit: int = Query(5, ge=1, le=50)):
    items = [{"title": f"{q} result {i+1}", "snippet": ""} for i in range(limit)]
    return {"query": q, "limit": limit, "results": items}
