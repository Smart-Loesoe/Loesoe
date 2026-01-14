import asyncio
import json
from typing import AsyncGenerator
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

router = APIRouter()

def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

@router.get("/sse")
async def stream_sse(request: Request, session_id: str, q: str):
    async def gen() -> AsyncGenerator[str, None]:
        try:
            # Stuur meteen iets zodat clients geen 'empty reply' zien
            yield _sse("open", {"session_id": session_id})

            # Demo: token-per-woord
            text = f"Loesoe antwoord op: {q}. (demo stream) "
            for word in text.split():
                if await request.is_disconnected():
                    # client sloot zelf: breek stilletjes
                    return
                yield _sse("token", {"text": word + " "})
                await asyncio.sleep(0.08)

            yield _sse("done", {"finish_reason": "stop"})
        except asyncio.CancelledError:
            # verbinding onderbroken
            return
        except Exception as e:
            # stuur error als event, dan clean close
            yield _sse("error", {"message": str(e)})
    # expliciete headers helpen bij sommige proxies/clients
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        # "X-Accel-Buffering": "no",  # alleen relevant achter Nginx
    }
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)

@router.websocket("/ws")
async def stream_ws(ws: WebSocket):
    await ws.accept()
    try:
        raw = await ws.receive_text()
        try:
            req = json.loads(raw)
        except Exception:
            req = {"q": raw}
        q = (req.get("q") or "").strip()
        text = f"WS stream voor: {q} "
        for word in text.split():
            await ws.send_text(json.dumps({"type": "token", "text": word + " "}))
            await asyncio.sleep(0.06)
        await ws.send_text(json.dumps({"type": "done"}))
    except WebSocketDisconnect:
        pass
    finally:
        await ws.close()
