import os
from typing import Optional, Dict, Any
from openai import OpenAI

# Pak model uit env; val anders terug op een zeker model
DEFAULT_MODEL = (os.getenv("MODEL_DEFAULT") or "gpt-4o-mini").strip()

_client: Optional[OpenAI] = None


def _build_client() -> OpenAI:
    """
    Bouwt een OpenAI client die werkt met zowel 'sk-' als 'sk-proj-' keys.
    Voor 'sk-proj-' is OPENAI_PROJECT verplicht.
    """
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY ontbreekt.")

    kwargs = {"api_key": api_key}

    if api_key.startswith("sk-proj-"):
        project = (os.getenv("OPENAI_PROJECT") or "").strip()
        if not project:
            raise RuntimeError(
                "Je gebruikt een project key ('sk-proj-…'), maar OPENAI_PROJECT ontbreekt. "
                "Zet OPENAI_PROJECT=proj_xxxxxxxxx in docker-compose.yml."
            )
        kwargs["project"] = project

    return OpenAI(**kwargs)


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = _build_client()
    return _client


def get_active_model() -> str:
    return DEFAULT_MODEL


def generate_response(prompt: str) -> Dict[str, Any]:
    """
    Stuurt prompt naar OpenAI en geeft ALTIJD een nette dict terug:
    {
      "response": "...",
      "status": "success" | "error",
      "tokens_used": int
    }
    """
    if not prompt:
        return {"response": "", "status": "success", "tokens_used": 0}

    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=400,
        )
        msg = resp.choices[0].message.content if (resp and resp.choices) else ""
        tokens = 0
        # usage kan ontbreken in sommige responses; defensief lezen
        try:
            tokens = int(getattr(resp, "usage", None).total_tokens)  # type: ignore
        except Exception:
            tokens = 0

        return {
            "response": (msg or "").strip(),
            "status": "success",
            "tokens_used": tokens,
        }

    except Exception as e:
        # Geen 500 meer omhoog gooien — altijd netjes teruggeven
        return {
            "response": f"Fout bij genereren: {e}",
            "status": "error",
            "tokens_used": 0,
        }
