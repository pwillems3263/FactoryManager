"""
backend/routers/commandes.py
-----------------------------
CRUD Orders (Commande + LigneCommande)
"""

from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import require_permission, get_db
from models import Commande, LigneCommande, Assemblage
from services.of_service import generer_of_depuis_ligne
from services.planning_service import planifier_of_assemblage
from services.cout_service import recalculer_assemblage

router = APIRouter(prefix="/orders", tags=["Orders"])

STATUT_LABELS = {
    "planifiee":  "Planned",
    "en_cours":   "In Progress",
    "terminee":   "Completed",
    "annulee":    "Cancelled",
    "on_hold":    "On Hold",
    "released":   "Released",
    "completed":  "Completed",
    "cancelled":  "Cancelled",
}

STATUT_COLORS = {
    "planifiee": "#e67e22",
    "en_cours":  "#8e44ad",
    "terminee":  "#27ae60",
    "annulee":   "#95a5a6",
    "on_hold":   "#e67e22",
    "released":  "#3498db",
    "completed": "#27ae60",
    "cancelled": "#95a5a6",
}


# ─── Schemas ─────────────────────────────────────────────────────────────────

class CommandeBase(BaseModel):
    date_commande:  date
    client:         str
    numero_externe: Optional[str] = None
    date_livraison: Optional[date] = None
    statut:         str = "planifiee"


class CommandeCreate(CommandeBase):
    pass


class CommandeUpdate(BaseModel):
    date_commande:  Optional[date] = None
    client:         Optional[str]  = None
    numero_externe: Optional[str]  = None
    date_livraison: Optional[date] = None
    statut:         Optional[str]  = None


class LigneResponse(BaseModel):
    id_ligne:      int
    id_commande:   int
    id_assemblage: int
    assemblage_nom: str
    quantite:      float
    code_ligne:    Optional[str]
    statut:        str
    statut_label:  str
    statut_color:  str
    prix_revient_snapshot: Optional[float]

    class Config:
        from_attributes = True


class CommandeResponse(BaseModel):
    id_commande:    int
    code_commande:  Optional[str]
    numero_externe: Optional[str]
    client:         str
    date_commande:  str
    date_livraison: Optional[str]
    statut:         str
    statut_label:   str
    statut_color:   str
    nb_lignes:      int
    lignes:         list[LigneResponse] = []

    class Config:
        from_attributes = True


class CommandeListResponse(BaseModel):
    items: list[CommandeResponse]
    total: int
    page:  int
    pages: int


class LigneCreate(BaseModel):
    id_assemblage: int
    quantite:      float


class LigneUpdate(BaseModel):
    quantite: Optional[float] = None
    statut:   Optional[str]   = None


class ReleaseResponse(BaseModel):
    ligne:   LigneResponse
    nb_ofs:  int
    message: str


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _ligne_to_response(l: LigneCommande, db: Session) -> LigneResponse:
    asm = db.get(Assemblage, l.id_assemblage)
    return LigneResponse(
        id_ligne=l.id_ligne,
        id_commande=l.id_commande,
        id_assemblage=l.id_assemblage,
        assemblage_nom=asm.nom if asm else "—",
        quantite=float(l.quantite),
        code_ligne=l.code_ligne,
        statut=l.statut,
        statut_label=STATUT_LABELS.get(l.statut, l.statut),
        statut_color=STATUT_COLORS.get(l.statut, "#95a5a6"),
        prix_revient_snapshot=float(l.prix_revient_snapshot) if l.prix_revient_snapshot else None,
    )


def _to_response(c: Commande, db: Session, with_lignes: bool = False) -> CommandeResponse:
    lignes = [_ligne_to_response(l, db) for l in c.lignes] if with_lignes else []
    return CommandeResponse(
        id_commande=c.id_commande,
        code_commande=c.code_commande,
        numero_externe=c.numero_externe,
        client=c.client,
        date_commande=str(c.date_commande),
        date_livraison=str(c.date_livraison) if c.date_livraison else None,
        statut=c.statut,
        statut_label=STATUT_LABELS.get(c.statut, c.statut),
        statut_color=STATUT_COLORS.get(c.statut, "#95a5a6"),
        nb_lignes=len(c.lignes),
        lignes=lignes,
    )


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("", response_model=CommandeListResponse)
def list_orders(
    search: Optional[str] = Query(None),
    statut: Optional[str] = Query(None),
    page:   int           = Query(1, ge=1),
    limit:  int           = Query(50, ge=1, le=200),
    db:     Session       = Depends(get_db),
    _user                 = Depends(require_permission("orders")),
):
    q = db.query(Commande)
    if search:
        like = f"%{search}%"
        q = q.filter(
            Commande.client.ilike(like) |
            Commande.code_commande.ilike(like) |
            Commande.numero_externe.ilike(like)
        )
    if statut:
        q = q.filter(Commande.statut == statut)
    q = q.order_by(Commande.date_commande.desc())
    total = q.count()
    items = q.offset((page-1)*limit).limit(limit).all()
    pages = max(1, (total + limit - 1) // limit)
    return CommandeListResponse(
        items=[_to_response(c, db) for c in items],
        total=total, page=page, pages=pages,
    )


@router.get("/{id_commande}", response_model=CommandeResponse)
def get_order(id_commande: int, db: Session = Depends(get_db),
              _user=Depends(require_permission("orders"))):
    c = db.get(Commande, id_commande)
    if not c:
        raise HTTPException(404, "Order not found")
    return _to_response(c, db, with_lignes=True)


@router.post("", response_model=CommandeResponse, status_code=201)
def create_order(payload: CommandeCreate, db: Session = Depends(get_db),
                 _user=Depends(require_permission("orders"))):
    c = Commande(**payload.model_dump())
    db.add(c); db.commit(); db.refresh(c)
    return _to_response(c, db, with_lignes=True)


@router.put("/{id_commande}", response_model=CommandeResponse)
def update_order(id_commande: int, payload: CommandeUpdate,
                 db: Session = Depends(get_db),
                 _user=Depends(require_permission("orders"))):
    c = db.get(Commande, id_commande)
    if not c:
        raise HTTPException(404, "Order not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(c, field, value)
    db.commit(); db.refresh(c)
    return _to_response(c, db, with_lignes=True)


@router.delete("/{id_commande}", status_code=204)
def delete_order(id_commande: int, db: Session = Depends(get_db),
                 _user=Depends(require_permission("orders"))):
    c = db.get(Commande, id_commande)
    if not c:
        raise HTTPException(404, "Order not found")
    active = [l for l in c.lignes if l.statut in ("released", "completed")]
    if active:
        raise HTTPException(409, f"Cannot delete: {len(active)} active line(s)")
    db.delete(c); db.commit()


# ─── Order Lines ─────────────────────────────────────────────────────────────

@router.post("/{id_commande}/lines", response_model=LigneResponse, status_code=201)
def add_line(id_commande: int, payload: LigneCreate,
             db: Session = Depends(get_db),
             _user=Depends(require_permission("orders"))):
    c = db.get(Commande, id_commande)
    if not c:
        raise HTTPException(404, "Order not found")
    if not db.get(Assemblage, payload.id_assemblage):
        raise HTTPException(404, "Assembly not found")
    l = LigneCommande(
        id_commande=id_commande,
        id_assemblage=payload.id_assemblage,
        quantite=payload.quantite,
        statut="on_hold",
    )
    db.add(l); db.commit(); db.refresh(l)
    return _ligne_to_response(l, db)


@router.post("/{id_commande}/lines/{id_ligne}/release", response_model=ReleaseResponse)
def release_line(id_commande: int, id_ligne: int,
                  db: Session = Depends(get_db),
                  _user=Depends(require_permission("orders"))):
    """
    Release a line: generates the OFAssemblage + component OFs from the BOM,
    schedules them at the earliest possible date, snapshots the cost price,
    and marks the line as 'released'.
    Mirrors the desktop app's "Release Line" action.
    """
    ligne = db.get(LigneCommande, id_ligne)
    if not ligne or ligne.id_commande != id_commande:
        raise HTTPException(404, "Line not found")
    if ligne.statut != "on_hold":
        raise HTTPException(409, f"Line already '{ligne.statut}', cannot release again")

    try:
        # 1. Generate the assembly OF + component OFs from the BOM
        of_assemblage = generer_of_depuis_ligne(db, id_ligne)

        # 2. Schedule all component OFs at the earliest date
        planifier_of_assemblage(session=db, id_of_assemblage=of_assemblage.id_of_assemblage)

        # 3. Snapshot the cost price
        ligne = db.get(LigneCommande, id_ligne)
        if ligne and ligne.assemblage:
            prix = recalculer_assemblage(db, ligne.id_assemblage)
            ligne.prix_revient_snapshot = prix

        ligne.statut = "released"
        db.commit()
        db.refresh(ligne)
    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Failed to release line: {e}")

    nb_ofs = len(of_assemblage.ordres_fabrication) if of_assemblage else 0
    return ReleaseResponse(
        ligne=_ligne_to_response(ligne, db),
        nb_ofs=nb_ofs,
        message="Production Orders generated and scheduled.",
    )


@router.put("/{id_commande}/lines/{id_ligne}", response_model=LigneResponse)
def update_line(id_commande: int, id_ligne: int, payload: LigneUpdate,
                db: Session = Depends(get_db),
                _user=Depends(require_permission("orders"))):
    l = db.get(LigneCommande, id_ligne)
    if not l or l.id_commande != id_commande:
        raise HTTPException(404, "Line not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(l, field, value)
    db.commit(); db.refresh(l)
    return _ligne_to_response(l, db)


@router.delete("/{id_commande}/lines/{id_ligne}", status_code=204)
def delete_line(id_commande: int, id_ligne: int,
                db: Session = Depends(get_db),
                _user=Depends(require_permission("orders"))):
    l = db.get(LigneCommande, id_ligne)
    if not l or l.id_commande != id_commande:
        raise HTTPException(404, "Line not found")
    if l.statut in ("released", "completed"):
        raise HTTPException(409, "Cannot delete a released or completed line")
    db.delete(l); db.commit()
