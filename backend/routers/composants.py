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

from auth import require_permission, get_db
from models import Composant, OrdreFabrication, Gamme, Operation, Machine, Service, PieceExterne
from services.cout_service import recalculer_et_sauvegarder_composant, _recalculer_assemblages_du_composant

router = APIRouter(prefix="/composants", tags=["Composants"])


# ─── Schémas ────────────────────────────────────────────────────────────────

class ComposantBase(BaseModel):
    reference:        Optional[str]   = None
    nom:              str
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


# ─── Schémas Gamme / Operations (Manufacturing Routing) ─────────────────────

class OperationResponse(BaseModel):
    id_operation:      int
    ordre:             int
    description:       Optional[str]
    tps_preparation:   int
    tps_execution:     int
    plan_url:          Optional[str]
    id_machine:        Optional[int]
    machine_nom:       Optional[str]
    id_service:        Optional[int]
    service_nom:       Optional[str]
    id_piece_externe:  Optional[int]
    piece_externe_nom: Optional[str]

    class Config:
        from_attributes = True


class GammeResponse(BaseModel):
    id_gamme:     int
    id_composant: int
    version:      int
    active:       bool
    operations:   list[OperationResponse]


class OperationCreate(BaseModel):
    description:      Optional[str] = None
    tps_preparation:  int = 0
    tps_execution:    int = 0
    plan_url:         Optional[str] = None
    id_machine:       Optional[int] = None
    id_service:       Optional[int] = None
    id_piece_externe: Optional[int] = None
    ordre:            Optional[int] = None  # auto (max+1) si non fourni


class OperationUpdate(BaseModel):
    description:      Optional[str] = None
    tps_preparation:  Optional[int] = None
    tps_execution:    Optional[int] = None
    plan_url:         Optional[str] = None
    id_machine:       Optional[int] = None
    id_service:       Optional[int] = None
    id_piece_externe: Optional[int] = None


class MoveOperationRequest(BaseModel):
    direction: str  # "up" | "down"


# ─── Helper ──────────────────────────────────────────────────────────────────

def _to_response(c: Composant, db: Session) -> ComposantResponse:
    return ComposantResponse(
        id_composant=c.id_composant,
        reference=c.reference,
        nom=c.nom,
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
    if payload.reference and payload.reference.strip():
        existing = (
            db.query(Composant)
            .filter(Composant.reference.ilike(payload.reference.strip()))
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f'Reference "{payload.reference}" is already used by "{existing.nom}". '
                       f"Please change the reference."
            )
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

    # Reference is immutable once created: components may already be referenced
    # by assemblies, orders (OF) or BOMs, and changing it could silently break
    # those links. Any change to "reference" in the payload is ignored.
    update_data = payload.model_dump(exclude_unset=True)
    update_data.pop("reference", None)

    for field, value in update_data.items():
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


# ─── Manufacturing Routing (Gamme + Operations) ──────────────────────────────
# Mirrors the desktop app: routing is managed as part of the Component window,
# not as a separate module.

def _op_to_response(op: Operation) -> OperationResponse:
    return OperationResponse(
        id_operation=op.id_operation,
        ordre=op.ordre,
        description=op.description,
        tps_preparation=op.tps_preparation,
        tps_execution=op.tps_execution,
        plan_url=op.plan_url,
        id_machine=op.id_machine,
        machine_nom=op.machine.nom if op.machine else None,
        id_service=op.id_service,
        service_nom=op.service.nom if op.service else None,
        id_piece_externe=op.id_piece_externe,
        piece_externe_nom=op.piece_externe.nom if op.piece_externe else None,
    )


def _get_or_create_gamme(db: Session, id_composant: int) -> Gamme:
    gamme = db.query(Gamme).filter_by(id_composant=id_composant, active=True).first()
    if not gamme:
        gamme = Gamme(id_composant=id_composant, version=1, active=True)
        db.add(gamme)
        db.flush()
    return gamme


@router.get("/{id_composant}/gamme", response_model=GammeResponse)
def get_gamme(
    id_composant: int,
    db:           Session = Depends(get_db),
    _user                 = Depends(require_permission("components")),
):
    """Returns the active routing (gamme) for this component, with its steps in order."""
    if not db.get(Composant, id_composant):
        raise HTTPException(404, "Composant introuvable")

    gamme = db.query(Gamme).filter_by(id_composant=id_composant, active=True).first()
    if not gamme:
        return GammeResponse(id_gamme=0, id_composant=id_composant, version=0,
                              active=False, operations=[])

    ops = sorted(gamme.operations, key=lambda o: o.ordre)
    return GammeResponse(
        id_gamme=gamme.id_gamme, id_composant=id_composant,
        version=gamme.version, active=gamme.active,
        operations=[_op_to_response(o) for o in ops],
    )


@router.post("/{id_composant}/gamme/operations", response_model=OperationResponse, status_code=201)
def add_operation(
    id_composant: int,
    payload:      OperationCreate,
    db:           Session = Depends(get_db),
    _user                 = Depends(require_permission("components")),
):
    """Adds a manufacturing step to this component's active routing (creates the routing if needed)."""
    if not db.get(Composant, id_composant):
        raise HTTPException(404, "Composant introuvable")
    if payload.id_machine and not db.get(Machine, payload.id_machine):
        raise HTTPException(404, "Machine introuvable")
    if payload.id_service and not db.get(Service, payload.id_service):
        raise HTTPException(404, "Service introuvable")
    if payload.id_piece_externe and not db.get(PieceExterne, payload.id_piece_externe):
        raise HTTPException(404, "External part introuvable")

    gamme = _get_or_create_gamme(db, id_composant)

    ordre = payload.ordre
    if not ordre:
        ordre = (max((o.ordre for o in gamme.operations), default=0)) + 1

    op = Operation(
        id_gamme=gamme.id_gamme,
        id_machine=payload.id_machine,
        id_service=payload.id_service,
        id_piece_externe=payload.id_piece_externe,
        ordre=ordre,
        description=payload.description,
        tps_preparation=payload.tps_preparation,
        tps_execution=payload.tps_execution,
        plan_url=payload.plan_url,
    )
    db.add(op); db.commit(); db.refresh(op)

    # Mirrors desktop: recompute this component's cost price, then cascade
    # to any assemblies that use it.
    recalculer_et_sauvegarder_composant(db, id_composant)
    _recalculer_assemblages_du_composant(db, id_composant)
    db.commit()

    return _op_to_response(op)


@router.put("/{id_composant}/gamme/operations/{id_operation}", response_model=OperationResponse)
def update_operation(
    id_composant: int,
    id_operation: int,
    payload:      OperationUpdate,
    db:           Session = Depends(get_db),
    _user                 = Depends(require_permission("components")),
):
    op = db.get(Operation, id_operation)
    if not op or op.gamme.id_composant != id_composant:
        raise HTTPException(404, "Step not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(op, field, value)

    db.commit(); db.refresh(op)

    recalculer_et_sauvegarder_composant(db, id_composant)
    _recalculer_assemblages_du_composant(db, id_composant)
    db.commit()

    return _op_to_response(op)


@router.delete("/{id_composant}/gamme/operations/{id_operation}", status_code=204)
def delete_operation(
    id_composant: int,
    id_operation: int,
    db:           Session = Depends(get_db),
    _user                 = Depends(require_permission("components")),
):
    op = db.get(Operation, id_operation)
    if not op or op.gamme.id_composant != id_composant:
        raise HTTPException(404, "Step not found")
    id_gamme = op.id_gamme
    db.delete(op); db.commit()

    # Renumber remaining steps so "ordre" stays contiguous (1, 2, 3...)
    # after the deleted step's gap.
    remaining = (
        db.query(Operation)
        .filter(Operation.id_gamme == id_gamme)
        .order_by(Operation.ordre)
        .all()
    )
    for i, o in enumerate(remaining, start=1):
        o.ordre = i
    db.commit()

    recalculer_et_sauvegarder_composant(db, id_composant)
    _recalculer_assemblages_du_composant(db, id_composant)
    db.commit()


@router.put("/{id_composant}/gamme/operations/{id_operation}/move", response_model=list[OperationResponse])
def move_operation(
    id_composant: int,
    id_operation: int,
    payload:      MoveOperationRequest,
    db:           Session = Depends(get_db),
    _user                 = Depends(require_permission("components")),
):
    """Swaps this step's order with its previous ('up') or next ('down') neighbour."""
    op = db.get(Operation, id_operation)
    if not op or op.gamme.id_composant != id_composant:
        raise HTTPException(404, "Step not found")

    ops = sorted(op.gamme.operations, key=lambda o: o.ordre)
    idx = next(i for i, o in enumerate(ops) if o.id_operation == id_operation)

    if payload.direction == "up" and idx > 0:
        ops[idx].ordre, ops[idx-1].ordre = ops[idx-1].ordre, ops[idx].ordre
    elif payload.direction == "down" and idx < len(ops) - 1:
        ops[idx].ordre, ops[idx+1].ordre = ops[idx+1].ordre, ops[idx].ordre
    else:
        raise HTTPException(400, "Cannot move step in that direction")

    db.commit()
    ops_sorted = sorted(op.gamme.operations, key=lambda o: o.ordre)
    return [_op_to_response(o) for o in ops_sorted]
