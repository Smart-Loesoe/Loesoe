# loesoe/core/prompts.py
from __future__ import annotations
from typing import Dict, Any

TEMPLATES: Dict[str, str] = {
    "default": (
        "Je bent Loesoe. Antwoord behulpzaam en concreet.\n\n"
        "[Persona] Taal: {language}. Toon: {tone}. Gebruik {verbosity} lengte.\n"
        "Antwoord kort en to-the-point.\n"
        "Leg het uit in eenvoudige Jip-en-Janneke taal.\n"
        "Bij code: duidelijke uitleg met stappen.\n"
        "{question}"
    ),
    "dev": (
        "Je bent Loesoe in developer-modus. Wees technisch en compact.\n\n"
        "[Dev-style: {dev_style}] Antwoord in {language}, toon {tone}, lengte {verbosity}.\n"
        "{question}"
    ),
    "uitleg": (
        "Je bent Loesoe als uitleg-buddy. Leg dingen stap voor stap uit.\n\n"
        "[Persona] taal={language}, toon={tone}, lengte={verbosity}.\n"
        "{question}"
    ),
    "dev_review": (
        "Code review: geef korte, concrete feedback. Noem onveilige patronen en verbeterpunten.\n"
        "{snippet}"
    ),
}

_DEFAULTS: Dict[str, Any] = {
    "language": "Nederlands",
    "tone": "vriendelijk en nuchter (casual)",
    "verbosity": "normaal",
    "dev_style": "uitleg",
    "question": "",
    "snippet": "",
}

def list_templates() -> list[str]:
    return list(TEMPLATES.keys())

def get_prompt(name: str, **kwargs) -> str:
    tpl = TEMPLATES.get(name)
    if not tpl:
        raise ValueError(f"Onbekende prompt: {name}")
    data = {**_DEFAULTS, **kwargs}
    return tpl.format(**data)

def add_template(name: str, template: str) -> None:
    TEMPLATES[name] = template

def remove_template(name: str) -> None:
    if name in TEMPLATES:
        del TEMPLATES[name]
