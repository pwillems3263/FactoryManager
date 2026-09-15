"""
backend/routers/assemblages.py
------------------------------
CRUD Assemblies + Bill of Materials (Nomenclature)
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import require_permission, get_db
from models import Assemblage, Nomenclature, Composant, Service, PieceExterne
from services.cout_service import recalculer_assemblage

router = APIRouter(prefix="/assemblies", tags=["Assemblies"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class AssemblageBase(BaseModel):
    nom:         str
    reference:   Optional[str]   = None
    description: Optional[str]   = None
    plan_url:    Optional[str]   = None


class AssemblageCreate(AssemblageBase):
    pass


class AssemblageUpdate(BaseModel):
    nom:         Optional[str] = None
    reference:   Optional[str] = None
    description: Optional[str] = None
    plan_url:    Optional[str] = None


class AssemblageResponse(BaseModel):
    id_assemblage: int
    nom:           str
    reference:     Optional[str]
    description:   Optional[str]
    plan_url:      Optional[str]
    prix_revient:  Optional[float]
    nb_bom_items:  int

    class Config:
        from_attributes = True


class AssemblageListResponse(BaseModel):
    items: list[AssemblageResponse]
    total: int
    page:  int
    pages: int


class BOMItemResponse(BaseModel):
    id_nomenclature: int
    quantite:        float
    type_item:       str   # 'component' | 'service' | 'external_part'
    item_id:         int
    item_nom:        str
    item_reference:  Optional[str]
    item_prix:       Optional[float]


class BOMAddItem(BaseModel):
    quantite:        float
    id_composant:    Optional[int] = None
    id_service:      Optional[int] = None
    id_piece_externe: Optional[int] = None
    type_parent:     str = "assemblage"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _to_response(a: Assemblage, db: Session) -> AssemblageResponse:
    nb = db.query(Nomenclature).filter(
        Nomenclature.id_parent == a.id_assemblage,
        Nomenclature.type_parent == "assemblage"
    ).count()
    return AssemblageResponse(
        id_assemblage=a.id_assemblage,
        nom=a.nom,
        reference=a.reference,
        description=a.description,
        plan_url=a.plan_url,
        prix_revient=float(a.prix_revient) if a.prix_revient else None,
        nb_bom_items=nb,
    )


def _bom_item(n: Nomenclature, db: Session) -> BOMItemResponse:
    if n.id_composant:
        c = db.get(Composant, n.id_composant)
        return BOMItemResponse(
            id_nomenclature=n.id_nomenclature,
            quantite=float(n.quantite),
            type_item="component",
            item_id=n.id_composant,
            item_nom=c.nom if c else "—",
            item_reference=c.reference if c else None,
            item_prix=float(c.prix_revient) if c and c.prix_revient else None,
        )
    elif n.id_service:
        s = db.get(Service, n.id_service)
        return BOMItemResponse(
            id_nomenclature=n.id_nomenclature,
            quantite=float(n.quantite),
            type_item="service",
            item_id=n.id_service,
            item_nom=s.nom if s else "—",
            item_reference=s.code_produit if s else None,
            # Matches recalculer_assemblage(): fixed cost takes priority,
            # otherwise fall back to the hourly rate.
            item_prix=float(s.cout_fixe) if s and s.cout_fixe
                      else (float(s.cout_horaire) if s and s.cout_horaire else None),
        )
    elif n.id_piece_externe:
        p = db.get(PieceExterne, n.id_piece_externe)
        return BOMItemResponse(
            id_nomenclature=n.id_nomenclature,
            quantite=float(n.quantite),
            type_item="external_part",
            item_id=n.id_piece_externe,
            item_nom=p.nom if p else "—",
            item_reference=p.code_produit if p else None,
            item_prix=float(p.prix_unitaire) if p and p.prix_unitaire else None,
        )


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("", response_model=AssemblageListResponse)
def list_assemblies(
    search: Optional[str] = Query(None),
    page:   int           = Query(1, ge=1),
    limit:  int           = Query(50, ge=1, le=200),
    db:     Session       = Depends(get_db),
    _user                 = Depends(require_permission("assemblies")),
):
    q = db.query(Assemblage)
    if search:
        like = f"%{search}%"
        q = q.filter(Assemblage.nom.ilike(like) | Assemblage.reference.ilike(like))
    q = q.order_by(Assemblage.nom)
    total = q.count()
    items = q.offset((page-1)*limit).limit(limit).all()
    pages = max(1, (total + limit - 1) // limit)
    return AssemblageListResponse(
        items=[_to_response(a, db) for a in items],
        total=total, page=page, pages=pages,
    )


@router.get("/{id_assemblage}", response_model=AssemblageResponse)
def get_assembly(id_assemblage: int, db: Session = Depends(get_db),
                 _user=Depends(require_permission("assemblies"))):
    a = db.get(Assemblage, id_assemblage)
    if not a:
        raise HTTPException(404, "Assembly not found")
    return _to_response(a, db)


@router.post("/{id_assemblage}/recalculate", response_model=AssemblageResponse)
def recalculate_cost(id_assemblage: int, db: Session = Depends(get_db),
                      _user=Depends(require_permission("assemblies"))):
    """Force-recomputes the assembly's cost price from its current BOM."""
    a = db.get(Assemblage, id_assemblage)
    if not a:
        raise HTTPException(404, "Assembly not found")
    recalculer_assemblage(db, id_assemblage)
    db.commit()
    db.refresh(a)
    return _to_response(a, db)


@router.post("", response_model=AssemblageResponse, status_code=201)
def create_assembly(payload: AssemblageCreate, db: Session = Depends(get_db),
                    _user=Depends(require_permission("assemblies"))):
    if payload.reference and payload.reference.strip():
        existing = (
            db.query(Assemblage)
            .filter(Assemblage.reference.ilike(payload.reference.strip()))
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f'Reference "{payload.reference}" is already used by "{existing.nom}". '
                       f"Please change the reference."
            )
    a = Assemblage(**payload.model_dump())
    db.add(a); db.commit(); db.refresh(a)
    return _to_response(a, db)


@router.put("/{id_assemblage}", response_model=AssemblageResponse)
def update_assembly(id_assemblage: int, payload: AssemblageUpdate,
                    db: Session = Depends(get_db),
                    _user=Depends(require_permission("assemblies"))):
    a = db.get(Assemblage, id_assemblage)
    if not a:
        raise HTTPException(404, "Assembly not found")

    # Reference is immutable once created: assemblies may already be referenced
    # by orders (lignecommande) or nested BOMs, and changing it could silently
    # break those links. Any change to "reference" in the payload is ignored.
    update_data = payload.model_dump(exclude_unset=True)
    update_data.pop("reference", None)

    for field, value in update_data.items():
        setattr(a, field, value)
    db.commit(); db.refresh(a)
    return _to_response(a, db)


@router.delete("/{id_assemblage}", status_code=204)
def delete_assembly(id_assemblage: int, db: Session = Depends(get_db),
                    _user=Depends(require_permission("assemblies"))):
    a = db.get(Assemblage, id_assemblage)
    if not a:
        raise HTTPException(404, "Assembly not found")
    db.delete(a); db.commit()


# ─── BOM ─────────────────────────────────────────────────────────────────────

@router.get("/{id_assemblage}/bom", response_model=list[BOMItemResponse])
def get_bom(id_assemblage: int, db: Session = Depends(get_db),
            _user=Depends(require_permission("assemblies"))):
    items = db.query(Nomenclature).filter(
        Nomenclature.id_parent == id_assemblage,
        Nomenclature.type_parent == "assemblage"
    ).all()
    return [_bom_item(n, db) for n in items if _bom_item(n, db)]


@router.post("/{id_assemblage}/bom", response_model=BOMItemResponse, status_code=201)
def add_bom_item(id_assemblage: int, payload: BOMAddItem,
                 db: Session = Depends(get_db),
                 _user=Depends(require_permission("assemblies"))):
    if not db.get(Assemblage, id_assemblage):
        raise HTTPException(404, "Assembly not found")
    if not any([payload.id_composant, payload.id_service, payload.id_piece_externe]):
        raise HTTPException(400, "Must specify one of: id_composant, id_service, id_piece_externe")
    n = Nomenclature(
        id_parent=id_assemblage,
        type_parent="assemblage",
        quantite=payload.quantite,
        id_composant=payload.id_composant,
        id_service=payload.id_service,
        id_piece_externe=payload.id_piece_externe,
    )
    db.add(n); db.commit(); db.refresh(n)

    recalculer_assemblage(db, id_assemblage)
    db.commit()

    return _bom_item(n, db)


@router.delete("/{id_assemblage}/bom/{id_nomenclature}", status_code=204)
def remove_bom_item(id_assemblage: int, id_nomenclature: int,
                    db: Session = Depends(get_db),
                    _user=Depends(require_permission("assemblies"))):
    n = db.get(Nomenclature, id_nomenclature)
    if not n or n.id_parent != id_assemblage:
        raise HTTPException(404, "BOM item not found")
    db.delete(n); db.commit()

    recalculer_assemblage(db, id_assemblage)
    db.commit()
