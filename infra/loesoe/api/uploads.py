import os
import io
import time
import base64
import hmac
import hashlib
import json
from pathlib import Path
from typing import Optional, List, Dict

from fastapi import APIRouter, HTTPException, UploadFile, Header, Request, Query
from fastapi.responses import FileResponse

router = APIRouter()

# === Config (single source of truth) ===
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", "/app/uploads")).resolve()
SIGNER_SECRET = os.getenv("SIGNER_SECRET", "change-me-super-secret-64chars")
DEFAULT_TTL = int(os.getenv("SIGNER_DEFAULT_TTL", "600"))

# === HMAC signer (token = base64url(payload).signature) ===
def _hmac(payload_bytes: bytes) -> str:
    mac = hmac.new(SIGNER_SECRET.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")

def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)

def _sign(filename: str, session_id: str, ttl: int) -> str:
    exp = int(time.time()) + max(1, int(ttl))
    payload = {"f": filename, "s": session_id, "e": exp}
    raw = json.dumps(payload, separators=(",", ":")).encode()
    sig = _hmac(raw)
    return _b64url(raw) + "." + sig

def _verify(token: str) -> Optional[dict]:
    try:
        raw_b64, sig = token.split(".", 1)
        raw = _b64url_decode(raw_b64)
        expected = _hmac(raw)
        if not hmac.compare_digest(expected, sig):
            return None
        payload = json.loads(raw.decode())
        if int(payload.get("e", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None

# === Helpers ===
def _ensure_session_dir(session_id: str) -> Path:
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if any(c in session_id for c in ("/", "\\", "..")):
        raise HTTPException(status_code=400, detail="invalid session_id")
    p = (UPLOADS_DIR / session_id).resolve()
    if UPLOADS_DIR not in p.parents and p != UPLOADS_DIR:
        raise HTTPException(status_code=400, detail="invalid session path")
    p.mkdir(parents=True, exist_ok=True)
    return p

def _sanitize_filename(name: Optional[str]) -> str:
    name = (name or "").strip()
    if not name:
        return f"upload-{int(time.time()*1000)}.bin"
    # drop any path parts
    name = name.replace("\\", "/").split("/")[-1]
    if ".." in name or name.startswith("."):
        raise HTTPException(status_code=400, detail="invalid filename")
    return name

# === Routes ===

@router.post("/uploads")
async def upload_file(
    request: Request,
    session_id: str = Query(..., description="Session id"),
    x_filename: Optional[str] = Header(default=None, convert_underscores=False, alias="X-Filename"),
    file: Optional[UploadFile] = None,
):
    try:
        session_dir = _ensure_session_dir(session_id)
        filename = _sanitize_filename(x_filename or (file.filename if file else None))
        dst = (session_dir / filename).resolve()
        if UPLOADS_DIR not in dst.parents and dst != UPLOADS_DIR:
            raise HTTPException(status_code=400, detail="invalid destination path")

        # Read body
        if file is not None:
            data = await file.read()
        else:
            data = await request.body()
        if not data:
            raise HTTPException(status_code=400, detail="empty body")

        # Optional size cap: 100MB
        if len(data) > 100 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="file too large")

        with open(dst, "wb") as f:
            f.write(data)

        st = dst.stat()
        return {"filename": filename, "size": st.st_size, "created": int(st.st_mtime), "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/uploads")
def list_uploads(session_id: str):
    d = _ensure_session_dir(session_id)
    items: List[Dict] = []
    if not d.exists():
        return []
    for p in d.iterdir():
        if p.is_file():
            st = p.stat()
            items.append({"filename": p.name, "size": st.st_size, "created": int(st.st_mtime)})
    items.sort(key=lambda x: x["created"], reverse=True)
    return items

@router.get("/uploads/signed")
def get_signed_url(session_id: str, filename: str, ttl: int = DEFAULT_TTL):
    if ttl <= 0:
        raise HTTPException(status_code=400, detail="ttl must be > 0")
    d = _ensure_session_dir(session_id)
    filename = _sanitize_filename(filename)
    path = (d / filename).resolve()
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    token = _sign(filename=filename, session_id=session_id, ttl=ttl)
    return {"url": f"/signed/{token}", "expires_in": ttl, "expires_at": int(time.time()) + ttl}

@router.get("/signed/{token}")
def download_signed(token: str):
    payload = _verify(token)
    if not payload:
        raise HTTPException(status_code=404, detail="invalid or expired token")
    session_id = payload.get("s")
    filename = _sanitize_filename(payload.get("f"))
    d = _ensure_session_dir(session_id)
    path = (d / filename).resolve()
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    if UPLOADS_DIR not in path.parents and path != UPLOADS_DIR:
        raise HTTPException(status_code=400, detail="invalid path")
    return FileResponse(str(path), filename=filename, media_type="application/octet-stream")