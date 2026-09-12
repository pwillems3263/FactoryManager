"""
backend/routers/matieres.py
---------------------------
CRUD Raw Materials (MatierePremiere) :
  GET    /matieres       → list
  GET    /matieres/{id}  → detail
  POST   /matieres       → create
  PUT    /matieres/{id}  → update
  DELETE /matieres/{id}  → delete (if not used by active components)
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import require_permission, get_db
from models import MatierePremiere, Composant

router = APIRouter(prefix="/matieres", tags=["Raw Materials"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class MatiereBase(BaseModel):
    nom:             str
    unite:           str
    stock_actuel:    float = 0
    poids_volumique: Optional[float] = None
    prix_au_kg:      Optional[float] = None


class MatiereCreate(MatiereBase):
    pass


class MatiereUpdate(BaseModel):
    nom:             Optional[str]   = None
    unite:           Optional[str]   = None
    stock_actuel:    Optional[float] = None
    poids_volumique: Optional[float] = None
    prix_au_kg:      Optional[float] = None


class MatiereResponse(BaseModel):
    id_matiere:      int
    nom:             str
    unite:           str
    stock_actuel:    float
    poids_volumique: Optional[float]
    prix_au_kg:      Optional[float]
    nb_composants:   int

    class Config:
        from_attributes = True


class MatiereListResponse(BaseModel):
    items: list[MatiereResponse]
    total: int
    page:  int
    pages: int


# ─── Helper ──────────────────────────────────────────────────────────────────

def _to_response(m: MatierePremiere, db: Session) -> MatiereResponse:
    nb = db.query(Composant).filter(Composant.id_matiere_brut == m.id_matiere).count()
    return MatiereResponse(
        id_matiere=m.id_matiere,
        nom=m.nom,
        unite=m.unite,
        stock_actuel=float(m.stock_actuel),
        poids_volumique=float(m.poids_volumique) if m.poids_volumique else None,
        prix_au_kg=float(m.prix_au_kg) if m.prix_au_kg else None,
        nb_composants=nb,
    )


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("", response_model=MatiereListResponse)
def list_matieres(
    search: Optional[str] = Query(None),
    page:   int           = Query(1, ge=1),
    limit:  int           = Query(100, ge=1, le=500),
    db:     Session       = Depends(get_db),
    _user                 = Depends(require_permission("materials")),
):
    q = db.query(MatierePremiere)
    if search:
        q = q.filter(MatierePremiere.nom.ilike(f"%{search}%"))
    q = q.order_by(MatierePremiere.nom)
    total  = q.count()
    items  = q.offset((page-1)*limit).limit(limit).all()
    pages  = max(1, (total + limit - 1) // limit)
    return MatiereListResponse(
        items=[_to_response(m, db) for m in items],
        total=total, page=page, pages=pages,
    )


@router.get("/{id_matiere}", response_model=MatiereResponse)
def get_matiere(
    id_matiere: int,
    db:         Session = Depends(get_db),
    _user               = Depends(require_permission("materials")),
):
    m = db.get(MatierePremiere, id_matiere)
    if not m:
        raise HTTPException(404, "Raw material not found")
    return _to_response(m, db)


@router.post("", response_model=MatiereResponse, status_code=201)
def create_matiere(
    payload: MatiereCreate,
    db:      Session = Depends(get_db),
    _user            = Depends(require_permission("materials")),
):
    m = MatierePremiere(**payload.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    return _to_response(m, db)


@router.put("/{id_matiere}", response_model=MatiereResponse)
def update_matiere(
    id_matiere: int,
    payload:    MatiereUpdate,
    db:         Session = Depends(get_db),
    _user               = Depends(require_permission("materials")),
):
    m = db.get(MatierePremiere, id_matiere)
    if not m:
        raise HTTPException(404, "Raw material not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(m, field, value)
    db.commit()
    db.refresh(m)
    return _to_response(m, db)


@router.delete("/{id_matiere}", status_code=204)
def delete_matiere(
    id_matiere: int,
    db:         Session = Depends(get_db),
    _user               = Depends(require_permission("materials")),
):
    m = db.get(MatierePremiere, id_matiere)
    if not m:
        raise HTTPException(404, "Raw material not found")
    nb = db.query(Composant).filter(Composant.id_matiere_brut == id_matiere).count()
    if nb:
        raise HTTPException(409, f"Cannot delete: used by {nb} component(s)")
    db.delete(m)
    db.commit()
