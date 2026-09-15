"""
backend/routers/settings.py
----------------------------
Key/value application settings (currently: where drawing/plan files are
stored). Administrator only (reuses the "users" permission level).
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import require_permission, get_db
from models import AppSetting

router = APIRouter(prefix="/settings", tags=["Settings"])

PLANS_STORAGE_KEY = "plans_storage"


class PlansStorageConfig(BaseModel):
    provider:  str           = "onedrive"  # "onedrive" | "sharepoint" | "local" | "other"
    base_path: str           = ""          # folder / URL prefix where drawings live
    notes:     Optional[str] = None


def _get_setting(db: Session, key: str) -> Optional[str]:
    row = db.get(AppSetting, key)
    return row.value if row else None


def _set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(AppSetting, key)
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=key, value=value))
    db.commit()


@router.get("/plans-storage", response_model=PlansStorageConfig)
def get_plans_storage(
    db:    Session = Depends(get_db),
    _user          = Depends(require_permission("users")),
):
    raw = _get_setting(db, PLANS_STORAGE_KEY)
    if not raw:
        return PlansStorageConfig()
    return PlansStorageConfig(**json.loads(raw))


@router.put("/plans-storage", response_model=PlansStorageConfig)
def update_plans_storage(
    payload: PlansStorageConfig,
    db:      Session = Depends(get_db),
    _user            = Depends(require_permission("users")),
):
    _set_setting(db, PLANS_STORAGE_KEY, json.dumps(payload.model_dump()))
    return payload
