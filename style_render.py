from __future__ import annotations
from .policy import StyleProfile

def render_text(content: str, style: StyleProfile) -> str:
    text = content.strip()
    if style.verbosity == "kort":
        import re
        parts = re.split(r'(?<=[.!?])\s+', text)
        text = " ".join(parts[:2])
    if style.tone == "straat":
        if not text.endswith(" 😎"):
            text += " 😎"
    elif style.tone == "jip":
        text += " (simpel uitgelegd)"
    if not style.emojis:
        import re
        text = re.sub(r'[\U0001F300-\U0001FAFF\U0001F1E6-\U0001F1FF]', '', text)
    return text
