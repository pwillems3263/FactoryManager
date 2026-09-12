"""
backend/routers/of.py
----------------------
Work Orders (OFAssemblage + OrdreFabrication + OperationPlanifiee)
  GET  /work-orders              → list OFAssemblage
  GET  /work-orders/{id}         → detail with child OFs + operations
  PUT  /work-orders/{id}         → update priority/status
  GET  /work-orders/{id}/ops     → list planned operations
  PUT  /work-orders/{id}/ops/{op_id} → update operation (machine, dates)
"""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import require_permission, get_db
from models import OFAssemblage, OrdreFabrication, OperationPlanifiee, LigneCommande

router = APIRouter(prefix="/work-orders", tags=["Work Orders"])

STATUT_LABELS = {
    "a_planifier": "To Schedule",
    "planifie":    "Planned",
    "en_cours":    "In Progress",
    "termine":     "Completed",
    "terminee":    "Completed",
    "annule":      "Cancelled",
    "rebutee":     "Scrapped",
}

STATUT_COLORS = {
    "a_planifier": "#e67e22",
    "planifie":    "#3498db",
    "en_cours":    "#8e44ad",
    "termine":     "#27ae60",
    "terminee":    "#27ae60",
    "annule":      "#95a5a6",
    "rebutee":     "#e74c3c",
}

PRIORITY_LABELS = {1: "Urgent", 2: "High", 3: "Elevated", 4: "Elevated", 5: "Normal"}
PRIORITY_COLORS = {1: "#e74c3c", 2: "#e67e22", 3: "#f39c12", 4: "#f39c12", 5: "#27ae60"}


# ─── Schemas ─────────────────────────────────────────────────────────────────

class OperationResponse(BaseModel):
    id_op:           int
    id_of:           int
    ordre:           int
    nom_operation:   str
    machine_nom:     Optional[str]
    duree_prevue_h:  Optional[float]
    date_debut:      Optional[str]
    date_fin:        Optional[str]
    statut:          str
    statut_label:    str
    statut_color:    str

    class Config:
        from_attributes = True


class OFResponse(BaseModel):
    id_of:           int
    code_of:         Optional[str]
    composant_nom:   str
    composant_ref:   Optional[str]
    quantite:        float
    type_of:         str
    statut:          str
    statut_label:    str
    statut_color:    str
    date_lancement:  Optional[str]
    date_fin_prevue: Optional[str]
    date_fin_reelle: Optional[str]
    prix_snapshot:   Optional[float]
    nb_ops:          int
    ops:             list[OperationResponse] = []

    class Config:
        from_attributes = True


class OFAssemblageResponse(BaseModel):
    id_of_assemblage: int
    assemblage_nom:   str
    client:           Optional[str]
    code_commande:    Optional[str]
    quantite:         float
    priorite:         int
    priorite_label:   str
    priorite_color:   str
    statut:           str
    statut_label:     str
    statut_color:     str
    date_lancement:   Optional[str]
    date_fin_prevue:  Optional[str]
    nb_ofs:           int
    ofs:              list[OFResponse] = []

    class Config:
        from_attributes = True


class OFAssemblageListResponse(BaseModel):
    items: list[OFAssemblageResponse]
    total: int
    page:  int
    pages: int


class OFAssemblageUpdate(BaseModel):
    priorite: Optional[int] = None
    statut:   Optional[str] = None


class OperationUpdate(BaseModel):
    id_machine:     Optional[int]      = None
    date_debut:     Optional[datetime] = None
    date_fin:       Optional[datetime] = None
    statut:         Optional[str]      = None


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _op_to_response(op: OperationPlanifiee) -> OperationResponse:
    return OperationResponse(
        id_op=op.id_op,
        id_of=op.id_of,
        ordre=op.ordre,
        nom_operation=op.nom_operation or f"Operation {op.ordre}",
        machine_nom=op.machine.nom if op.machine else None,
        duree_prevue_h=float(op.duree_prevue_h) if op.duree_prevue_h else None,
        date_debut=str(op.date_debut)[:16] if op.date_debut else None,
        date_fin=str(op.date_fin)[:16] if op.date_fin else None,
        statut=op.statut,
        statut_label=STATUT_LABELS.get(op.statut, op.statut),
        statut_color=STATUT_COLORS.get(op.statut, "#95a5a6"),
    )


def _of_to_response(of: OrdreFabrication, with_ops: bool = False) -> OFResponse:
    ops = [_op_to_response(op) for op in
           sorted(of.operations_planifiees, key=lambda o: o.ordre)] if with_ops else []
    return OFResponse(
        id_of=of.id_of,
        code_of=of.code_of,
        composant_nom=of.composant.nom if of.composant else "—",
        composant_ref=of.composant.reference if of.composant else None,
        quantite=float(of.quantite),
        type_of=of.type_of,
        statut=of.statut,
        statut_label=STATUT_LABELS.get(of.statut, of.statut),
        statut_color=STATUT_COLORS.get(of.statut, "#95a5a6"),
        date_lancement=str(of.date_lancement)[:16] if of.date_lancement else None,
        date_fin_prevue=str(of.date_fin_prevue)[:16] if of.date_fin_prevue else None,
        date_fin_reelle=str(of.date_fin_reelle)[:16] if of.date_fin_reelle else None,
        prix_snapshot=float(of.prix_revient_snapshot) if of.prix_revient_snapshot else None,
        nb_ops=len(of.operations_planifiees),
        ops=ops,
    )


def _ofa_to_response(ofa: OFAssemblage, with_ofs: bool = False) -> OFAssemblageResponse:
    # Get client/code from order line
    client = None
    code_commande = None
    if ofa.ligne_commande and ofa.ligne_commande.commande:
        client = ofa.ligne_commande.commande.client
        code_commande = ofa.ligne_commande.commande.code_commande

    ofs = [_of_to_response(of, with_ops=with_ofs)
           for of in ofa.ordres_fabrication] if with_ofs else []

    return OFAssemblageResponse(
        id_of_assemblage=ofa.id_of_assemblage,
        assemblage_nom=ofa.assemblage.nom if ofa.assemblage else "—",
        client=client,
        code_commande=code_commande,
        quantite=float(ofa.quantite),
        priorite=ofa.priorite,
        priorite_label=PRIORITY_LABELS.get(ofa.priorite, "Normal"),
        priorite_color=PRIORITY_COLORS.get(ofa.priorite, "#27ae60"),
        statut=ofa.statut,
        statut_label=STATUT_LABELS.get(ofa.statut, ofa.statut),
        statut_color=STATUT_COLORS.get(ofa.statut, "#95a5a6"),
        date_lancement=str(ofa.date_lancement)[:16] if ofa.date_lancement else None,
        date_fin_prevue=str(ofa.date_fin_prevue)[:16] if ofa.date_fin_prevue else None,
        nb_ofs=len(ofa.ordres_fabrication),
        ofs=ofs,
    )


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("", response_model=OFAssemblageListResponse)
def list_work_orders(
    search:  Optional[str] = Query(None),
    statut:  Optional[str] = Query(None),
    priorite: Optional[int] = Query(None),
    page:    int            = Query(1, ge=1),
    limit:   int            = Query(50, ge=1, le=200),
    db:      Session        = Depends(get_db),
    _user                   = Depends(require_permission("work_orders")),
):
    q = db.query(OFAssemblage)
    if statut:
        q = q.filter(OFAssemblage.statut == statut)
    if priorite:
        q = q.filter(OFAssemblage.priorite == priorite)
    q = q.order_by(OFAssemblage.priorite, OFAssemblage.date_fin_prevue)
    total = q.count()
    items = q.offset((page-1)*limit).limit(limit).all()
    pages = max(1, (total + limit - 1) // limit)

    # Filter by assembly name if search
    if search:
        items = [i for i in items if search.lower() in (i.assemblage.nom if i.assemblage else "").lower()]

    return OFAssemblageListResponse(
        items=[_ofa_to_response(i) for i in items],
        total=total, page=page, pages=pages,
    )


@router.get("/{id_of_assemblage}", response_model=OFAssemblageResponse)
def get_work_order(
    id_of_assemblage: int,
    db:               Session = Depends(get_db),
    _user                     = Depends(require_permission("work_orders")),
):
    ofa = db.get(OFAssemblage, id_of_assemblage)
    if not ofa:
        raise HTTPException(404, "Work order not found")
    return _ofa_to_response(ofa, with_ofs=True)


@router.put("/{id_of_assemblage}", response_model=OFAssemblageResponse)
def update_work_order(
    id_of_assemblage: int,
    payload:          OFAssemblageUpdate,
    db:               Session = Depends(get_db),
    _user                     = Depends(require_permission("work_orders")),
):
    ofa = db.get(OFAssemblage, id_of_assemblage)
    if not ofa:
        raise HTTPException(404, "Work order not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(ofa, field, value)
    db.commit(); db.refresh(ofa)
    return _ofa_to_response(ofa, with_ofs=True)


@router.get("/{id_of_assemblage}/ops", response_model=list[OperationResponse])
def list_operations(
    id_of_assemblage: int,
    db:               Session = Depends(get_db),
    _user                     = Depends(require_permission("work_orders")),
):
    ofa = db.get(OFAssemblage, id_of_assemblage)
    if not ofa:
        raise HTTPException(404, "Work order not found")
    ops = []
    for of in ofa.ordres_fabrication:
        ops.extend(of.operations_planifiees)
    ops.sort(key=lambda o: (o.id_of, o.ordre))
    return [_op_to_response(op) for op in ops]


@router.put("/{id_of_assemblage}/ops/{id_op}", response_model=OperationResponse)
def update_operation(
    id_of_assemblage: int,
    id_op:            int,
    payload:          OperationUpdate,
    db:               Session = Depends(get_db),
    _user                     = Depends(require_permission("work_orders")),
):
    op = db.get(OperationPlanifiee, id_op)
    if not op:
        raise HTTPException(404, "Operation not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(op, field, value)
    db.commit(); db.refresh(op)
    return _op_to_response(op)
