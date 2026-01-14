# api/streaming.py

import asyncio
import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse

try:
    # Nieuwe OpenAI client (v1+)
    from openai import AsyncOpenAI

    _openai_client: AsyncOpenAI | None = AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY")
    )
except Exception:
    _openai_client = None

router = APIRouter(prefix="/stream", tags=["stream"])


# -----------------------------------------------------
# 1) Dashboard pings: /stream/events
# -----------------------------------------------------
async def _event_generator(request: Request):
    """
    Eenvoudige SSE-stream voor het dashboard.
    Stuurt elke 5 seconden een 'ping' met een timestamp.
    """
    while True:
        # Stoppen als de client weg is
        if await request.is_disconnected():
            break

        now = datetime.now(timezone.utc).isoformat()

        payload = {
            "type": "ping",
            "ts": now,
        }

        chunk = f"data: {json.dumps(payload)}\n\n"
        yield chunk.encode("utf-8")

        await asyncio.sleep(5)


@router.get("/events")
async def stream_events(request: Request):
    """
    Endpoint voor dashboard-SSE (StreamingStatus + auto-refresh).
    """
    return StreamingResponse(
        _event_generator(request),
        media_type="text/event-stream",
    )


# -----------------------------------------------------
# 2) Chat streaming via GPT-5.1: /stream/chat
# -----------------------------------------------------
async def _chat_stream(request: Request, q: str):
    """
    Streaming chat:

    - Probeert via OpenAI GPT-5.1 te streamen
    - Stuurt 'chat_chunk' events met tekst naar de frontend
    - Eindigt met een 'chat_done' event

    Frontend bouwt hiermee de Loesoe-bubble op.
    """

    # 1) Fallback als er geen client of key is
    if _openai_client is None or not os.getenv("OPENAI_API_KEY"):
        fallback_text = (
            "Let op: er is geen geldige OPENAI_API_KEY ingesteld. "
            "Loesoe kan nu geen echte GPT-stream gebruiken. "
            f"(Ontvangen vraag: {q})"
        )

        # Simpele woord-voor-woord fallback zodat de UI wél werkt
        words = fallback_text.split(" ")
        for i, word in enumerate(words):
            if await request.is_disconnected():
                break
            chunk_text = ("" if i == 0 else " ") + word
            payload = {"type": "chat_chunk", "content": chunk_text}
            chunk = f"data: {json.dumps(payload)}\n\n"
            yield chunk.encode("utf-8")
            await asyncio.sleep(0.15)

        if not await request.is_disconnected():
            done_payload = {"type": "chat_done"}
            done_chunk = f"data: {json.dumps(done_payload)}\n\n"
            yield done_chunk.encode("utf-8")
        return

    model_name = os.getenv("MODEL_DEFAULT", "gpt-5.1")

    try:
        # 2) Echte GPT streaming call
        stream = await _openai_client.chat.completions.create(
            model=model_name,
            stream=True,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Je bent Loesoe, een persoonlijke assistent die kort, duidelijk "
                        "en vriendelijk reageert. Je antwoord wordt live gestreamd naar "
                        "een web-dashboard van Richard. Geef geen extreem lange monologen, "
                        "maar reageer in natuurlijke zinnen."
                    ),
                },
                {
                    "role": "user",
                    "content": q,
                },
            ],
        )

        # 3) Stream de delta-content naar de frontend
        async for chunk in stream:
            if await request.is_disconnected():
                break

            choice = chunk.choices[0]
            delta = getattr(choice, "delta", None)
            if not delta:
                continue

            content_piece = getattr(delta, "content", None)
            if not content_piece:
                continue

            payload = {"type": "chat_chunk", "content": content_piece}
            data_str = json.dumps(payload)
            yield f"data: {data_str}\n\n".encode("utf-8")

        # 4) Einde van de stream
        if not await request.is_disconnected():
            done_payload = {"type": "chat_done"}
            yield f"data: {json.dumps(done_payload)}\n\n".encode("utf-8")

    except Exception as e:
        # Bij fout: stuur een foutmelding terug als één gestreamde tekst
        err_text = (
            "Er ging iets mis bij het streamen van GPT-5.1. "
            f"Technische details: {type(e).__name__}: {e}"
        )
        words = err_text.split(" ")
        for i, word in enumerate(words):
            if await request.is_disconnected():
                break
            chunk_text = ("" if i == 0 else " ") + word
            payload = {"type": "chat_chunk", "content": chunk_text}
            yield f"data: {json.dumps(payload)}\n\n".encode("utf-8")
            await asyncio.sleep(0.1)

        if not await request.is_disconnected():
            done_payload = {"type": "chat_done"}
            yield f"data: {json.dumps(done_payload)}\n\n".encode("utf-8")


@router.get("/chat")
async def stream_chat(
    request: Request,
    q: str = Query(..., description="Gebruikersbericht dat gestreamd moet worden"),
):
    """
    Streaming chat endpoint.

    Frontend (Dashboard / ChatWithLearning) opent een EventSource naar:
        /stream/chat?q=...

    De UI plakt alle 'chat_chunk' content achter elkaar in de Loesoe-bubble.
    """
    return StreamingResponse(
        _chat_stream(request, q),
        media_type="text/event-stream",
    )
