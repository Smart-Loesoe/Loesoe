# loesoe/api/uploads.py
from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel
from typing import List
from pathlib import Path
from datetime import datetime
import os
import uuid

# ✅ Prefix toevoegen zodat prefix + pad nooit allebei leeg zijn
router = APIRouter(prefix="/uploads", tags=["uploads"])

# ✅ Default pad afgestemd op jouw container layout (/app/data is gemount)
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", "/app/data/uploads"))
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


class UploadItem(BaseModel):
    filename: str
    size: int
    created: str


def _session_dir(session_id: str) -> Path:
    p = UPLOADS_DIR / session_id
    p.mkdir(parents=True, exist_ok=True)
    return p


@router.post("/binary", response_model=UploadItem)
async def upload_binary(
    request: Request,
    session_id: str = Query(..., description="Sessienaam/id om uploads te groeperen"),
):
    """
    Ontvangt ruwe binary (application/octet-stream) in de request body.
    Bestandsnaam optioneel via header 'X-Filename' (case-insensitive).
    """
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="Lege body")

    x_filename = request.headers.get("x-filename") or request.headers.get("X-Filename")
    if x_filename:
        name = os.path.basename(x_filename)
    else:
        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        name = f"upload-{ts}-{uuid.uuid4().hex[:8]}.bin"

    target_dir = _session_dir(session_id)
    target_path = target_dir / name
    target_path.write_bytes(data)

    stat = target_path.stat()
    return UploadItem(
        filename=name,
        size=stat.st_size,
        created=datetime.utcfromtimestamp(stat.st_mtime).isoformat() + "Z",
    )


@router.get("/list", response_model=List[UploadItem])
async def list_uploads(
    session_id: str = Query(..., description="Sessienaam/id om uploads op te vragen"),
):
    """
    Lijst alle bestanden binnen een session_id.
    """
    p = _session_dir(session_id)
    items: List[UploadItem] = []
    for f in sorted(p.glob("*")):
        if f.is_file():
            s = f.stat()
            items.append(
                UploadItem(
                    filename=f.name,
                    size=s.st_size,
                    created=datetime.utcfromtimestamp(s.st_mtime).isoformat() + "Z",
                )
            )
    return items
