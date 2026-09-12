"""
backend/routers/planning.py
----------------------------
Planning view — operations by machine with date range filter.
Also exposes the global reschedule action.
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import require_permission, get_db
from models import Machine, OperationPlanifiee, OrdreFabrication

router = APIRouter(prefix="/planning", tags=["Planning"])

STATUT_COLORS = {
    "planifiee": "#3498db",
    "en_cours":  "#8e44ad",
    "terminee":  "#27ae60",
    "rebutee":   "#e74c3c",
    "a_planifier": "#e67e22",
}
STATUT_LABELS = {
    "planifiee":   "Planned",
    "en_cours":    "In Progress",
    "terminee":    "Completed",
    "rebutee":     "Scrapped",
    "a_planifier": "To Schedule",
}


# ─── Schemas ─────────────────────────────────────────────────────────────────

class PlanningOpResponse(BaseModel):
    id_op:           int
    id_of:           int
    code_of:         Optional[str]
    ordre:           int
    nom_operation:   str
    composant_nom:   str
    assembly_nom:    str
    id_machine:      Optional[int]
    machine_nom:     Optional[str]
    duree_prevue_h:  Optional[float]
    date_debut:      Optional[str]
    date_fin:        Optional[str]
    statut:          str
    statut_label:    str
    statut_color:    str
    priorite:        int


class MachinePlanningResponse(BaseModel):
    id_machine:  int
    nom:         str
    statut:      str
    operations:  list[PlanningOpResponse]


class PlanningResponse(BaseModel):
    machines:    list[MachinePlanningResponse]
    date_debut:  str
    date_fin:    str
    total_ops:   int


class MoveOpRequest(BaseModel):
    new_date_debut: datetime
    id_machine:     Optional[int] = None


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _op_response(op: OperationPlanifiee) -> PlanningOpResponse:
    of = op.of
    ofa = of.of_assemblage if of else None
    return PlanningOpResponse(
        id_op=op.id_op,
        id_of=op.id_of,
        code_of=of.code_of if of else None,
        ordre=op.ordre,
        nom_operation=op.nom_operation or f"Op {op.ordre}",
        composant_nom=of.composant.nom if of and of.composant else "—",
        assembly_nom=ofa.assemblage.nom if ofa and ofa.assemblage else "—",
        id_machine=op.id_machine,
        machine_nom=op.machine.nom if op.machine else None,
        duree_prevue_h=float(op.duree_prevue_h) if op.duree_prevue_h else None,
        date_debut=str(op.date_debut)[:16] if op.date_debut else None,
        date_fin=str(op.date_fin)[:16] if op.date_fin else None,
        statut=op.statut,
        statut_label=STATUT_LABELS.get(op.statut, op.statut),
        statut_color=STATUT_COLORS.get(op.statut, "#95a5a6"),
        priorite=ofa.priorite if ofa else 5,
    )


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("", response_model=PlanningResponse)
def get_planning(
    date_debut: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_fin:   Optional[str] = Query(None, description="YYYY-MM-DD"),
    db:         Session       = Depends(get_db),
    _user                     = Depends(require_permission("planning")),
):
    """
    Returns all planned operations grouped by machine for the given date range.
    Default: today + 7 days.
    """
    now = datetime.now()
    if date_debut:
        dt_debut = datetime.strptime(date_debut, "%Y-%m-%d")
    else:
        dt_debut = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if date_fin:
        dt_fin = datetime.strptime(date_fin, "%Y-%m-%d").replace(hour=23, minute=59)
    else:
        dt_fin = dt_debut + timedelta(days=7)

    # All machines
    machines = db.query(Machine).order_by(Machine.nom).all()

    # Operations in date range (include in-progress even if started before)
    ops = db.query(OperationPlanifiee).filter(
        OperationPlanifiee.statut.in_(["planifiee", "en_cours"]),
    ).filter(
        (OperationPlanifiee.date_fin >= dt_debut) |
        (OperationPlanifiee.statut == "en_cours")
    ).filter(
        (OperationPlanifiee.date_debut <= dt_fin) |
        (OperationPlanifiee.statut == "en_cours")
    ).order_by(OperationPlanifiee.date_debut).all()

    # Group by machine
    ops_by_machine: dict[int, list] = {}
    unassigned = []
    for op in ops:
        if op.id_machine:
            ops_by_machine.setdefault(op.id_machine, []).append(op)
        else:
            unassigned.append(op)

    result_machines = []
    for m in machines:
        m_ops = ops_by_machine.get(m.id_machine, [])
        if m_ops:
            result_machines.append(MachinePlanningResponse(
                id_machine=m.id_machine,
                nom=m.nom,
                statut=m.statut,
                operations=[_op_response(op) for op in
                            sorted(m_ops, key=lambda o: o.date_debut or datetime.max)],
            ))

    # Unassigned operations
    if unassigned:
        result_machines.append(MachinePlanningResponse(
            id_machine=0,
            nom="⚠ Unassigned",
            statut="unknown",
            operations=[_op_response(op) for op in unassigned],
        ))

    return PlanningResponse(
        machines=result_machines,
        date_debut=str(dt_debut)[:10],
        date_fin=str(dt_fin)[:10],
        total_ops=len(ops),
    )


@router.put("/ops/{id_op}/move", response_model=PlanningOpResponse)
def move_operation(
    id_op:   int,
    payload: MoveOpRequest,
    db:      Session = Depends(get_db),
    _user            = Depends(require_permission("planning")),
):
    """Move an operation to a new start date (and optionally a new machine)."""
    op = db.get(OperationPlanifiee, id_op)
    if not op:
        raise HTTPException(404, "Operation not found")
    if op.statut not in ("planifiee", "a_planifier"):
        raise HTTPException(400, f"Cannot move operation with status '{op.statut}'")

    # Recalculate end date based on duration
    op.date_debut = payload.new_date_debut
    if op.duree_prevue_h:
        op.date_fin = payload.new_date_debut + timedelta(hours=float(op.duree_prevue_h))

    if payload.id_machine is not None:
        op.id_machine = payload.id_machine

    db.commit(); db.refresh(op)
    return _op_response(op)


@router.get("/summary", response_model=dict)
def get_summary(
    db:   Session = Depends(get_db),
    _user         = Depends(require_permission("planning")),
):
    """Quick summary: ops by status + machines load."""
    total      = db.query(OperationPlanifiee).count()
    planifiees = db.query(OperationPlanifiee).filter(OperationPlanifiee.statut == "planifiee").count()
    en_cours   = db.query(OperationPlanifiee).filter(OperationPlanifiee.statut == "en_cours").count()
    terminees  = db.query(OperationPlanifiee).filter(OperationPlanifiee.statut == "terminee").count()
    return {
        "total": total,
        "planifiees": planifiees,
        "en_cours": en_cours,
        "terminees": terminees,
        "unassigned": db.query(OperationPlanifiee).filter(
            OperationPlanifiee.id_machine.is_(None),
            OperationPlanifiee.statut == "planifiee"
        ).count(),
    }
