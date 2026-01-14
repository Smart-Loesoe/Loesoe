import os
import time
from typing import List, Dict, Any

import httpx

# --- Kleine in-memory TTL cache ---
_TTL_SECONDS = int(os.getenv("SEARCH_CACHE_TTL", "60"))
_CACHE: dict[tuple, tuple[float, List[Dict[str, Any]]]] = {}
_HITS = 0
_MISSES = 0


def cache_info() -> Dict[str, Any]:
    """Kleine statistiek om te zien of caching werkt."""
    return {
        "size": len(_CACHE),
        "ttl_seconds": _TTL_SECONDS,
        "hits": _HITS,
        "misses": _MISSES,
    }


def _choose_provider() -> str:
    """Volgorde: SerpAPI -> Bing -> stub."""
    if os.getenv("SERPAPI_KEY"):
        return "serpapi"
    if os.getenv("BING_API_KEY"):
        return "bing"
    return "stub"


def selected_provider() -> str:
    """Exporteer welke provider gekozen is (serpapi/bing/stub)."""
    return _choose_provider()


def _from_cache(key: tuple) -> List[Dict[str, Any]] | None:
    now = time.time()
    item = _CACHE.get(key)
    if not item:
        return None
    ts, payload = item
    if now - ts <= _TTL_SECONDS:
        return payload
    _CACHE.pop(key, None)  # verlopen
    return None


def _store_cache(key: tuple, payload: List[Dict[str, Any]]) -> None:
    _CACHE[key] = (time.time(), payload)


def search_web(query: str, limit: int = 5, use_cache: bool = True) -> List[Dict[str, Any]]:
    """Normale zoekfunctie met cache. Geeft lijst met {title,url,snippet}."""
    global _HITS, _MISSES
    provider = _choose_provider()
    key = (provider, query, int(limit))

    if use_cache:
        cached = _from_cache(key)
        if cached is not None:
            _HITS += 1
            return cached

    try:
        if provider == "serpapi":
            keyval = os.getenv("SERPAPI_KEY")
            url = "https://serpapi.com/search.json"
            params = {"q": query, "engine": "google", "api_key": keyval, "num": max(1, limit)}
            with httpx.Client(timeout=10) as client:
                r = client.get(url, params=params)
                r.raise_for_status()
                data = r.json()
            results = [{
                "title": item.get("title"),
                "url": item.get("link"),
                "snippet": item.get("snippet"),
            } for item in (data.get("organic_results") or [])[:limit]]
            _MISSES += 1
            _store_cache(key, results)
            return results

        if provider == "bing":
            keyval = os.getenv("BING_API_KEY")
            url = "https://api.bing.microsoft.com/v7.0/search"
            headers = {"Ocp-Apim-Subscription-Key": keyval}
            params = {"q": query, "count": max(1, limit)}
            with httpx.Client(timeout=10) as client:
                r = client.get(url, headers=headers, params=params)
                r.raise_for_status()
                data = r.json()
            web_pages = (data.get("webPages") or {}).get("value") or []
            results = [{
                "title": item.get("name"),
                "url": item.get("url"),
                "snippet": item.get("snippet"),
            } for item in web_pages[:limit]]
            _MISSES += 1
            _store_cache(key, results)
            return results

    except httpx.HTTPStatusError as e:
        # API key ongeldig of rate-limit
        return [{"title": f"Error {e.response.status_code}", "url": "#", "snippet": str(e)}]
    except Exception as e:
        # Andere fouten
        return [{"title": "Error", "url": "#", "snippet": str(e)}]

    # Fallback stub (ook gecachet)
    results = [{"title": f"STUB: {query}", "url": "#", "snippet": "Nog niet geïmplementeerd."}]
    _MISSES += 1
    _store_cache(key, results)
    return results


def search_web_with_meta(query: str, limit: int = 5) -> Dict[str, Any]:
    """
    Zelfde als search_web, maar met extra metadata:
    { results, provider, cached, took_ms, error? }
    """
    global _HITS
    provider = selected_provider()
    key = (provider, query, int(limit))

    t0 = time.time()
    cached_now = _from_cache(key)
    if cached_now is not None:
        _HITS += 1
        took_ms = int((time.time() - t0) * 1000)
        return {
            "results": cached_now,
            "provider": provider,
            "cached": True,
            "took_ms": took_ms,
        }

    try:
        results = search_web(query, limit=limit, use_cache=True)
        took_ms = int((time.time() - t0) * 1000)
        return {
            "results": results,
            "provider": provider,
            "cached": False,
            "took_ms": took_ms,
        }
    except Exception as e:
        took_ms = int((time.time() - t0) * 1000)
        return {
            "results": [],
            "provider": provider,
            "cached": False,
            "took_ms": took_ms,
            "error": str(e),
        }
