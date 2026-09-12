"""
backend/auth.py
---------------
JWT authentication with multi-database support.
The active database ('prod' or 'test') is stored in the JWT token.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import get_session_factory, get_db_for_key, DB_CONFIGS
from models.user import User, verify_password

SECRET_KEY                = os.getenv("JWT_SECRET_KEY", "changez-moi-en-production")
ALGORITHM                 = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "8"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ─── Token creation ───────────────────────────────────────────────────────────

def create_access_token(user: User, db_key: str = "test") -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub":       str(user.id_user),
        "username":  user.username,
        "full_name": user.full_name or "",
        "niveau":    user.niveau,
        "db":        db_key,          # ← database context stored in token
        "exp":       expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ─── Token decoding ───────────────────────────────────────────────────────────

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─── FastAPI dependencies ─────────────────────────────────────────────────────

def get_current_user_and_db(token: str = Depends(oauth2_scheme)):
    """
    Returns (user, db_session, db_key).
    The db_session targets the database specified in the JWT token.
    """
    payload  = decode_token(token)
    user_id  = int(payload.get("sub", 0))
    db_key   = payload.get("db", "test")

    factory = get_session_factory(db_key)
    db = factory()
    try:
        user = db.get(User, user_id)
        if not user or not user.actif:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        return user, db, db_key
    except HTTPException:
        db.close()
        raise
    except Exception:
        db.close()
        raise


def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Simplified dependency — returns only the user (for endpoints that manage their own DB session)."""
    payload = decode_token(token)
    user_id = int(payload.get("sub", 0))
    db_key  = payload.get("db", "test")

    factory = get_session_factory(db_key)
    db = factory()
    try:
        user = db.get(User, user_id)
        if not user or not user.actif:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        return user
    finally:
        db.close()


def get_db_key_from_token(token: str = Depends(oauth2_scheme)) -> str:
    """Extract the db_key from the token."""
    payload = decode_token(token)
    return payload.get("db", "test")


def get_db(token: str = Depends(oauth2_scheme)):
    """
    FastAPI dependency: open a DB session targeting the database in the JWT.
    Usage: db: Session = Depends(get_db)
    """
    payload = decode_token(token)
    db_key  = payload.get("db", "test")
    yield from get_db_for_key(db_key)


def require_permission(action: str):
    """
    Permission check dependency.
    Returns (user, db_key) if allowed.
    """
    def _check(token: str = Depends(oauth2_scheme)):
        payload = decode_token(token)
        user_id = int(payload.get("sub", 0))
        db_key  = payload.get("db", "test")

        factory = get_session_factory(db_key)
        db = factory()
        try:
            user = db.get(User, user_id)
            if not user or not user.actif:
                raise HTTPException(status_code=401, detail="Unauthorized")
            if not user.can(action):
                raise HTTPException(
                    status_code=403,
                    detail=f"Permission denied (level {user.niveau} insufficient)"
                )
            return user
        finally:
            db.close()
    return _check


# ─── Login helper ─────────────────────────────────────────────────────────────

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    user = db.query(User).filter(
        User.username == username,
        User.actif    == True
    ).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash, user.password_salt):
        return None
    return user
