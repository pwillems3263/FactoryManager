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
from services.planning_service import valider_deplacement, deplacer_operation, recalculer_planning_global

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
    ordre = op.operation.ordre if op.operation else 0
    duree_h = None
    if op.date_debut and op.date_fin:
        duree_h = round((op.date_fin - op.date_debut).total_seconds() / 3600, 2)
    return PlanningOpResponse(
        id_op=op.id_op_plan,
        id_of=op.id_of,
        code_of=of.code_of if of else None,
        ordre=ordre,
        nom_operation=(op.operation.description if op.operation and op.operation.description
                       else f"Op {ordre}"),
        composant_nom=of.composant.nom if of and of.composant else "—",
        assembly_nom=ofa.assemblage.nom if ofa and ofa.assemblage else "—",
        id_machine=op.id_machine,
        machine_nom=op.machine.nom if op.machine else None,
        duree_prevue_h=duree_h,
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


@router.put("/ops/{id_op}/move", response_model=list[PlanningOpResponse])
def move_operation(
    id_op:   int,
    payload: MoveOpRequest,
    db:      Session = Depends(get_db),
    _user            = Depends(require_permission("planning")),
):
    """
    Move an operation to a new start date (and optionally a new machine).
    Cascades the shift to subsequent operations of the same routing, exactly
    like the desktop app. Returns every operation that was touched, so the
    Gantt can update all affected bars in one go.
    """
    op = db.get(OperationPlanifiee, id_op)
    if not op:
        raise HTTPException(404, "Operation not found")

    # The frontend sends an ISO string with a 'Z' suffix, which parses as
    # timezone-aware — but every date stored in the DB (date_fin, etc.) is
    # naive. Strip the tzinfo so comparisons in the service layer don't blow up.
    nouvelle_date_debut = payload.new_date_debut
    if nouvelle_date_debut.tzinfo is not None:
        nouvelle_date_debut = nouvelle_date_debut.replace(tzinfo=None)

    try:
        ok, message = valider_deplacement(
            session=db,
            id_op_plan=id_op,
            nouvelle_date_debut=nouvelle_date_debut,
            id_nouvelle_machine=payload.id_machine,
        )
    except Exception as e:
        raise HTTPException(400, f"Validation error: {e}")
    if not ok:
        raise HTTPException(400, message)

    try:
        modifiees = deplacer_operation(
            session=db,
            id_op_plan=id_op,
            nouvelle_date_debut=nouvelle_date_debut,
            id_nouvelle_machine=payload.id_machine,
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Failed to move operation: {e}")

    return [_op_response(db.get(OperationPlanifiee, m.id_op_plan)) for m in modifiees]


@router.post("/recalculate-global", response_model=dict)
def recalculate_global(
    db:   Session = Depends(get_db),
    _user         = Depends(require_permission("planning")),
):
    """
    Re-schedules every planned operation at the earliest possible time,
    respecting machine availability, routing order, and priority — the same
    global optimizer as the desktop app's planning screen.
    """
    try:
        result = recalculer_planning_global(db)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Failed to recalculate schedule: {e}")
    return result


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
