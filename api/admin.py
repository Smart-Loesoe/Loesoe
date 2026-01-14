# api/admin.py

import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from .auth.utils import get_current_user  # je bestaande auth

router = APIRouter(prefix="/admin", tags=["admin"])

BASE_DIR = Path(__file__).resolve().parent.parent
ADMIN_SETTINGS_PATH = BASE_DIR / "data" / "memory" / "admin_settings.json"


class AdminSettings(BaseModel):
  safe_mode: bool = False
  streaming_enabled: bool = True
  websearch_enabled: bool = True


def _load_settings() -> AdminSettings:
  if not ADMIN_SETTINGS_PATH.exists():
    return AdminSettings()
  data = json.loads(ADMIN_SETTINGS_PATH.read_text(encoding="utf-8"))
  return AdminSettings(**data)


def _save_settings(settings: AdminSettings) -> None:
  ADMIN_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
  ADMIN_SETTINGS_PATH.write_text(
    settings.model_dump_json(indent=2, ensure_ascii=False),
    encoding="utf-8",
  )


@router.get("/settings", response_model=AdminSettings)
async def get_admin_settings(current_user=Depends(get_current_user)):
  return _load_settings()


@router.post("/settings", response_model=AdminSettings)
async def update_admin_settings(
  settings: AdminSettings,
  current_user=Depends(get_current_user),
):
  try:
    _save_settings(settings)
    return settings
  except Exception as e:
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail=f"Kon admin settings niet opslaan: {e}",
    )
