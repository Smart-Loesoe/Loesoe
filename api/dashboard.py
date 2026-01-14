# api/dashboard.py

from datetime import datetime
from pathlib import Path
import json
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# ✅ JWT: altijd via get_current_user (géén demo-user in dit bestand)
try:
    from api.auth.routes import get_current_user
except ImportError:
    from auth.routes import get_current_user  # fallback voor lokale runs

# 🔁 Fase 20 – Zelflerend geheugen / Slimheidsmeter v2
try:
    # verwacht: modules/zelflerend/analyse.py
    from modules.zelflerend.analyse import get_global_self_learning_summary
    print("[ok] zelflerend analyse-module geladen")
except Exception as e:
    print(
        f"[warn] zelflerend analyse-module niet geladen: "
        f"{e.__class__.__name__}: {e}"
    )
    get_global_self_learning_summary = None

# 🔥 Slimheidsmeter V2-module
try:
    from modules.status_slimheidsmeter import calculate_slimheidsmeter
    print("[ok] slimheidsmeter-module geladen")
except Exception as e:
    print(
        f"[warn] slimheidsmeter-module niet geladen: "
        f"{e.__class__.__name__}: {e}"
    )
    calculate_slimheidsmeter = None

# ➜ /dashboard
router = APIRouter(prefix="/dashboard", tags=["dashboard"])

DATA_DIR = Path("data") / "memory"
ZELFLEREN_PATH = DATA_DIR / "zelfleren.json"
LAST_SESSION_PATH = DATA_DIR / "last_session.json"
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", "data/uploads"))


class ModuleStatus(BaseModel):
    key: str
    status: str  # ok | warn | off
    note: str | None = None


class DashboardPayload(BaseModel):
    user: dict
    slimheidsmeter: float
    modules: list[ModuleStatus]
    last_session: dict | None
    updated_at: str
    self_learning: dict | None = None  # Fase 20 blok


def file_exists(p: Path) -> bool:
    try:
        return p.exists()
    except Exception:
        return False


def load_json(p: Path) -> dict | None:
    if not file_exists(p):
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def calculate_slimheid(modules: list[ModuleStatus]) -> float:
    """
    V1-implementatie op basis van alleen modules.
    Gebruiken we als fallback als V2 niet beschikbaar is.
    """
    score = 0.0
    for m in modules:
        if m.status == "ok":
            score += 1.0
        elif m.status == "warn":
            score += 0.5

    max_score = float(len(modules)) or 1.0
    return round((score / max_score) * 100.0, 1)


def _build_self_learning_block(current_user) -> dict | None:
    """
    Bouwt het zelflerend-blok voor het dashboard, op basis van:
    - modules/zelflerend/analyse.py (globale scores)
    - data/memory/zelfleren.json (state per gebruiker)
    """

    if get_global_self_learning_summary is None:
        return None

    try:
        summary = get_global_self_learning_summary()
    except Exception as e:
        print(
            f"[warn] self-learning summary failed: "
            f"{e.__class__.__name__}: {e}"
        )
        return None

    if not summary.get("has_data"):
        return {
            "has_data": False,
            "avg_score": 0.0,
            "user_score": None,
            "last_mood": None,
            "preferences_count": 0,
            "patterns": {},
        }

    user_id = getattr(current_user, "id", 1)
    uid = str(user_id)

    user_scores = summary.get("user_scores", {}) or {}
    user_score = user_scores.get(uid)

    state = load_json(ZELFLEREN_PATH) or {}
    users = state.get("users", {})
    user_state = users.get(uid, {})

    prefs = user_state.get("preferences", []) or []
    patterns = user_state.get("patterns", {}) or {}
    mood_state = user_state.get("mood", {}) or {}
    last_mood = mood_state.get("last")

    return {
        "has_data": True,
        "avg_score": summary.get("avg_score", 0.0),
        "user_score": user_score,
        "last_mood": last_mood,
        "preferences_count": len(prefs),
        "patterns": patterns,
    }


@router.get("", response_model=DashboardPayload)
async def get_dashboard(current_user=Depends(get_current_user)):
    """
    Dashboard is ALLEEN bereikbaar met geldige JWT.
    Geen demo-fallback meer in dit bestand.
    """
    if not current_user:
        # zou eigenlijk nooit gebeuren: get_current_user hoort al 401 te gooien
        raise HTTPException(status_code=401, detail="Unauthorized")

    modules: list[ModuleStatus] = []

    # --- AUTH ---
    modules.append(
        ModuleStatus(
            key="auth",
            status="ok",
            note="JWT actief",
        )
    )

    # --- DATABASE FILE ---
    db_file = Path("api/database.py")
    modules.append(
        ModuleStatus(
            key="database",
            status="ok" if file_exists(db_file) else "warn",
            note="Async engine aanwezig in api/database.py",
        )
    )

    # --- DATABASE CONNECTION ---
    try:
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            engine = create_async_engine(db_url, echo=False, future=True)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            modules.append(
                ModuleStatus(
                    key="database_conn",
                    status="ok",
                    note="DB connectie OK",
                )
            )
        else:
            modules.append(
                ModuleStatus(
                    key="database_conn",
                    status="warn",
                    note="Geen DATABASE_URL gevonden",
                )
            )
    except Exception as e:
        modules.append(
            ModuleStatus(
                key="database_conn",
                status="warn",
                note=f"DB probe error: {e.__class__.__name__}",
            )
        )

    # --- STREAMING ---
    sse_exists = any("stream" in p.name.lower() for p in Path("api").glob("*.py"))
    modules.append(
        ModuleStatus(
            key="streaming",
            status="ok" if sse_exists else "warn",
            note="SSE endpoint aanwezig" if sse_exists else "SSE ontbreekt",
        )
    )

    # --- UPLOADS ---
    uploads_file = Path("api/uploads.py")
    if not file_exists(uploads_file):
        modules.append(
            ModuleStatus(
                key="uploads",
                status="off",
                note="uploads.py ontbreekt",
            )
        )
    else:
        if UPLOADS_DIR.exists():
            modules.append(
                ModuleStatus(
                    key="uploads",
                    status="ok",
                    note=f"Uploads-map aanwezig: {UPLOADS_DIR}",
                )
            )
        else:
            modules.append(
                ModuleStatus(
                    key="uploads",
                    status="warn",
                    note=f"Uploads-map ontbreekt: {UPLOADS_DIR}",
                )
            )

    # --- DASHBOARD API ---
    modules.append(
        ModuleStatus(
            key="dashboard_api",
            status="ok",
            note="/dashboard endpoint actief",
        )
    )

    # --- ZELFLEREND GEHEUGEN BESTAND ---
    if file_exists(ZELFLEREN_PATH):
        modules.append(
            ModuleStatus(
                key="zelflerend_geheugen",
                status="ok",
                note="zelfleren.json aanwezig",
            )
        )
    else:
        modules.append(
            ModuleStatus(
                key="zelflerend_geheugen",
                status="warn",
                note="zelfleren.json mist",
            )
        )

    # --- LAST SESSION ---
    last_session = load_json(LAST_SESSION_PATH)

    # Minimaal current_user markeren als actief
    try:
        state = last_session or {"version": 1, "users": {}}
        users = state.setdefault("users", {})
        uid = str(getattr(current_user, "id", 1))

        user_state = users.get(uid) or {}
        now_iso = datetime.utcnow().isoformat() + "Z"

        user_state.setdefault("last_login", None)
        user_state.setdefault("last_logout", None)
        user_state["last_action"] = now_iso

        users[uid] = user_state
        last_session = state

        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            LAST_SESSION_PATH.write_text(
                json.dumps(state, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            print(
                f"[dashboard] kon last_session niet opslaan: "
                f"{e.__class__.__name__}: {e}"
            )
    except Exception as e:
        print(
            f"[dashboard] last_session update failed: "
            f"{e.__class__.__name__}: {e}"
        )

    # --- ZELFLEREND BLOK (FASE 20) ---
    self_learning = _build_self_learning_block(current_user)

    # --- SLIMHEIDSMETER V2 (met fallback naar V1) ---
    if calculate_slimheidsmeter is not None and self_learning is not None:
        try:
            modules_raw = [m.dict() for m in modules]
            last_session_raw = last_session or {}
            slimheidsmeter = calculate_slimheidsmeter(
                modules_raw=modules_raw,
                self_learning_raw=self_learning,
                last_session_raw=last_session_raw,
            )
        except Exception as e:
            print(
                f"[warn] slimheidsmeter v2 failed, fallback v1: "
                f"{e.__class__.__name__}: {e}"
            )
            slimheidsmeter = calculate_slimheid(modules)
    else:
        slimheidsmeter = calculate_slimheid(modules)

    return DashboardPayload(
        user={
            "id": getattr(current_user, "id", 1),
            "name": getattr(current_user, "name", "Richard"),
        },
        slimheidsmeter=slimheidsmeter,
        modules=modules,
        last_session=last_session,
        updated_at=datetime.utcnow().isoformat() + "Z",
        self_learning=self_learning,
    )
