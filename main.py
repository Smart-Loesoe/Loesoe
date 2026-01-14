import os
import sys
import types
import logging
from typing import Optional, Dict, Any, Iterable, Tuple
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

# Pydantic is handig als andere modules dit nodig hebben
try:
    from pydantic import BaseModel  # noqa: F401
except Exception:  # pragma: no cover
    BaseModel = object  # fallback

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(override=True)
except Exception:
    pass

logger = logging.getLogger("loesoe.main")
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

APP_VERSION   = os.getenv("APP_VERSION", "19.0.0-dashboard")
SAFE_MODE     = os.getenv("LOESOE_SAFE_MODE", "0") not in ("0", "false", "False", "")
MODEL_DEFAULT = os.getenv("MODEL_DEFAULT", "gpt-5.1")
DATABASE_URL  = os.getenv("DATABASE_URL", "")
AUTH_SECRET   = os.getenv("AUTH_SECRET", "")

# Globale flags
db_ready: bool = False
db_last_error: Optional[str] = None

auth_ready: bool = False
auth_last_error: Optional[str] = None

# DB-objects (voor latere uitbreidingen)
async_engine = None
AsyncSession = None


# ---------- DB init helpers ----------

def _db_scheme_ok(url: str) -> bool:
    return isinstance(url, str) and url.startswith("postgresql+asyncpg://")


async def _try_init_db() -> None:
    """Zorgt dat de asyncpg-engine klaarstaat."""
    global db_ready, db_last_error, async_engine, AsyncSession

    if not DATABASE_URL:
        db_ready = False
        db_last_error = "DATABASE_URL must be set and use postgresql+asyncpg"
        return

    if not _db_scheme_ok(DATABASE_URL):
        db_ready = False
        db_last_error = f"Expected postgresql+asyncpg scheme, got: {DATABASE_URL.split('://',1)[0]}://"
        return

    try:
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession as _AsyncSession
        from sqlalchemy.orm import sessionmaker

        async_engine = create_async_engine(DATABASE_URL, future=True, echo=False)
        AsyncSession = sessionmaker(async_engine, class_=_AsyncSession, expire_on_commit=False)

        async with async_engine.begin() as conn:
            await conn.run_sync(lambda *_: None)

        db_ready = True
        db_last_error = None
        logger.info("[init] DB geladen met asyncpg")
    except Exception as e:  # pragma: no cover
        db_ready = False
        db_last_error = f"{type(e).__name__}: {e}"
        logger.warning("[init] DB niet geladen: %s", db_last_error)


# ---------- Auth / JWT router ----------

def _inject_auth_db_shim() -> None:
    """
    Maakt api.auth.database => api.database alias,
    zodat de auth-module dezelfde DB-layer gebruikt.
    """
    try:
        import api.database  # type: ignore
        if "api.auth.database" not in sys.modules:
            mod = types.ModuleType("api.auth.database")
            for k, v in vars(api.database).items():
                setattr(mod, k, v)
            sys.modules["api.auth.database"] = mod
            logger.info("[auth] Shim api.auth.database -> api.database geactiveerd")
    except Exception:
        # Niet dodelijk; auth faalt dan bij load
        pass


def _auth_preconditions_ok() -> Optional[str]:
    if not AUTH_SECRET or len(AUTH_SECRET) < 32:
        return "AUTH_SECRET must be set (>=32 chars)"
    if not db_ready:
        return "Database not ready"
    return None


def _try_load_auth(app: FastAPI) -> None:
    """Laadt de auth-router (login/register/me)."""
    global auth_ready, auth_last_error

    try:
        _inject_auth_db_shim()

        candidates = [
            "api.auth.routes",
            "auth.routes",
            "api.routes.auth",
        ]
        auth_router = None

        for cand in candidates:
            try:
                mod = __import__(cand, fromlist=["router"])
                auth_router = getattr(mod, "router", None)
                if auth_router is not None:
                    # optioneel global beschikbaar
                    try:
                        global get_current_user  # type: ignore
                        get_current_user = getattr(mod, "get_current_user", None)
                    except Exception:
                        pass
                    break
            except Exception:
                continue

        if auth_router is None:
            raise ModuleNotFoundError("Geen auth router gevonden (probeer api.auth.routes / auth.routes)")

        app.include_router(auth_router)

        auth_ready = True
        auth_last_error = None
        logger.info("[auth] Auth-router geladen")
    except Exception as e:  # pragma: no cover
        auth_ready = False
        auth_last_error = f"{type(e).__name__}: {e}"
        logger.warning("[init] Auth niet geladen: %s", auth_last_error)


# ---------- Dynamische routers (dashboard, memory, chat, ...) ----------

def _iter_router_candidates() -> Iterable[Tuple[str, str]]:
    """
    Bepaalt welke router-modules we proberen te includen.

    Volgorde:
    - api.model_router  → GPT-5.1 router / tools
    - api.memory        → zelflerend geheugen / last_session
    - api.uploads       → uploads (nu nog uitgeschakeld)
    - api.dashboard     → dashboard + slimheidsmeter
    - api.chat          → chat + behavior scoring (Fase 20C)
    """
    return (
        ("api.model_router", "router"),
        ("api.memory", "router"),
        ("api.uploads", "router"),
        ("api.dashboard", "router"),
        ("api.chat", "router"),
    )


def _try_include_routers(app: FastAPI) -> None:
    loaded = []

    for mod_name, attr in _iter_router_candidates():
        try:
            mod = __import__(mod_name, fromlist=[attr])
            router = getattr(mod, attr, None)
            if router is None:
                continue
            app.include_router(router)
            loaded.append(mod_name)
        except Exception as e:
            logger.info("[routers] overslaan %s: %s: %s", mod_name, type(e).__name__, e)

    if loaded:
        logger.info("[routers] geladen: %s", ", ".join(loaded))


# ---------- Lifespan / Startup ----------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[startup] Loesoe v%s (SAFE_MODE=%s)", APP_VERSION, SAFE_MODE)
    logger.info("[startup] MODEL_DEFAULT=%s", MODEL_DEFAULT)
    logger.info("[startup] DATABASE_URL=%s", (DATABASE_URL.split('@')[-1] if DATABASE_URL else "<not set>"))

    # 1. Database
    await _try_init_db()

    # 2. Auth (als mogelijk)
    missing = _auth_preconditions_ok()
    if missing is None:
        _try_load_auth(app)
    else:
        global auth_ready, auth_last_error
        auth_ready = False
        auth_last_error = missing
        logger.warning("[init] Auth niet geladen: %s", missing)

    # 3. Routers (dashboard, memory, chat, ...)
    _try_include_routers(app)

    yield


# ---------- FastAPI app ----------

app = FastAPI(
    title="Loesoe API",
    version=APP_VERSION,
    lifespan=lifespan,
)

# CORS
_default_origins = {"http://localhost:5173", "http://127.0.0.1:5173"}
_env_origins = {o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if o.strip()}
allow_origins = list((_default_origins | _env_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Authorization"],
)
logger.info("[cors] enabled for: %s", ", ".join(allow_origins))


# ---------- Health / Debug endpoints ----------

def _health_payload() -> Dict[str, Any]:
    return {
        "ok": True,
        "version": APP_VERSION,
        "model": MODEL_DEFAULT,
        "safe_mode": SAFE_MODE,
        "db_ready": db_ready,
        "auth_ready": auth_ready,
        "db_driver": "asyncpg" if _db_scheme_ok(DATABASE_URL) else "unknown",
        "last_init_error_db": db_last_error,
        "last_init_error_auth": auth_last_error,
        "python": sys.version.split()[0],
    }


@app.get("/healthz")
async def healthz():
    return JSONResponse(_health_payload())


@app.get("/debug/env")
async def debug_env():
    return {
        "MODEL_DEFAULT": MODEL_DEFAULT,
        "DATABASE_URL": ("***asyncpg***" if _db_scheme_ok(DATABASE_URL) else (DATABASE_URL or "")),
        "AUTH_SECRET_len": len(AUTH_SECRET or ""),
        "SAFE_MODE": SAFE_MODE,
        "TZ": os.getenv("TZ", ""),
        "CORS_ALLOW_ORIGINS": allow_origins,
    }


@app.get("/__dbcheck")
async def dbcheck():
    if not db_ready:
        raise HTTPException(status_code=503, detail=db_last_error or "db not ready")
    return {"ok": True, "driver": "asyncpg"}


@app.get("/me")
async def me_fallback():
    if not auth_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth niet geladen (SAFE_MODE, ontbrekende AUTH_SECRET of importfout)"
        )
    # Als auth wel is geladen, redirecten we naar echte /auth/me
    return RedirectResponse(url="/auth/me", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@app.get("/")
async def root():
    return {"hello": "loesoe", "version": APP_VERSION}
