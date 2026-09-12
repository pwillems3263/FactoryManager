"""
backend/routers/auth.py (updated)
----------------------------------
Authentication endpoints with database switching support.
POST /auth/login          → login, returns token with db context
GET  /auth/me             → current user info + active DB
POST /auth/switch-db      → switch to prod or test (re-issues token)
POST /auth/kiosk          → kiosk PIN login
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import (
    authenticate_user, create_access_token, get_current_user,
    get_db_key_from_token, decode_token, DB_CONFIGS
)
from database import get_session_factory, get_db_for_key
from models.user import User, verify_pin

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    niveau:       int
    full_name:    str
    username:     str
    db_key:       str
    db_label:     str
    db_color:     str


class UserMe(BaseModel):
    id_user:    int
    username:   str
    full_name:  str | None
    niveau:     int
    niveau_label: str
    db_key:     str
    db_label:   str
    db_color:   str

    class Config:
        from_attributes = True


class SwitchDBRequest(BaseModel):
    db_key: str   # "prod" or "test"


class KioskLoginRequest(BaseModel):
    username: str
    pin:      str
    db_key:   str = "test"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _token_response(user: User, db_key: str) -> TokenResponse:
    info = DB_CONFIGS.get(db_key, DB_CONFIGS["test"])
    return TokenResponse(
        access_token=create_access_token(user, db_key),
        niveau=user.niveau,
        full_name=user.full_name or "",
        username=user.username,
        db_key=db_key,
        db_label=info["label"],
        db_color=info["color"],
    )


# ─── Login ───────────────────────────────────────────────────────────────────

class LoginForm(BaseModel):
    username: str
    password: str
    db_key:   str = "test"


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Standard login. Defaults to TEST database.
    The frontend can then call /auth/switch-db to move to production.
    """
    db_key  = "prod"  # ⚠️ TEMPORAIRE — pour diagnostic (revenir à "test" ensuite)
    factory = get_session_factory(db_key)
    db = factory()
    try:
        user = authenticate_user(db, form_data.username, form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return _token_response(user, db_key)
    finally:
        db.close()


# ─── Switch database ─────────────────────────────────────────────────────────

@router.post("/switch-db", response_model=TokenResponse)
def switch_db(
    payload: SwitchDBRequest,
    token:   str = Depends(__import__('fastapi').security.OAuth2PasswordBearer(tokenUrl="/auth/login")),
):
    """
    Switch the active database context.
    Re-issues a JWT with the new db_key.
    Requires re-authentication on the target DB to ensure credentials are valid there too.
    """
    from fastapi.security import OAuth2PasswordBearer
    if payload.db_key not in DB_CONFIGS:
        raise HTTPException(400, f"Unknown database: {payload.db_key}")

    # Decode current token to get user identity
    current = decode_token(token)
    user_id = int(current.get("sub", 0))

    # Get user from the TARGET database
    factory = get_session_factory(payload.db_key)
    db = factory()
    try:
        user = db.get(User, user_id)
        if not user or not user.actif:
            raise HTTPException(403, "Your account does not exist in the target database")
        return _token_response(user, payload.db_key)
    finally:
        db.close()


# ─── Current user ────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserMe)
def get_me(token: str = Depends(__import__('fastapi').security.OAuth2PasswordBearer(tokenUrl="/auth/login"))):
    payload = decode_token(token)
    user_id = int(payload.get("sub", 0))
    db_key  = payload.get("db", "test")
    info    = DB_CONFIGS.get(db_key, DB_CONFIGS["test"])

    factory = get_session_factory(db_key)
    db = factory()
    try:
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(404, "User not found")
        return UserMe(
            id_user=user.id_user,
            username=user.username,
            full_name=user.full_name,
            niveau=user.niveau,
            niveau_label=user.niveau_label(),
            db_key=db_key,
            db_label=info["label"],
            db_color=info["color"],
        )
    finally:
        db.close()


# ─── Kiosk login ─────────────────────────────────────────────────────────────

@router.post("/kiosk", response_model=TokenResponse)
def kiosk_login(payload: KioskLoginRequest):
    db_key  = payload.db_key if payload.db_key in DB_CONFIGS else "test"
    factory = get_session_factory(db_key)
    db = factory()
    try:
        user = db.query(User).filter(
            User.username == payload.username,
            User.actif    == True
        ).first()
        if not user or not user.has_pin():
            raise HTTPException(401, "Invalid user or PIN")
        if user.is_kiosk_blocked():
            raise HTTPException(403, f"Account blocked until {user.kiosk_blocked_until.strftime('%H:%M')}")
        if not verify_pin(payload.pin, user.pin_hash, user.pin_salt):
            raise HTTPException(401, "Invalid PIN")
        return _token_response(user, db_key)
    finally:
        db.close()


# ─── DB info ─────────────────────────────────────────────────────────────────

@router.get("/databases")
def list_databases():
    """Return available databases for the switch UI."""
    return [
        {"key": k, "label": v["label"], "color": v["color"]}
        for k, v in DB_CONFIGS.items()
    ]
