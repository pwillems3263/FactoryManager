"""
backend/routers/production_track.py
-------------------------------------
Production Tracking — read-only view of all manufacturing orders
with their operations, grouped by status.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import require_permission
from database import get_db
from models import OrdreFabrication, OFAssemblage, OperationPlanifiee

router = APIRouter(prefix="/production-track", tags=["Production Track"])

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


class OperationTrackResponse(BaseModel):
    id_op:          int
    ordre:          int
    nom_operation:  str
    machine_nom:    Optional[str]
    duree_prevue_h: Optional[float]
    date_debut:     Optional[str]
    date_fin:       Optional[str]
    statut:         str
    statut_label:   str
    statut_color:   str


class OFTrackResponse(BaseModel):
    id_of:           int
    code_of:         Optional[str]
    order_code:      Optional[str]
    client:          Optional[str]
    assembly_nom:    str
    composant_nom:   str
    quantite:        float
    date_lancement:  Optional[str]
    date_fin_prevue: Optional[str]
    date_fin_reelle: Optional[str]
    date_livraison:  Optional[str]
    statut:          str
    statut_label:    str
    statut_color:    str
    priorite:        int
    nb_ops_total:    int
    nb_ops_done:     int
    progress_pct:    int
    operations:      list[OperationTrackResponse] = []


class ProductionTrackResponse(BaseModel):
    items: list[OFTrackResponse]
    total: int
    page:  int
    pages: int


def _op_response(op: OperationPlanifiee) -> OperationTrackResponse:
    return OperationTrackResponse(
        id_op=op.id_op,
        ordre=op.ordre,
        nom_operation=op.nom_operation or f"Op {op.ordre}",
        machine_nom=op.machine.nom if op.machine else None,
        duree_prevue_h=float(op.duree_prevue_h) if op.duree_prevue_h else None,
        date_debut=str(op.date_debut)[:16] if op.date_debut else None,
        date_fin=str(op.date_fin)[:16] if op.date_fin else None,
        statut=op.statut,
        statut_label=STATUT_LABELS.get(op.statut, op.statut),
        statut_color=STATUT_COLORS.get(op.statut, "#95a5a6"),
    )


def _of_response(of: OrdreFabrication, with_ops: bool = False) -> OFTrackResponse:
    ofa = of.of_assemblage
    ligne = ofa.ligne_commande if ofa else None
    commande = ligne.commande if ligne else None

    ops = sorted(of.operations_planifiees, key=lambda o: o.ordre)
    nb_total = len(ops)
    nb_done  = sum(1 for o in ops if o.statut in ("terminee", "termine"))
    progress = int(nb_done / nb_total * 100) if nb_total else 0

    return OFTrackResponse(
        id_of=of.id_of,
        code_of=of.code_of,
        order_code=commande.code_commande if commande else None,
        client=commande.client if commande else None,
        assembly_nom=ofa.assemblage.nom if ofa and ofa.assemblage else "—",
        composant_nom=of.composant.nom if of.composant else "—",
        quantite=float(of.quantite),
        date_lancement=str(of.date_lancement)[:16] if of.date_lancement else None,
        date_fin_prevue=str(of.date_fin_prevue)[:16] if of.date_fin_prevue else None,
        date_fin_reelle=str(of.date_fin_reelle)[:16] if of.date_fin_reelle else None,
        date_livraison=str(commande.date_livraison) if commande and commande.date_livraison else None,
        statut=of.statut,
        statut_label=STATUT_LABELS.get(of.statut, of.statut),
        statut_color=STATUT_COLORS.get(of.statut, "#95a5a6"),
        priorite=ofa.priorite if ofa else 5,
        nb_ops_total=nb_total,
        nb_ops_done=nb_done,
        progress_pct=progress,
        operations=[_op_response(op) for op in ops] if with_ops else [],
    )


@router.get("", response_model=ProductionTrackResponse)
def list_production(
    statut:  Optional[str] = Query(None),
    search:  Optional[str] = Query(None),
    page:    int           = Query(1, ge=1),
    limit:   int           = Query(50, ge=1, le=200),
    db:      Session       = Depends(get_db),
    _user                  = Depends(require_permission("production_track")),
):
    q = db.query(OrdreFabrication)
    if statut:
        q = q.filter(OrdreFabrication.statut == statut)
    q = q.order_by(OrdreFabrication.date_fin_prevue)

    total = q.count()
    items = q.offset((page-1)*limit).limit(limit).all()
    pages = max(1, (total + limit - 1) // limit)

    if search:
        s = search.lower()
        items = [i for i in items if
                 s in (i.composant.nom if i.composant else "").lower() or
                 s in (i.code_of or "").lower()]

    return ProductionTrackResponse(
        items=[_of_response(of) for of in items],
        total=total, page=page, pages=pages,
    )


@router.get("/{id_of}", response_model=OFTrackResponse)
def get_of_detail(
    id_of: int,
    db:    Session = Depends(get_db),
    _user          = Depends(require_permission("production_track")),
):
    of = db.get(OrdreFabrication, id_of)
    if not of:
        from fastapi import HTTPException
        raise HTTPException(404, "Manufacturing order not found")
    return _of_response(of, with_ops=True)
