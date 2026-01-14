import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

log = logging.getLogger(__name__)

app = FastAPI(title="Loesoe API", version="16.0")

# --- CORS ---
origins_env = os.getenv("CORS_ALLOW_ORIGINS") or os.getenv("CORS_ORIGINS", "")
origins = [o.strip() for o in origins_env.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Health & root ---
@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/")
def root():
    return {"ok": True, "service": "loesoe-api"}

# --- Required routers ---
try:
    from loesoe.api import uploads
    app.include_router(uploads.router)
    log.info("Uploads router mounted")
except Exception as e:
    log.exception("Uploads router not mounted: %s", e)

# --- NEW in Fase 16: stream router ---
try:
    from loesoe.api import stream
    app.include_router(stream.router, prefix="/stream")  # -> /stream/sse and /stream/ws
    log.info("Stream router mounted at /stream")
except Exception as e:
    log.exception("Stream router not mounted: %s", e)

# --- Optional routers ---
def _try_mount(modname: str, prefix: str):
    try:
        module = __import__(f"loesoe.api.{modname}", fromlist=["router"])
        router = getattr(module, "router", None)
        if router is not None:
            app.include_router(router, prefix=prefix)
            log.info("Mounted router '%s' at '%s'", modname, prefix)
    except Exception as e:
        log.info("Optional router '%s' not mounted: %s", modname, e)

for name, pfx in (("chat", "/chat"), ("memory", "/memory"), ("prefs", "/prefs")):
    _try_mount(name, pfx)
