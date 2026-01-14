# api/search.py

from __future__ import annotations

import os
from typing import List, Optional

import httpx
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

router = APIRouter(
    tags=["search"],
)

# 🔑 SerpAPI config (via .env.api)
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
SERPAPI_BASE_URL = os.getenv("SERPAPI_BASE_URL", "https://serpapi.com/search.json")


class SearchResult(BaseModel):
    title: Optional[str]
    link: Optional[str]
    snippet: Optional[str]
    source: Optional[str] = "google"


class SearchResponse(BaseModel):
    query: str
    limit: int
    engine: str
    results: List[SearchResult]


async def _serpapi_search(
    query: str,
    engine: str = "google",
    num_results: int = 5,
) -> List[SearchResult]:
    """
    Roept SerpAPI aan en geeft een genormaliseerde lijst resultaten terug.
    """

    if not SERPAPI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="SERPAPI_API_KEY is niet geconfigureerd op de server.",
        )

    params = {
        "api_key": SERPAPI_API_KEY,
        "engine": engine,
        "q": query,
        "num": num_results,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(SERPAPI_BASE_URL, params=params)

    if resp.status_code == 401:
        raise HTTPException(
            status_code=502,
            detail="SerpAPI: Unauthorized (check API key).",
        )

    if resp.status_code >= 500:
        raise HTTPException(
            status_code=502,
            detail=f"SerpAPI: server error ({resp.status_code}).",
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail=f"SerpAPI: onverwachte statuscode {resp.status_code}.",
        )

    data = resp.json()
    organic = data.get("organic_results") or []

    results: List[SearchResult] = []
    for item in organic:
        results.append(
            SearchResult(
                title=item.get("title"),
                link=item.get("link") or item.get("displayed_link"),
                snippet=item.get("snippet")
                or " ".join(item.get("snippet_highlighted_words") or []),
                source=item.get("source") or "google",
            )
        )

    return results


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Websearch via SerpAPI (Google)",
)
async def search(
    q: str = Query(..., description="De zoekopdracht"),
    limit: int = Query(
        5,
        ge=1,
        le=10,
        description="Aantal resultaten (1–10)",
    ),
):
    """
    Voert een webzoekopdracht uit via SerpAPI (Google-engine).

    Endpoint: GET /search?q=...&limit=...
    """

    results = await _serpapi_search(query=q, engine="google", num_results=limit)

    return SearchResponse(
        query=q,
        limit=limit,
        engine="google",
        results=results,
    )
