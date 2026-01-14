# ML-laag (Fase 23.4) — Deterministisch & Opt-in

Deze map bevat de **ML-laag van Loesoe**, maar let op:

✅ **Deterministisch**  
✅ **Uitlegbaar / auditbaar**  
✅ **Opt-in**  
✅ **Geen impact zonder expliciete activatie**  

Loesoe blijft standaard **read-only observability** (Fase 23.3):  
events → patterns → transparant zichtbaar in dashboard.

---

## Doel van deze laag

Deze laag voegt een **deterministische “ML-engine”** toe bovenop bestaande learning patterns.

Voorbeelden (gecontroleerd, later):
- simpele scorings (trend / routine score)
- anomaly detection (afwijking t.o.v. baseline)
- suggesties (“wil je X doen?”) **zonder auto-acties**
- ML-score voor slimheidsmeter

---

## Hard rules (niet onderhandelbaar)

1) **Geen impliciete beslissingen**
- ML mag nooit “stiekem” gedrag veranderen.

2) **Geen automatische acties**
- ML produceert alleen **output** (score/flags/suggesties), geen side-effects.

3) **Altijd uitlegbaar**
- Elke output bevat:
  - input-sources (patterns / counters)
  - berekening / regels
  - confidence/score
  - timestamp

4) **Opt-in activatie**
- ML draait alleen als een expliciete feature-flag aan staat.
- Default: **OFF**

5) **Kill-switch verplicht**
- Als ML ooit actief wordt: kill-switch moet alles direct kunnen uitschakelen.

6) **Geen afhankelijkheid op hidden state**
- Geen globale variabelen
- Geen “cache die waarheid wordt”
- Alles herleidbaar uit DB / inputs

---

## Output contract (actueel)

Elke ML-module levert een object terug met (minimaal):

- `module`: string
- `version`: string
- `computed_at_utc`: ISO timestamp (UTC)
- `inputs`: lijst van gebruikte sources/patterns
- `kind`: score / flags / suggestion / summary
- `status`: ok / warn / error
- `score`: (optioneel) float
- `flags`: (optioneel) dict
- `payload`: (optioneel) dict
- `explain`: korte uitleg + (optioneel) debug details

Zie: `api/ml/interfaces.py`

---

## Grenzen

Wat deze laag NIET is:
- Geen “black box AI”
- Geen autonoom agent-systeem
- Geen model fine-tuning
- Geen probabilistische chaos

Loesoe blijft:
> **expliciet, voorspelbaar en debugbaar**

---

## Status (actueel)

✅ Fase 23.4.1 — Skeleton + contracts + registry (AFGEROND)
- `interfaces.py` (MLContext/MLResult/MLModule contract)
- `registry.py` (safe default registration, in-memory)

✅ Fase 23.4.2 — Deterministische score op patterns (AFGEROND)
- `modules/explain_preference_score.py`
  - read-only: gebruikt alleen `ctx.patterns`
  - value parsing: dict óf JSON-string (bijv. `"{"level":"high"}"`)
  - score = base(level) × confidence (0..1)
  - altijd explain + debug trace

✅ Fase 23.4.3 — 2e module + runner (AFGEROND)
- `modules/patterns_volume_anomaly.py`
  - flags op basis van totaal patterns + breakdown per type
- `run_once.py` (read-only runner)
  - init/close database netjes
  - haalt patterns uit DB
  - draait modules zonder endpoints
  - subject-filter is “safe” (filter alleen als er matches zijn)

🔒 Nog steeds GEEN impact op gedrag:
- geen router-calls
- geen DB writes
- geen netwerk calls
- alleen read-only output

➡️ Pas bij expliciete feature-flag + kill-switch wordt koppeling met gedrag/UX overwogen.
