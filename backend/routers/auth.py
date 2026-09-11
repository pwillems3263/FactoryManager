from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from auth import authenticate_user, create_access_token, get_current_user
from database import get_db
from models.user import User, verify_pin

router = APIRouter(prefix="/auth", tags=["Authentification"])

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    niveau: int
    full_name: str
    username: str

class UserMe(BaseModel):
    id_user: int
    username: str
    full_name: str | None
    niveau: int
    niveau_label: str
    class Config:
        from_attributes = True

class KioskLoginRequest(BaseModel):
    username: str
    pin: str

@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Identifiant ou mot de passe incorrect", headers={"WWW-Authenticate": "Bearer"})
    token = create_access_token(user)
    return TokenResponse(access_token=token, niveau=user.niveau, full_name=user.full_name or "", username=user.username)

@router.get("/me", response_model=UserMe)
def get_me(current_user: User = Depends(get_current_user)):
    return UserMe(id_user=current_user.id_user, username=current_user.username, full_name=current_user.full_name, niveau=current_user.niveau, niveau_label=current_user.niveau_label())

@router.post("/kiosk", response_model=TokenResponse)
def kiosk_login(payload: KioskLoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username, User.actif == True).first()
    if not user or not user.has_pin():
        raise HTTPException(status_code=401, detail="Utilisateur ou PIN invalide")
    if user.is_kiosk_blocked():
        raise HTTPException(status_code=403, detail="Compte bloque")
    if not verify_pin(payload.pin, user.pin_hash, user.pin_salt):
        raise HTTPException(status_code=401, detail="PIN incorrect")
    token = create_access_token(user)
    return TokenResponse(access_token=token, niveau=user.niveau, full_name=user.full_name or "", username=user.username)
