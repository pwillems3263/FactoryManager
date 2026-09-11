"""
backend/routers/users.py
-------------------------
CRUD Users — Admin only (niveau 4)
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import require_permission
from database import get_db
from models.user import User, hash_password

router = APIRouter(prefix="/users", tags=["Users"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username:  str
    full_name: Optional[str] = None
    password:  str
    niveau:    int = 1
    actif:     bool = True


class UserUpdate(BaseModel):
    full_name: Optional[str]  = None
    niveau:    Optional[int]  = None
    actif:     Optional[bool] = None


class UserPasswordUpdate(BaseModel):
    new_password: str


class UserResponse(BaseModel):
    id_user:   int
    username:  str
    full_name: Optional[str]
    niveau:    int
    niveau_label: str
    actif:     bool
    has_pin:   bool

    class Config:
        from_attributes = True


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _to_response(u: User) -> UserResponse:
    return UserResponse(
        id_user=u.id_user,
        username=u.username,
        full_name=u.full_name,
        niveau=u.niveau,
        niveau_label=u.niveau_label(),
        actif=u.actif,
        has_pin=u.has_pin(),
    )


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("", response_model=list[UserResponse])
def list_users(
    db:    Session = Depends(get_db),
    _user          = Depends(require_permission("users")),
):
    return [_to_response(u) for u in
            db.query(User).order_by(User.username).all()]


@router.get("/{id_user}", response_model=UserResponse)
def get_user(id_user: int, db: Session = Depends(get_db),
             _user=Depends(require_permission("users"))):
    u = db.get(User, id_user)
    if not u:
        raise HTTPException(404, "User not found")
    return _to_response(u)


@router.post("", response_model=UserResponse, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db),
                _user=Depends(require_permission("users"))):
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(409, f"Username '{payload.username}' already exists")

    h, s = hash_password(payload.password)
    u = User(
        username=payload.username,
        full_name=payload.full_name,
        password_hash=h,
        password_salt=s,
        niveau=payload.niveau,
        actif=payload.actif,
    )
    db.add(u); db.commit(); db.refresh(u)
    return _to_response(u)


@router.put("/{id_user}", response_model=UserResponse)
def update_user(id_user: int, payload: UserUpdate,
                db: Session = Depends(get_db),
                _user=Depends(require_permission("users"))):
    u = db.get(User, id_user)
    if not u:
        raise HTTPException(404, "User not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(u, field, value)
    db.commit(); db.refresh(u)
    return _to_response(u)


@router.put("/{id_user}/password", response_model=UserResponse)
def change_password(id_user: int, payload: UserPasswordUpdate,
                    db: Session = Depends(get_db),
                    _user=Depends(require_permission("users"))):
    u = db.get(User, id_user)
    if not u:
        raise HTTPException(404, "User not found")
    h, s = hash_password(payload.new_password)
    u.password_hash = h
    u.password_salt = s
    db.commit(); db.refresh(u)
    return _to_response(u)


@router.delete("/{id_user}", status_code=204)
def delete_user(id_user: int, db: Session = Depends(get_db),
                current_user=Depends(require_permission("users"))):
    u = db.get(User, id_user)
    if not u:
        raise HTTPException(404, "User not found")
    if u.id_user == current_user.id_user:
        raise HTTPException(400, "Cannot delete your own account")
    db.delete(u); db.commit()
