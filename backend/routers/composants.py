"""
backend/routers/composants.py
-----------------------------
CRUD Composants :
  GET    /composants          → liste paginée + recherche
  GET    /composants/{id}     → détail
  POST   /composants          → création
  PUT    /composants/{id}     → modification
  DELETE /composants/{id}     → suppression (si pas d'OF actif)
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import require_permission
from database import get_db
from models import Composant, OrdreFabrication

router = APIRouter(prefix="/composants", tags=["Composants"])


# ─── Schémas ────────────────────────────────────────────────────────────────

class ComposantBase(BaseModel):
    reference:        Optional[str]   = None
    nom:              str
    type:             Optional[str]   = None
    description:      Optional[str]   = None
    plan_url:         Optional[str]   = None
    id_matiere_brut:  Optional[int]   = None
    forme_brut:       Optional[str]   = None
    brut_diametre:    Optional[float] = None
    brut_diam_ext:    Optional[float] = None
    brut_diam_int:    Optional[float] = None
    brut_longueur:    Optional[float] = None
    brut_largeur:     Optional[float] = None
    brut_hauteur:     Optional[float] = None
    brut_epaisseur:   Optional[float] = None
    id_service:       Optional[int]   = None
    id_piece_externe: Optional[int]   = None


class ComposantCreate(ComposantBase):
    pass


class ComposantUpdate(ComposantBase):
    nom: Optional[str] = None  # nom optionnel pour update partiel


class ComposantResponse(BaseModel):
    id_composant:     int
    reference:        Optional[str]
    nom:              str
    type:             Optional[str]
    description:      Optional[str]
    plan_url:         Optional[str]
    prix_revient:     Optional[float]
    id_matiere_brut:  Optional[int]
    matiere_nom:      Optional[str]
    forme_brut:       Optional[str]
    brut_diametre:    Optional[float]
    brut_diam_ext:    Optional[float]
    brut_diam_int:    Optional[float]
    brut_longueur:    Optional[float]
    brut_largeur:     Optional[float]
    brut_hauteur:     Optional[float]
    brut_epaisseur:   Optional[float]
    id_service:       Optional[int]
    service_nom:      Optional[str]
    id_piece_externe: Optional[int]
    piece_externe_nom: Optional[str]
    nb_gammes:        int

    class Config:
        from_attributes = True


class ComposantListResponse(BaseModel):
    items:  list[ComposantResponse]
    total:  int
    page:   int
    pages:  int


# ─── Helper ──────────────────────────────────────────────────────────────────

def _to_response(c: Composant, db: Session) -> ComposantResponse:
    return ComposantResponse(
        id_composant=c.id_composant,
        reference=c.reference,
        nom=c.nom,
        type=c.type,
        description=c.description,
        plan_url=c.plan_url,
        prix_revient=float(c.prix_revient) if c.prix_revient else None,
        id_matiere_brut=c.id_matiere_brut,
        matiere_nom=c.matiere_brut.nom if c.matiere_brut else None,
        forme_brut=c.forme_brut,
        brut_diametre=float(c.brut_diametre) if c.brut_diametre else None,
        brut_diam_ext=float(c.brut_diam_ext) if c.brut_diam_ext else None,
        brut_diam_int=float(c.brut_diam_int) if c.brut_diam_int else None,
        brut_longueur=float(c.brut_longueur) if c.brut_longueur else None,
        brut_largeur=float(c.brut_largeur) if c.brut_largeur else None,
        brut_hauteur=float(c.brut_hauteur) if c.brut_hauteur else None,
        brut_epaisseur=float(c.brut_epaisseur) if c.brut_epaisseur else None,
        id_service=c.id_service,
        service_nom=c.service.nom if c.service else None,
        id_piece_externe=c.id_piece_externe,
        piece_externe_nom=c.piece_externe.nom if c.piece_externe else None,
        nb_gammes=len(c.gammes),
    )


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("", response_model=ComposantListResponse)
def liste_composants(
    search: Optional[str] = Query(None, description="Recherche nom ou référence"),
    page:   int           = Query(1, ge=1),
    limit:  int           = Query(50, ge=1, le=200),
    db:     Session       = Depends(get_db),
    _user                 = Depends(require_permission("components")),
):
    """Liste paginée des composants avec recherche optionnelle."""
    q = db.query(Composant)
    if search:
        like = f"%{search}%"
        q = q.filter(
            Composant.nom.ilike(like) | Composant.reference.ilike(like)
        )
    q = q.order_by(Composant.nom)

    total  = q.count()
    offset = (page - 1) * limit
    items  = q.offset(offset).limit(limit).all()
    pages  = max(1, (total + limit - 1) // limit)

    return ComposantListResponse(
        items=[_to_response(c, db) for c in items],
        total=total,
        page=page,
        pages=pages,
    )


@router.get("/{id_composant}", response_model=ComposantResponse)
def get_composant(
    id_composant: int,
    db:           Session = Depends(get_db),
    _user                 = Depends(require_permission("components")),
):
    """Détail d'un composant."""
    c = db.get(Composant, id_composant)
    if not c:
        raise HTTPException(status_code=404, detail="Composant introuvable")
    return _to_response(c, db)


@router.post("", response_model=ComposantResponse, status_code=201)
def creer_composant(
    payload: ComposantCreate,
    db:      Session = Depends(get_db),
    _user            = Depends(require_permission("components")),
):
    """Crée un nouveau composant."""
    c = Composant(**payload.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return _to_response(c, db)


@router.put("/{id_composant}", response_model=ComposantResponse)
def modifier_composant(
    id_composant: int,
    payload:      ComposantUpdate,
    db:           Session = Depends(get_db),
    _user                 = Depends(require_permission("components")),
):
    """Modifie un composant existant."""
    c = db.get(Composant, id_composant)
    if not c:
        raise HTTPException(status_code=404, detail="Composant introuvable")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(c, field, value)

    db.commit()
    db.refresh(c)
    return _to_response(c, db)


@router.delete("/{id_composant}", status_code=204)
def supprimer_composant(
    id_composant: int,
    db:           Session = Depends(get_db),
    _user                 = Depends(require_permission("components")),
):
    """
    Supprime un composant.
    Refusé si des OFs actifs (non terminés/annulés) y sont liés.
    """
    c = db.get(Composant, id_composant)
    if not c:
        raise HTTPException(status_code=404, detail="Composant introuvable")

    ofs_actifs = db.query(OrdreFabrication).filter(
        OrdreFabrication.id_composant == id_composant,
        OrdreFabrication.statut.notin_(["termine", "annule", "rebute"])
    ).count()

    if ofs_actifs:
        raise HTTPException(
            status_code=409,
            detail=f"Impossible de supprimer : {ofs_actifs} ordre(s) de fabrication actif(s)"
        )

    db.delete(c)
    db.commit()
