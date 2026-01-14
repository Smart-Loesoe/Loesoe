from fastapi import APIRouter, Header, HTTPException
from typing import Optional, Dict, List, Any
from datetime import datetime
from pathlib import Path
import json
import os
import logging

from pydantic import BaseModel
import jwt  # PyJWT

# Postgres (Fase 22.1)
import asyncpg

logger = logging.getLogger("loesoe.memory")

router = APIRouter(tags=["memory"])  # main hangt routes direct


# =========================
# Filesystem (legacy / snapshots)
# =========================
MEM_DIR = Path("data") / "memory"
MEM_DIR.mkdir(parents=True, exist_ok=True)

ZELFLEREN_PATH = MEM_DIR / "zelfleren.json"
LAST_SESSION_PATH = MEM_DIR / "last_session.json"
SNAPSHOTS_DIR = MEM_DIR / "snapshots"
SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)


# =========================
# JWT helper
# =========================
def _get_user_from_header(authorization: Optional[str]) -> Dict[str, Any]:
    """
    Decodeert de JWT direct uit de Authorization-header.
    Verwacht: 'Bearer <token>'.
    Geeft dict terug met minimaal 'id' en (optioneel) 'name'.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header")

    token = parts[1]
    secret = os.getenv("AUTH_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="Server misconfigured: AUTH_SECRET missing")

    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if "id" not in payload:
        raise HTTPException(status_code=401, detail="Token missing user id")

    return payload


# =========================
# Pydantic modellen
# =========================
class MemoryUpdate(BaseModel):
    profile: Optional[Dict[str, Any]] = None
    preferences: Optional[Dict[str, Any]] = None
    habits: Optional[Dict[str, int]] = None
    topics_counters: Optional[Dict[str, int]] = None
    modules_usage: Optional[Dict[str, int]] = None
    scores: Optional[Dict[str, Any]] = None


class SnapshotRestoreRequest(BaseModel):
    filename: str


# =========================
# JSON helpers (legacy)
# =========================
def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning(f"[memory] JSON load failed: {path}", exc_info=True)
        return default


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _utc_stamp() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def _create_snapshot(label: str, data: Dict[str, Any], keep_last: int = 20) -> None:
    """
    Maakt een snapshot van de volledige structuur (legacy safety-net).
    - keep_last: behoud alleen de laatste N snapshots per label
    """
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{label}_{_utc_stamp()}.json"
    (SNAPSHOTS_DIR / filename).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Rotatie
    files = sorted(SNAPSHOTS_DIR.glob(f"{label}_*.json"))
    if len(files) > keep_last:
        for f in files[: len(files) - keep_last]:
            try:
                f.unlink()
            except Exception:
                logger.warning(f"[memory] snapshot cleanup failed: {f}", exc_info=True)


def _list_snapshots(label: str) -> List[Dict[str, Any]]:
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    out: List[Dict[str, Any]] = []
    for f in sorted(SNAPSHOTS_DIR.glob(f"{label}_*.json"), reverse=True):
        try:
            stat = f.stat()
            out.append(
                {
                    "filename": f.name,
                    "created_at": datetime.utcfromtimestamp(stat.st_mtime).isoformat() + "Z",
                    "size_bytes": stat.st_size,
                }
            )
        except Exception:
            continue
    return out


# =========================
# Default data
# =========================
def _default_selflearn() -> Dict[str, Any]:
    return {"users": {}}


def _default_user_block() -> Dict[str, Any]:
    return {
        "profile": {},
        "preferences": {},
        "habits": {},
        "topics_counters": {},
        "modules_usage": {},
        "documents": [],
        "images": [],
        "charts": [],
        "behavior_log": [],
        "emotion_summary": {"current": None, "history": []},
        "last_updated": datetime.utcnow().isoformat() + "Z",
    }


def _get_or_create_selflearn_user(data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
    users = data.setdefault("users", {})
    key = str(user_id)
    if key not in users:
        users[key] = _default_user_block()
    return users[key]


def _apply_scores_to_user_block(user_block: Dict[str, Any], scores: Dict[str, Any]) -> None:
    """
    Simpele score-logging (Fase 20C compat).
    """
    try:
        log = user_block.setdefault("behavior_log", [])
        log.append({"timestamp": datetime.utcnow().isoformat() + "Z", "scores": scores})
        if len(log) > 200:
            del log[:-200]
    except Exception:
        logger.warning("[memory] apply_scores failed", exc_info=True)


# =========================
# Postgres helpers (Fase 22.1)
# =========================
def _normalize_for_asyncpg(url: str) -> str:
    """
    asyncpg snapt geen 'postgresql+asyncpg://'.
    SQLAlchemy async gebruikt dat schema wel.
    Dus: strip '+asyncpg' voor asyncpg.
    """
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url.split("://", 1)[1]
    if url.startswith("postgres+asyncpg://"):
        return "postgresql://" + url.split("://", 1)[1]
    return url


def _pg_dsn() -> Optional[str]:
    """
    Probeert DATABASE_URL, anders bouwt hij DSN uit env vars.
    Returned DSN is altijd asyncpg-compatibel.
    """
    url = os.getenv("DATABASE_URL")
    if url:
        return _normalize_for_asyncpg(url)

    host = os.getenv("POSTGRES_HOST") or os.getenv("DB_HOST") or "db"
    port = int(os.getenv("POSTGRES_PORT") or os.getenv("DB_PORT") or "5432")
    user = os.getenv("POSTGRES_USER") or os.getenv("DB_USER") or "loesoe"
    password = os.getenv("POSTGRES_PASSWORD") or os.getenv("DB_PASSWORD") or "loesoe"
    database = os.getenv("POSTGRES_DB") or os.getenv("DB_NAME") or "loesoe"

    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


async def _db_upsert_selflearning(user_id: int, user_block: Dict[str, Any]) -> None:
    dsn = _pg_dsn()
    if not dsn:
        return

    try:
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute(
                """
                INSERT INTO memory_selflearning (user_id, data, updated_at)
                VALUES ($1, $2::jsonb, NOW())
                ON CONFLICT (user_id)
                DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()
                """,
                user_id,
                json.dumps(user_block, ensure_ascii=False),
            )
        finally:
            await conn.close()
    except Exception:
        logger.warning("[memory] DB upsert failed (fallback blijft JSON)", exc_info=True)


async def _db_get_selflearning(user_id: int) -> Optional[Dict[str, Any]]:
    dsn = _pg_dsn()
    if not dsn:
        return None

    try:
        conn = await asyncpg.connect(dsn)
        try:
            row = await conn.fetchrow(
                "SELECT data FROM memory_selflearning WHERE user_id = $1",
                user_id,
            )
            if not row:
                return None

            data = row["data"]
            if isinstance(data, str):
                return json.loads(data)
            return dict(data)
        finally:
            await conn.close()
    except Exception:
        logger.warning("[memory] DB get failed (fallback naar JSON)", exc_info=True)
        return None


# =========================
# Endpoints
# =========================
@router.get("/selflearning")
async def get_selflearning(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    Haalt het zelflerend geheugenblok op voor de ingelogde gebruiker.
    Fase 22.1:
    - probeert eerst Postgres (memory_selflearning)
    - fallback: data/memory/zelfleren.json
    """
    user_payload = _get_user_from_header(authorization)
    user_id = int(user_payload["id"])
    user_name = user_payload.get("name")

    # 1) DB first
    db_block = await _db_get_selflearning(user_id)
    if db_block is not None:
        return {"user_id": user_id, "name": user_name, "memory": db_block, "source": "db"}

    # 2) fallback JSON
    data = _load_json(ZELFLEREN_PATH, _default_selflearn())
    user_block = _get_or_create_selflearn_user(data, user_id)
    return {"user_id": user_id, "name": user_name, "memory": user_block, "source": "json"}


@router.post("/selflearning/update")
async def update_selflearning(
    payload: MemoryUpdate,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """
    Update zelflerend geheugen.
    Fase 21: snapshot (legacy safety-net)
    Fase 22.1: upsert naar Postgres (memory_selflearning) per user_id
    """
    user_payload = _get_user_from_header(authorization)
    user_id = int(user_payload["id"])

    # JSON legacy struct bijhouden (meerdere users in 1 file)
    data = _load_json(ZELFLEREN_PATH, _default_selflearn())
    user_block = _get_or_create_selflearn_user(data, user_id)

    if payload.profile:
        user_block.setdefault("profile", {}).update(payload.profile)

    if payload.preferences:
        user_block.setdefault("preferences", {}).update(payload.preferences)

    if payload.habits:
        habits = user_block.setdefault("habits", {})
        for k, v in payload.habits.items():
            habits[k] = habits.get(k, 0) + int(v)

    if payload.topics_counters:
        topics = user_block.setdefault("topics_counters", {})
        for k, v in payload.topics_counters.items():
            topics[k] = topics.get(k, 0) + int(v)

    if payload.modules_usage:
        mods = user_block.setdefault("modules_usage", {})
        for k, v in payload.modules_usage.items():
            mods[k] = mods.get(k, 0) + int(v)

    if payload.scores:
        _apply_scores_to_user_block(user_block, payload.scores)

    user_block["last_updated"] = datetime.utcnow().isoformat() + "Z"

    # 1) JSON save + snapshot (blijft werken zoals jij gewend bent)
    _save_json(ZELFLEREN_PATH, data)
    _create_snapshot("selflearning", data)

    # 2) DB upsert (Fase 22.1)
    await _db_upsert_selflearning(user_id, user_block)

    return {"status": "ok", "user_id": user_id, "memory": user_block}


@router.get("/selflearning/snapshots")
def list_selflearning_snapshots(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    _get_user_from_header(authorization)
    snapshots = _list_snapshots("selflearning")
    return {"label": "selflearning", "count": len(snapshots), "snapshots": snapshots}


@router.post("/selflearning/restore")
def restore_selflearning_snapshot(
    payload: SnapshotRestoreRequest,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    _get_user_from_header(authorization)

    filename = payload.filename
    if not filename.startswith("selflearning_") or not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Ongeldige snapshot-naam")

    snap_path = SNAPSHOTS_DIR / filename
    if not snap_path.exists():
        raise HTTPException(status_code=404, detail="Snapshot niet gevonden")

    data = _load_json(snap_path, None)
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Snapshot inhoud ongeldig")

    _save_json(ZELFLEREN_PATH, data)
    return {"status": "ok", "restored": filename}
