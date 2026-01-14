# Skeleton voor het combineren van resultaten (dedupe minimal)
from typing import List, Dict, Any

def aggregate(results_lists: List[List[Dict[str, Any]]], dedupe: bool = True) -> List[Dict[str, Any]]:
    """
    Skeleton: combineer lijsten; minimale dedupe op 'url'.
    Details (scoren, sorteren, bronnenweging) komen later.
    """
    flat = [item for sub in results_lists for item in sub]
    if not dedupe:
        return flat

    seen = set()
    unique = []
    for r in flat:
        key = r.get("url")
        if key and key not in seen:
            seen.add(key)
            unique.append(r)
        elif key is None:
            unique.append(r)  # laat items zonder url door
    return unique
