"""
modules.zelflerend.scoring
--------------------------

Eenvoudige maar slimme scoring-engine voor Loesoe.

Doel:
- Elke user message (en eventueel history) omzetten naar een set scores
  die gebruikt kunnen worden door:
  - zelflerend geheugen
  - slimheidsmeter
  - behavior-analyse
  - dag-/gewoonteherkenning

Belangrijk:
- Geen externe libraries nodig (alleen standaard Python)
- Werkt met Nederlandse tekst + jouw typische slang ("joo maat", "gvd", "fk", etc.)
- Alle scores zijn JSON-vriendelijk (floats, ints, strings, lists, dicts)

Hoofdentry:
    score_message(message: str, history: list[str] | None = None) -> dict
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
import math
import re
from datetime import datetime


SCORE_VERSION = 1


# --------- Dataclasses voor structuur --------- #


@dataclass
class EmotionScore:
    label: str          # "positief", "neutraal", "negatief", "gestrest", "boos", ...
    confidence: float   # 0.0–1.0
    energy: float       # 0.0–1.0 (hoe veel "vibe" / intensiteit)
    stress: float       # 0.0–1.0


@dataclass
class IntentScore:
    label: str          # "smalltalk", "planning", "crypto", "werk", "emotioneel", "ontwikkeling", ...
    confidence: float   # 0.0–1.0
    tags: List[str]     # bv ["crypto", "tars", "risk"]


@dataclass
class BehaviorScore:
    importance: float       # 0.0–1.0 (hoe belangrijk voor geheugen / leven)
    novelty: float          # 0.0–1.0 (hoe nieuw t.o.v. history)
    habit_strength: float   # 0.0–1.0 (lijkt dit op vaste gewoonte?)
    risk: float             # 0.0–1.0 (financieel / emotioneel risico)


@dataclass
class RawStats:
    length: int
    word_count: int
    exclamations: int
    question_marks: int
    uppercase_ratio: float
    contains_crypto: bool
    contains_money: bool
    contains_time: bool
    timestamp: str


# --------- Hulpfuncties --------- #


def _safe_div(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return a / b


def _normalize(value: float, min_v: float, max_v: float) -> float:
    """Normeer een waarde tussen 0 en 1."""
    if max_v == min_v:
        return 0.0
    v = (value - min_v) / (max_v - min_v)
    return max(0.0, min(1.0, v))


def _to_words(text: str) -> List[str]:
    return re.findall(r"\w+", text.lower(), flags=re.UNICODE)


# --------- Emotion detection --------- #


_POSITIVE_WORDS = {
    "top", "lekker", "nice", "gaaf", "goed", "chill", "relaxed",
    "blij", "fijn", "yes", "yess", "yay", "super", "trots",
}

_NEGATIVE_WORDS = {
    "kut", "klote", "k*t", "slecht", "rot", "balen",
    "pfff", "pffff", "wtf", "boos", "haat",
}

_STRESS_WORDS = {
    "stress", "zenuw", "zenuwachtig", "paniek", "bang",
    "nerveus", "onzeker", "overprikkeld", "prikkels",
}

_ANGER_WORDS = {
    "gvd", "godver", "fk", "fuck", "woest", "klootzak", "idioot",
}

_HIGH_ENERGY_MARKERS = {
    "joo", "maat", "haha", "hahaha", "omg", "wtf", "🔥", "🤘",
}


def _detect_emotion(message: str) -> EmotionScore:
    text = message.strip()
    words = _to_words(text)

    pos_hits = sum(w in _POSITIVE_WORDS for w in words)
    neg_hits = sum(w in _NEGATIVE_WORDS for w in words)
    stress_hits = sum(w in _STRESS_WORDS for w in words)
    anger_hits = sum(w in _ANGER_WORDS for w in words)
    energy_hits = sum(w in _HIGH_ENERGY_MARKERS for w in words)

    exclamations = text.count("!")
    question_marks = text.count("?")

    # basis score voor energie op basis van uitroeptekens, caps en markers
    upper_chars = sum(1 for c in text if c.isupper())
    total_chars = len(text) or 1
    uppercase_ratio = upper_chars / total_chars

    base_energy = _normalize(exclamations + energy_hits * 1.5 + uppercase_ratio * 10, 0, 10)

    # stress op basis van stress + anger + vraagtekens
    base_stress = _normalize(stress_hits * 1.5 + anger_hits * 2 + question_marks, 0, 8)

    # sentiment richting
    sentiment_raw = pos_hits - (neg_hits + anger_hits)
    sentiment_norm = _normalize(sentiment_raw, -5, 5)  # 0–1, 0.5 is neutraal

    if sentiment_raw > 1:
        label = "positief"
    elif sentiment_raw < -1:
        # kijken of meer boos of verdrietig/stress
        if anger_hits > stress_hits:
            label = "boos"
        else:
            label = "negatief"
    else:
        if base_stress > 0.6:
            label = "gestrest"
        else:
            label = "neutraal"

    # confidence: hoe meer signalen, hoe zekerder
    signal_strength = pos_hits + neg_hits + stress_hits + anger_hits + exclamations + question_marks
    confidence = _normalize(signal_strength, 0, 12)

    return EmotionScore(
        label=label,
        confidence=round(confidence, 3),
        energy=round(base_energy, 3),
        stress=round(base_stress, 3),
    )


# --------- Intent detection --------- #


_INTENT_KEYWORDS = {
    "crypto": ["btc", "bitcoin", "altseason", "alt season", "altcoins",
               "wif", "tars", "fart", "kaspa", "kasp", "etc", "eth",
               "bybit", "bitvavo", "binance", "entry", "target", "stoploss", "stop loss"],
    "planning": ["planning", "afspraak", "agenda", "morgen", "vandaag",
                 "vanavond", "weekend", "deadline", "uren", "werken", "sollicitatie"],
    "werk": ["gemeente", "baan", "cv", "sollicitatie", "vacature", "uren",
             "contract", "werk", "functie", "teamleider"],
    "ontwikkeling": ["leren", "studie", "opleiding", "cursus", "boeken",
                     "pdf", "samenvatten", "developer", "programmeren", "python", "code"],
    "emotioneel": ["bang", "stress", "zorgen", "gevoel", "emotie", "twijfel",
                   "doodop", "overprikkeld", "overprikkeling", "onzeker"],
    "buddy": ["lizz", "jax", "buddy", "kinder", "tiener", "school",
              "sinterklaas", "cadeau", "speelgoed"],
}


def _detect_intent(message: str) -> IntentScore:
    text = message.lower()
    words = _to_words(text)

    scores: Dict[str, int] = {k: 0 for k in _INTENT_KEYWORDS.keys()}
    hits_tags: List[str] = []

    for intent, keywords in _INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[intent] += 1
                hits_tags.append(kw)

    # smalltalk detectie (joo maat, hoe is het, etc.)
    smalltalk_score = 0
    if any(phrase in text for phrase in ["joo maat", "jo maat", "joo", "maat"]):
        smalltalk_score += 2
        hits_tags.append("smalltalk")
    if any(phrase in text for phrase in ["hoe is het", "hoe gaat het"]):
        smalltalk_score += 2
        hits_tags.append("check-in")

    # kies intent met hoogste score
    top_intent = "smalltalk"
    top_score = smalltalk_score

    for intent, score in scores.items():
        if score > top_score:
            top_intent = intent
            top_score = score

    # emotioneel override: als emotioneel woorden overheersen
    emo_weight = scores.get("emotioneel", 0)
    if emo_weight >= 2 and emo_weight >= top_score:
        top_intent = "emotioneel"
        top_score = emo_weight

    # confidence
    confidence = _normalize(top_score, 0, 5)

    return IntentScore(
        label=top_intent,
        confidence=round(confidence, 3),
        tags=sorted(set(hits_tags)),
    )


# --------- Raw stats + behavior scores --------- #


_MONEY_WORDS = [
    "euro", "€", "salaris", "loon", "verdien", "verdient",
    "budget", "schuld", "betal", "rekening", "prive", "privé",
]

_TIME_WORDS = [
    "vandaag", "morgen", "vanavond", "straks", "volgende week",
    "overmorgen", "dit weekend", "die dag", "datum", "tijdstip",
]


def _extract_raw_stats(message: str) -> RawStats:
    text = message or ""
    words = _to_words(text)
    length = len(text)
    word_count = len(words)

    exclamations = text.count("!")
    question_marks = text.count("?")

    upper_chars = sum(1 for c in text if c.isupper())
    total_chars = length or 1
    uppercase_ratio = upper_chars / total_chars

    lw = text.lower()
    contains_crypto = any(kw in lw for kw in _INTENT_KEYWORDS["crypto"])
    contains_money = any(kw in lw for kw in _MONEY_WORDS)
    contains_time = any(kw in lw for kw in _TIME_WORDS)

    return RawStats(
        length=length,
        word_count=word_count,
        exclamations=exclamations,
        question_marks=question_marks,
        uppercase_ratio=round(uppercase_ratio, 3),
        contains_crypto=contains_crypto,
        contains_money=contains_money,
        contains_time=contains_time,
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


def _detect_habit_strength(message: str, history: Optional[List[str]]) -> float:
    """
    Schat hoe "gewoonte-achtig" dit bericht is.

    - Als de zin (of stukken ervan) vaak in history voorkwam → hogere score.
    - Als het veel lijkt op 'joo maat', 'heb je een crypto update', etc.
    """
    if not history:
        return 0.1  # geen context → licht laag

    text = message.lower().strip()
    history_lw = [h.lower().strip() for h in history if h]

    if not text:
        return 0.0

    # simpele variant: hoeveel history items bevatten een groot deel van deze tekst?
    same_start = 0
    for h in history_lw:
        if not h:
            continue
        if text.startswith("joo maat") and h.startswith("joo maat"):
            same_start += 1
        elif text in h or h in text:
            same_start += 1

    ratio = _safe_div(same_start, len(history_lw))
    return round(_normalize(ratio, 0.0, 0.6), 3)  # 0.0–1.0


def _estimate_importance(
    message: str,
    intent: IntentScore,
    emotion: EmotionScore,
    raw: RawStats,
) -> float:
    """
    Hoe belangrijk is dit bericht voor geheugen / leven?
    - Geld, werk, afspraken → belangrijker
    - Hoge stress of sterke emotie → belangrijk
    - Veel concrete info → belangrijk
    """
    text = message.lower()

    base = 0.2

    # intent gewicht
    if intent.label in ("werk", "planning", "ontwikkeling", "crypto"):
        base += 0.2
    if intent.label == "emotioneel":
        base += 0.15

    # geld / werkwoorden
    if raw.contains_money:
        base += 0.15
    if any(w in text for w in ["contract", "sollicitatie", "baan", "gemeente"]):
        base += 0.15

    # afspraken / tijd
    if raw.contains_time:
        base += 0.1

    # emotie/stress
    base += emotion.stress * 0.15
    if emotion.label in ("boos", "gestrest", "negatief"):
        base += 0.1

    # lengte / info
    if raw.word_count > 40:
        base += 0.05
    if raw.word_count > 80:
        base += 0.05

    return max(0.0, min(1.0, round(base, 3)))


def _estimate_novelty(message: str, history: Optional[List[str]]) -> float:
    """
    Schat hoe 'nieuw' deze info is t.o.v. history.
    - Als history leeg is → alles is nieuw.
    - Als echt bijna hetzelfde al vaak voorkomt → lager.
    """
    if not history:
        return 1.0

    text = message.lower().strip()
    if not text:
        return 0.0

    history_lw = [h.lower().strip() for h in history if h]
    total = len(history_lw)
    if total == 0:
        return 1.0

    similar = 0
    for h in history_lw:
        if not h:
            continue
        # simpele overlap: gedeelde woorden
        w1 = set(_to_words(text))
        w2 = set(_to_words(h))
        if not w1 or not w2:
            continue
        overlap = len(w1 & w2) / len(w1 | w2)
        if overlap > 0.7:
            similar += 1

    ratio = _safe_div(similar, total)
    novelty = 1.0 - ratio
    return round(max(0.0, min(1.0, novelty)), 3)


def _estimate_risk(
    message: str,
    intent: IntentScore,
    emotion: EmotionScore,
    raw: RawStats,
) -> float:
    """
    Schat een globale 'risico' score:
    - hoge bedragen / all-in / leverage / gokken → hoger
    - veel stress en crypto tegelijk → hoger
    - pure smalltalk → laag
    """
    text = message.lower()
    base = 0.0

    # crypto + emoties
    if raw.contains_crypto:
        base += 0.2
        base += emotion.stress * 0.2

    # woorden die wijzen op risico
    risk_words = [
        "all-in", "all in", "alles inzetten", "alles erin", "max leverage",
        "x50", "x100", "gokken", "casino", "mogelijk verlies",
    ]
    if any(w in text for w in risk_words):
        base += 0.3

    # hoge bedragen / grote sprongen
    if any(sym in text for sym in ["€", "euro"]):
        # heel ruwe check op getallen
        numbers = re.findall(r"\d+", text)
        if numbers:
            max_num = max(int(n) for n in numbers)
            if max_num >= 500:
                base += 0.2
            elif max_num >= 200:
                base += 0.1

    # emotioneel + geld
    if raw.contains_money and emotion.stress > 0.5:
        base += 0.2

    # smalltalk → laag risico
    if intent.label == "smalltalk":
        base *= 0.3

    return max(0.0, min(1.0, round(base, 3)))


# --------- Publieke entrypoint --------- #


def score_message(message: str, history: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Hoofdfunctie: geef een message (en optioneel history) en ontvang
    een volledig scoring-profiel terug.

    Voorbeeld output:
    {
        "version": 1,
        "emotion": {...},
        "intent": {...},
        "behavior": {...},
        "raw": {...}
    }
    """
    history = history or []

    raw = _extract_raw_stats(message)
    emotion = _detect_emotion(message)
    intent = _detect_intent(message)

    habit_strength = _detect_habit_strength(message, history)
    importance = _estimate_importance(message, intent, emotion, raw)
    novelty = _estimate_novelty(message, history)
    risk = _estimate_risk(message, intent, emotion, raw)

    behavior = BehaviorScore(
        importance=importance,
        novelty=novelty,
        habit_strength=habit_strength,
        risk=risk,
    )

    return {
        "version": SCORE_VERSION,
        "emotion": asdict(emotion),
        "intent": asdict(intent),
        "behavior": asdict(behavior),
        "raw": asdict(raw),
    }


# --------- Kleine zelftest --------- #

if __name__ == "__main__":
    tests = [
        "joo maat heb je een crypto update?",
        "Ik ben best gestrest over geld en die sollicitatie bij de gemeente.",
        "Morgen om 10:30 hebben we Loesoe-time, daarna kids ophalen.",
        "Ff chill, gewoon even ouwehoeren.",
        "Ga ik all-in op BTC of niet? 1500 euro erin knallen?",
    ]

    history = [
        "joo maat",
        "Heb je een crypto update?",
        "Heb je een crypto update?",
        "Kan je een crypto analyse doen?",
    ]

    for t in tests:
        print("=" * 80)
        print("TEXT:", t)
        result = score_message(t, history=history)
        print(result)
