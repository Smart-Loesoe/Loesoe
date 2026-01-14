# Skeleton voor eenvoudige router (later: ML + voorkeuren)
from typing import Literal, Dict

Route = Literal["search", "memory", "dev", "default"]

def simple_route(intent: str | None = None, meta: Dict | None = None) -> Route:
    """
    Skeleton: hele simpele mapping zonder externe calls.
    - intent "search"  -> "search"
    - intent "recall"  -> "memory"
    - intent "dev"     -> "dev"
    - anders           -> "default"
    """
    i = (intent or "").lower()
    if i == "search":
        return "search"
    if i in ("recall", "memory"):
        return "memory"
    if i == "dev":
        return "dev"
    return "default"
