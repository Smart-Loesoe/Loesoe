"""
Dev Buddy – reviewer.py
Snelle heuristische checks (zonder LLM).
"""

from typing import List

def quick_review(text: str) -> List[str]:
    """
    Voert simpele checks uit:
    - bevat 'TODO'
    - tekst extreem lang
    - lege/whitespace input
    """
    issues: List[str] = []
    if not text or not str(text).strip():
        issues.append("Lege tekst")
        return issues

    low = text.lower()

    if "todo" in low:
        issues.append("Bevat TODO's")

    if len(text) > 10_000:
        issues.append("Tekst is erg lang (>10k chars)")

    return issues
