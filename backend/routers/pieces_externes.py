"""
backend/routers/pieces_externes.py
-----------------------------------
CRUD External Parts (PieceExterne)
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import require_permission
from database import get_db
from models import PieceExterne, Composant

router = APIRouter(prefix="/external-parts", tags=["External Parts"])


class PieceExterneBase(BaseModel):
    code_produit:  Optional[str]   = None
    nom:           str
    description:   Optional[str]   = None
    fournisseur:   Optional[str]   = None
    prix_unitaire: Optional[float] = None


class PieceExterneCreate(PieceExterneBase):
    pass


class PieceExterneUpdate(BaseModel):
    code_produit:  Optional[str]   = None
    nom:           Optional[str]   = None
    description:   Optional[str]   = None
    fournisseur:   Optional[str]   = None
    prix_unitaire: Optional[float] = None


class PieceExterneResponse(BaseModel):
    id_piece_externe: int
    code_produit:     Optional[str]
    nom:              str
    description:      Optional[str]
    fournisseur:      Optional[str]
    prix_unitaire:    Optional[float]
    nb_composants:    int

    class Config:
        from_attributes = True


class PieceExterneListResponse(BaseModel):
    items: list[PieceExterneResponse]
    total: int
    page:  int
    pages: int


def _to_response(p: PieceExterne, db: Session) -> PieceExterneResponse:
    nb = db.query(Composant).filter(Composant.id_piece_externe == p.id_piece_externe).count()
    return PieceExterneResponse(
        id_piece_externe=p.id_piece_externe,
        code_produit=p.code_produit,
        nom=p.nom,
        description=p.description,
        fournisseur=p.fournisseur,
        prix_unitaire=float(p.prix_unitaire) if p.prix_unitaire else None,
        nb_composants=nb,
    )


@router.get("", response_model=PieceExterneListResponse)
def list_pieces(
    search: Optional[str] = Query(None),
    page:   int           = Query(1, ge=1),
    limit:  int           = Query(100, ge=1, le=500),
    db:     Session       = Depends(get_db),
    _user                 = Depends(require_permission("external_parts")),
):
    q = db.query(PieceExterne)
    if search:
        like = f"%{search}%"
        q = q.filter(PieceExterne.nom.ilike(like) | PieceExterne.code_produit.ilike(like))
    q = q.order_by(PieceExterne.nom)
    total = q.count()
    items = q.offset((page-1)*limit).limit(limit).all()
    pages = max(1, (total + limit - 1) // limit)
    return PieceExterneListResponse(
        items=[_to_response(p, db) for p in items],
        total=total, page=page, pages=pages,
    )


@router.get("/{id_piece_externe}", response_model=PieceExterneResponse)
def get_piece(
    id_piece_externe: int,
    db:               Session = Depends(get_db),
    _user                     = Depends(require_permission("external_parts")),
):
    p = db.get(PieceExterne, id_piece_externe)
    if not p:
        raise HTTPException(404, "External part not found")
    return _to_response(p, db)


@router.post("", response_model=PieceExterneResponse, status_code=201)
def create_piece(
    payload: PieceExterneCreate,
    db:      Session = Depends(get_db),
    _user            = Depends(require_permission("external_parts")),
):
    p = PieceExterne(**payload.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return _to_response(p, db)


@router.put("/{id_piece_externe}", response_model=PieceExterneResponse)
def update_piece(
    id_piece_externe: int,
    payload:          PieceExterneUpdate,
    db:               Session = Depends(get_db),
    _user                     = Depends(require_permission("external_parts")),
):
    p = db.get(PieceExterne, id_piece_externe)
    if not p:
        raise HTTPException(404, "External part not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(p, field, value)
    db.commit()
    db.refresh(p)
    return _to_response(p, db)


@router.delete("/{id_piece_externe}", status_code=204)
def delete_piece(
    id_piece_externe: int,
    db:               Session = Depends(get_db),
    _user                     = Depends(require_permission("external_parts")),
):
    p = db.get(PieceExterne, id_piece_externe)
    if not p:
        raise HTTPException(404, "External part not found")
    nb = db.query(Composant).filter(Composant.id_piece_externe == id_piece_externe).count()
    if nb:
        raise HTTPException(409, f"Cannot delete: used by {nb} component(s)")
    db.delete(p)
    db.commit()
