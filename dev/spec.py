"""
Dev Buddy – spec.py
Doel: een simpele, strakke representatie van een feature-/taakomschrijving.

Skeleton-functies:
- make_spec(title, goals) -> dict
- add_assumption(spec, note) -> dict
- add_constraint(spec, rule) -> dict
"""

from typing import List, Dict, Any

def make_spec(title: str, goals: List[str]) -> Dict[str, Any]:
    """
    Maak een basis-spec met titel en doelen.
    - title: korte naam van de feature/taak
    - goals: lijst met concrete doelen (1 zin per goal)
    """
    return {
        "title": title.strip(),
        "goals": [g.strip() for g in goals if str(g).strip()],
        "assumptions": [],
        "constraints": [],
    }

def add_assumption(spec: Dict[str, Any], note: str) -> Dict[str, Any]:
    """
    Voeg een aanname toe (bijv. 'User bestaat al').
    Returnt hetzelfde spec-dict (handig voor chaining).
    """
    spec.setdefault("assumptions", [])
    note = note.strip()
    if note:
        spec["assumptions"].append(note)
    return spec

def add_constraint(spec: Dict[str, Any], rule: str) -> Dict[str, Any]:
    """
    Voeg een constraint toe (bijv. 'HTTPS-only', 'max 200ms latency').
    Returnt hetzelfde spec-dict (handig voor chaining).
    """
    spec.setdefault("constraints", [])
    rule = rule.strip()
    if rule:
        spec["constraints"].append(rule)
    return spec
