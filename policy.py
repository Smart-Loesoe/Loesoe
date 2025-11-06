from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class StyleProfile:
    tone: str = "casual"         # casual | straat | jip | zakelijk
    verbosity: str = "normaal"   # kort | normaal | uitgebreid
    emojis: bool = True
    jargon: str = "normaal"      # laag | normaal | hoog
    structure: str = "verhaal"   # verhaal | bullets | rapport

def to_style(d: Dict[str, Any]) -> StyleProfile:
    s = StyleProfile()
    if not d: return s
    st = d.get("style", {})
    fmt = d.get("format", {})
    s.tone = st.get("tone", s.tone)
    s.verbosity = st.get("verbosity", s.verbosity)
    s.emojis = st.get("emojis", s.emojis)
    s.jargon = st.get("jargon_level", s.jargon)
    s.structure = "rapport" if s.tone == "zakelijk" else ("bullets" if fmt.get("bullets") else "verhaal")
    return s

def merge_style(base: StyleProfile, override: StyleProfile) -> StyleProfile:
    return StyleProfile(
        tone = override.tone or base.tone,
        verbosity = override.verbosity or base.verbosity,
        emojis = override.emojis if override.emojis is not None else base.emojis,
        jargon = override.jargon or base.jargon,
        structure = override.structure or base.structure
    )

def context_to_style(context: Dict[str, Any]) -> Optional[StyleProfile]:
    # ⚠️ Belangrijk: bij 'chat' GEEN override teruggeven
    intent = (context or {}).get("intent", "chat")
    if intent == "code":
        return StyleProfile(tone="zakelijk", verbosity="normaal", emojis=False, jargon="hoog", structure="rapport")
    if intent == "kids":
        return StyleProfile(tone="jip", verbosity="kort", emojis=True, jargon="laag", structure="verhaal")
    return None

def select_style(*, explicit: Optional[Dict[str, Any]] = None,
                 persona: Optional[Dict[str, Any]] = None,
                 prefs: Optional[Dict[str, Any]] = None,
                 context: Optional[Dict[str, Any]] = None,
                 domain: Optional[Dict[str, Any]] = None) -> StyleProfile:
    style = StyleProfile()  # default
    # cascade: persona -> prefs -> context(if not None) -> domain -> explicit
    for layer in (persona, prefs, context_to_style(context or {}), domain, explicit):
        if not layer: 
            continue
        sp = to_style(layer) if not isinstance(layer, StyleProfile) else layer
        style = merge_style(style, sp)
    return style
