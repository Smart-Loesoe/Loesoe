import os, sys
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

load_dotenv(override=True)

try:
    from openai import OpenAI, APIStatusError
except Exception as e:
    raise RuntimeError(f"OpenAI SDK ontbreekt of kan niet geladen worden: {e}")

APP_VERSION = "18.1-auth-stable"
app = FastAPI(title="Loesoe API", version=APP_VERSION)

# CORS
allow_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "")
allow_origins = [o for o in (allow_origins_env.split(",") if allow_origins_env else []) if o] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔐 Auth
from api.auth.routes import router as auth_router
from api.dependencies.user import get_current_user  # <-- gebruikt JWT access token
from api.auth.models import User                    # alleen voor type hints / .safe()
app.include_router(auth_router)

def _mask(v: Optional[str]) -> Optional[str]:
    if not v: return None
    return v[:4] + ("*" * max(0, len(v) - 8)) + v[-4:] if len(v) > 8 else "****"

def _active_model() -> str:
    return os.getenv("MODEL_DEFAULT", "gpt-5")

def _client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    project = os.getenv("OPENAI_PROJECT")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY ontbreekt")
    headers: Dict[str,str] = {}
    if project:
        headers["OpenAI-Project"] = project
    return OpenAI(api_key=api_key, default_headers=headers)

@app.get("/healthz")
def healthz():
    return {"ok": True, "version": APP_VERSION}

@app.get("/debug/env")
def debug_env():
    return {
        "OPENAI_API_KEY": _mask(os.getenv("OPENAI_API_KEY")),
        "OPENAI_PROJECT": os.getenv("OPENAI_PROJECT"),
        "MODEL_DEFAULT": os.getenv("MODEL_DEFAULT"),
        "UPLOADS_DIR": os.getenv("UPLOADS_DIR"),
        "SIGNER_DEFAULT_TTL": os.getenv("SIGNER_DEFAULT_TTL"),
        "TZ": os.getenv("TZ"),
        "CORS_ALLOW_ORIGINS": os.getenv("CORS_ALLOW_ORIGINS"),
        "python": sys.version.split()[0],
    }

@app.get("/model")
def get_model():
    return {"model": _active_model()}

# 🔐 Ingelogde gebruiker (vereist geldige Bearer access token)
@app.get("/me")
async def me(user: User = Depends(get_current_user)):
    # user.safe komt uit het User-model en verbergt gevoelige velden
    return {"user": user.safe}

@app.post("/chat")
def chat(payload: Dict[str, Any]):
    client = _client()
    model = payload.get("model") or _active_model()
    messages: List[Dict[str,str]] = payload.get("messages") or [{"role":"user","content":"Hallo!"}]
    try:
        res = client.chat.completions.create(model=model, messages=messages)
        txt = res.choices[0].message.content
        return {"model": model, "content": txt}
    except APIStatusError as e:
        raise HTTPException(status_code=e.status_code, detail={
            "error": str(e),
            "hint": "Controleer OPENAI_API_KEY en OpenAI-Project header (proj_...).",
            "project": os.getenv("OPENAI_PROJECT"),
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stream/sse")
def stream_sse():
    client = _client()
    model = _active_model()
    def gen():
        try:
            with client.chat.completions.stream(
                model=model,
                messages=[{"role": "user", "content": "Zeg 'Hallo!' in één korte zin."}],
            ) as stream:
                for event in stream:
                    delta = getattr(event, "delta", None)
                    content = getattr(delta, "content", None) if delta else None
                    if content:
                        yield f"data: {content}\n\n"
                yield "data: [DONE]\n\n"
        except APIStatusError as e:
            yield f"data: [ERROR] {e}\n\n"
        except Exception as e:
            yield f"data: [ERROR] {e}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
