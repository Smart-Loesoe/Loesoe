# api/serpapi_client.py

import os
from typing import List, Dict, Any, Optional

import httpx
from fastapi import HTTPException


SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
SERPAPI_BASE_URL = os.getenv("SERPAPI_BASE_URL", "https://serpapi.com/search.json")


if not SERPAPI_API_KEY:
    # We gooien nog geen exception bij import,
    # maar checken wel bij het eerste gebruik.
    pass


async def serpapi_search(
    query: str,
    engine: str = "google",
    num_results: int = 5,
) -> List[Dict[str, Any]]:
    """
    Basis SerpAPI-call.
    Normaliseert resultaten naar een simpele lijst met:
    - title
    - link
    - snippet
    - source
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

    # Voor 'google' engine zitten resultaten in 'organic_results'
    organic = data.get("organic_results") or []

    normalized: List[Dict[str, Any]] = []
    for item in organic:
        normalized.append(
            {
                "title": item.get("title"),
                "link": item.get("link") or item.get("displayed_link"),
                "snippet": item.get("snippet") or item.get("snippet_highlighted_words"),
                "source": item.get("source") or "google",
            }
        )

    return normalized
