# api/main.py
import logging
import os
from pathlib import Path
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

APP_VERSION = os.getenv("APP_VERSION", "v6.9")
SAFE_MODE = os.getenv("SAFE_MODE", "false").lower() in ("1", "true", "yes", "y", "on")
LOG_ASCII_ONLY = os.getenv("LOG_ASCII_ONLY", "1") == "1"

# ============================================================
# LOGGING (bind mount naar /data/logs/loesoe.log)
# ============================================================
LOG_DIR = Path(os.getenv("LOG_DIR", "/data/logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "loesoe.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
)
logger = logging.getLogger("loesoe")


def ok(msg: str) -> str:
    return f"[OK] {msg}" if LOG_ASCII_ONLY else f"✅ {msg}"


def fail(msg: str) -> str:
    return f"[FAIL] {msg}" if LOG_ASCII_ONLY else f"❌ {msg}"


# ============================================================
# APP
# ============================================================
app = FastAPI(title="Loesoe API", version=APP_VERSION)

# ============================================================
# CORS
# ============================================================
cors_origins_env = os.getenv("CORS_ORIGINS", "http://localhost:5173")
CORS_ORIGINS: List[str] = [o.strip() for o in cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# STARTUP / SHUTDOWN
# ============================================================
@app.on_event("startup")
async def startup():
    logger.info(ok("startup gestart"))
    logger.info(ok(f"Loesoe {APP_VERSION} (SAFE_MODE={SAFE_MODE})"))
    logger.info(ok(f"LOG_FILE={LOG_FILE}"))

    # ✅ 1 waarheid: init_database bouwt pool
    try:
        from api.db.database import init_database, get_pool

        await init_database()

        pool = get_pool()
        if pool is None:
            raise RuntimeError("get_pool() returned None")
        logger.info(ok("db pool ready"))
    except Exception as e:
        logger.error(fail(f"db init faalde: {e}"))

    # Routers laden (volgorde = zoals jouw README)
    routers = [
        "api.model_router",
        "api.memory",
        "api.uploads",
        "api.dashboard",
        "api.chat",
        "api.routes.embeddings_debug",
        "api.streaming",
        "api.search",
        "api.routes.events",
        "api.routes.learning",
        "api.auth.routes",
    ]

    loaded = []
    failed = []

    for mod in routers:
        try:
            module = __import__(mod, fromlist=["router"])
            if not hasattr(module, "router"):
                raise RuntimeError("module has no attribute 'router'")
            app.include_router(module.router)
            loaded.append(mod)
            logger.info(ok(f"geladen: {mod}"))
        except Exception as e:
            failed.append((mod, str(e)))
            logger.error(fail(f"router {mod} faalde: {e}"))

    logger.info("[routers] geladen totaal: %s", ", ".join(loaded) if loaded else "(none)")
    if failed:
        logger.warning("[routers] failures: %s", "; ".join(f"{m} -> {err}" for m, err in failed))


@app.on_event("shutdown")
async def shutdown():
    # ✅ 1 waarheid: close_database sluit pool
    try:
        from api.db.database import close_database

        await close_database()
        logger.info(ok("db pool closed"))
    except Exception as e:
        logger.warning(f"[shutdown] db close failed: {e}")


# ============================================================
# HEALTHZ (enige waarheid)
# ============================================================
@app.get("/healthz")
async def healthz():
    return {"ok": True, "version": APP_VERSION, "safe_mode": SAFE_MODE}
