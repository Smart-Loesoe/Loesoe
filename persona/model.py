# loesoe/persona/model.py
from __future__ import annotations
from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field
from loesoe.memory.long_term import fetch as lt_fetch, upsert as lt_upsert

Tone = Literal["casual", "zakelijk"]
Verbosity = Literal["kort", "normaal", "lang"]
Language = Literal["nl", "en"]
Safety = Literal["voorzichtig", "normaal", "ruim"]
DevStyle = Literal["compact", "uitleg"]
Mode = Literal["default", "jip-en-janneke"]

class Persona(BaseModel):
    tone: Tone = Field(default="casual", description="Spreektoon")
    verbosity: Verbosity = Field(default="normaal", description="Lengte van antwoorden")
    language: Language = Field(default="nl", description="Voorkeurstaal")
    voice_hint: Optional[str] = Field(default=None, description="TTS-stemlabel (toekomst)")
    safety_level: Safety = Field(default="normaal", description="Voorzichtigheid")
    dev_style: DevStyle = Field(default="compact", description="Code-stijl: compact of met uitleg")
    mode: Mode = Field(default="default", description="Jip-en-Janneke modus aan/uit")

    def merge_patch(self, patch: Dict[str, Any]) -> "Persona":
        data = self.dict()
        for k, v in (patch or {}).items():
            if k in data and v is not None:
                data[k] = v
        return Persona(**data)

def default_persona() -> Persona:
    return Persona()

def get_presets() -> Dict[str, Persona]:
    return {
        "casual": Persona(tone="casual", verbosity="normaal", language="nl", dev_style="compact"),
        "zakelijk": Persona(tone="zakelijk", verbosity="kort", language="nl", dev_style="compact"),
        "dev": Persona(tone="casual", verbosity="kort", language="nl", dev_style="compact", safety_level="normaal"),
        "uitleg": Persona(tone="zakelijk", verbosity="lang", language="nl", dev_style="uitleg"),
        "jip-en-janneke": Persona(tone="casual", verbosity="kort", language="nl", dev_style="uitleg", mode="jip-en-janneke"),
    }

# --- Persist helpers (LT memory) ------------------------------------------------
_LT_KEY = "persona"

def load_persona() -> Persona:
    raw = lt_fetch(_LT_KEY)
    if isinstance(raw, dict):
        return Persona(**raw)
    return default_persona()

def save_persona(p: Persona) -> None:
    lt_upsert(_LT_KEY, p.dict())
