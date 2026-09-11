"""
backend/auth.py
---------------
Gestion JWT : création et vérification des tokens.
Basé sur le modèle User existant (niveaux 1-4, SHA256+salt conservé,
compatible avec les comptes existants en DB).
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import get_db
from models.user import User, verify_password

# ─── Configuration JWT ───────────────────────────────────────────────────────
# Générer une clé secrète forte : python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY    = os.getenv("JWT_SECRET_KEY", "changez-moi-en-production")
ALGORITHM     = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "8"))  # 1 journée de travail

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ─── Création du token ───────────────────────────────────────────────────────
def create_access_token(user: User) -> str:
    """
    Crée un JWT contenant l'identité et les droits de l'utilisateur.
    Le niveau est encodé dans le token → pas de requête DB à chaque appel.
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub":       str(user.id_user),
        "username":  user.username,
        "full_name": user.full_name or "",
        "niveau":    user.niveau,
        "exp":       expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ─── Vérification du token ───────────────────────────────────────────────────
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Dépendance FastAPI : vérifie le token JWT et retourne l'utilisateur.
    À injecter dans chaque endpoint protégé via Depends(get_current_user).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalide ou expiré",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload  = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id  = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise credentials_exception

    user = db.get(User, user_id)
    if not user or not user.actif:
        raise credentials_exception
    return user


# ─── Vérification des permissions ────────────────────────────────────────────
def require_permission(action: str):
    """
    Factory de dépendance : vérifie qu'un utilisateur a la permission requise.
    Utilise la méthode can() existante du modèle User.

    Exemple d'usage dans un endpoint :
        @router.get("/users", dependencies=[Depends(require_permission("users"))])
    """
    def _check(current_user: User = Depends(get_current_user)):
        if not current_user.can(action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission refusée (niveau {current_user.niveau} insuffisant)"
            )
        return current_user
    return _check


# ─── Authentification login ──────────────────────────────────────────────────
def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """
    Vérifie les credentials. Compatible avec le hashing SHA256+salt existant.
    Retourne l'utilisateur si valide, None sinon.
    """
    user = db.query(User).filter(
        User.username == username,
        User.actif    == True
    ).first()

    if not user:
        return None
    if not verify_password(password, user.password_hash, user.password_salt):
        return None
    return user
