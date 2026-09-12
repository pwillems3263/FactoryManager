"""
backend/routers/time_tracking.py
----------------------------------
Time Tracking (Pointage) :
  GET  /time-tracking/machines         → list machines with their today's ops
  GET  /time-tracking/ops/{id_op}      → operation detail
  POST /time-tracking/ops/{id_op}/start   → start operation
  POST /time-tracking/ops/{id_op}/pause   → start pause
  POST /time-tracking/ops/{id_op}/resume  → end pause
  POST /time-tracking/ops/{id_op}/finish  → finish operation
"""

from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user, require_permission, get_db
from models import Machine, OperationPlanifiee, OrdreFabrication
from models.production import PausePointage

router = APIRouter(prefix="/time-tracking", tags=["Time Tracking"])

STATUT_LABELS = {
    "planifiee": "Planned",
    "en_cours":  "In Progress",
    "terminee":  "Completed",
    "rebutee":   "Scrapped",
}
STATUT_COLORS = {
    "planifiee": "#3498db",
    "en_cours":  "#8e44ad",
    "terminee":  "#27ae60",
    "rebutee":   "#e74c3c",
}


# ─── Schemas ─────────────────────────────────────────────────────────────────

class PauseResponse(BaseModel):
    id_pause:    int
    debut_pause: str
    fin_pause:   Optional[str]
    motif:       str
    en_cours:    bool


class OpTrackResponse(BaseModel):
    id_op:           int
    id_of:           int
    code_of:         Optional[str]
    ordre:           int
    nom_operation:   str
    composant_nom:   str
    assembly_nom:    str
    machine_nom:     Optional[str]
    duree_prevue_h:  Optional[float]
    statut:          str
    statut_label:    str
    statut_color:    str
    date_debut:      Optional[str]
    date_fin:        Optional[str]
    date_debut_reelle: Optional[str]
    date_fin_reelle:   Optional[str]
    pauses:          list[PauseResponse] = []
    en_pause:        bool = False


class MachineTrackResponse(BaseModel):
    id_machine:   int
    nom:          str
    statut:       str
    ops_today:    list[OpTrackResponse]
    ops_in_progress: int


class PauseRequest(BaseModel):
    motif: str = "autre"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_pauses(db: Session, id_op: int) -> list[PausePointage]:
    return db.query(PausePointage).filter(
        PausePointage.id_op_plan == id_op
    ).order_by(PausePointage.debut_pause).all()


def _pause_response(p: PausePointage) -> PauseResponse:
    return PauseResponse(
        id_pause=p.id_pause,
        debut_pause=str(p.debut_pause)[:16] if p.debut_pause else "—",
        fin_pause=str(p.fin_pause)[:16] if p.fin_pause else None,
        motif=p.motif or "autre",
        en_cours=p.fin_pause is None,
    )


def _op_response(op: OperationPlanifiee, db: Session) -> OpTrackResponse:
    of = op.of
    ofa = of.of_assemblage if of else None
    pauses = _get_pauses(db, op.id_op_plan)
    en_pause = any(p.fin_pause is None for p in pauses)
    ordre = op.operation.ordre if op.operation else 0
    duree_h = None
    if op.date_debut and op.date_fin:
        duree_h = round((op.date_fin - op.date_debut).total_seconds() / 3600, 2)

    return OpTrackResponse(
        id_op=op.id_op_plan,
        id_of=op.id_of,
        code_of=of.code_of if of else None,
        ordre=ordre,
        nom_operation=(op.operation.description if op.operation and op.operation.description
                       else f"Op {ordre}"),
        composant_nom=of.composant.nom if of and of.composant else "—",
        assembly_nom=ofa.assemblage.nom if ofa and ofa.assemblage else "—",
        machine_nom=op.machine.nom if op.machine else None,
        duree_prevue_h=duree_h,
        statut=op.statut,
        statut_label=STATUT_LABELS.get(op.statut, op.statut),
        statut_color=STATUT_COLORS.get(op.statut, "#95a5a6"),
        date_debut=str(op.date_debut)[:16] if op.date_debut else None,
        date_fin=str(op.date_fin)[:16] if op.date_fin else None,
        date_debut_reelle=str(op.date_debut_reelle)[:16] if op.date_debut_reelle else None,
        date_fin_reelle=str(op.date_fin_reelle)[:16] if op.date_fin_reelle else None,
        pauses=[_pause_response(p) for p in pauses],
        en_pause=en_pause,
    )


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/machines", response_model=list[MachineTrackResponse])
def list_machines_today(
    db:    Session = Depends(get_db),
    _user          = Depends(require_permission("time_tracking")),
):
    """List all machines with their operations for today."""
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end   = datetime.combine(date.today(), datetime.max.time())

    machines = db.query(Machine).order_by(Machine.nom).all()
    result = []

    for m in machines:
        ops = db.query(OperationPlanifiee).filter(
            OperationPlanifiee.id_machine == m.id_machine,
            OperationPlanifiee.statut.in_(["planifiee", "en_cours", "terminee"]),
        ).filter(
            (OperationPlanifiee.date_debut <= today_end) |
            (OperationPlanifiee.statut == "en_cours")
        ).order_by(OperationPlanifiee.date_debut).all()

        in_progress = sum(1 for o in ops if o.statut == "en_cours")

        if ops or in_progress:
            result.append(MachineTrackResponse(
                id_machine=m.id_machine,
                nom=m.nom,
                statut=m.statut,
                ops_today=[_op_response(op, db) for op in ops],
                ops_in_progress=in_progress,
            ))

    return result


@router.get("/ops", response_model=list[OpTrackResponse])
def list_ops_today(
    id_machine: Optional[int] = Query(None),
    db:         Session       = Depends(get_db),
    _user                     = Depends(require_permission("time_tracking")),
):
    """List all operations for today, optionally filtered by machine."""
    q = db.query(OperationPlanifiee).filter(
        OperationPlanifiee.statut.in_(["planifiee", "en_cours"])
    )
    if id_machine:
        q = q.filter(OperationPlanifiee.id_machine == id_machine)
    q = q.order_by(OperationPlanifiee.date_debut)
    return [_op_response(op, db) for op in q.all()]


@router.get("/ops/{id_op}", response_model=OpTrackResponse)
def get_op(id_op: int, db: Session = Depends(get_db),
           _user=Depends(require_permission("time_tracking"))):
    op = db.get(OperationPlanifiee, id_op)
    if not op:
        raise HTTPException(404, "Operation not found")
    return _op_response(op, db)


@router.post("/ops/{id_op}/start", response_model=OpTrackResponse)
def start_op(id_op: int, db: Session = Depends(get_db),
             _user=Depends(require_permission("time_tracking"))):
    """Start an operation (planifiee → en_cours)."""
    op = db.get(OperationPlanifiee, id_op)
    if not op:
        raise HTTPException(404, "Operation not found")
    if op.statut != "planifiee":
        raise HTTPException(400, f"Cannot start: current status is '{op.statut}'")

    op.date_debut_reelle = datetime.now()
    op.statut = "en_cours"

    # Cascade to OF and OFAssemblage
    of = db.get(OrdreFabrication, op.id_of)
    if of and of.statut in ("a_planifier", "planifie"):
        of.statut = "en_cours"
        if of.of_assemblage and of.of_assemblage.statut == "planifie":
            of.of_assemblage.statut = "en_cours"

    db.commit(); db.refresh(op)
    return _op_response(op, db)


@router.post("/ops/{id_op}/pause", response_model=OpTrackResponse)
def pause_op(id_op: int, payload: PauseRequest,
             db: Session = Depends(get_db),
             _user=Depends(require_permission("time_tracking"))):
    """Start a pause on an in-progress operation."""
    op = db.get(OperationPlanifiee, id_op)
    if not op:
        raise HTTPException(404, "Operation not found")
    if op.statut != "en_cours":
        raise HTTPException(400, f"Cannot pause: current status is '{op.statut}'")

    # Close any open pause first
    open_pause = db.query(PausePointage).filter(
        PausePointage.id_op_plan == id_op,
        PausePointage.fin_pause.is_(None)
    ).first()
    if open_pause:
        open_pause.fin_pause = datetime.now()

    pause = PausePointage(
        id_op_plan=id_op,
        debut_pause=datetime.now(),
        motif=payload.motif,
    )
    db.add(pause); db.commit(); db.refresh(op)
    return _op_response(op, db)


@router.post("/ops/{id_op}/resume", response_model=OpTrackResponse)
def resume_op(id_op: int, db: Session = Depends(get_db),
              _user=Depends(require_permission("time_tracking"))):
    """End the current pause, resume operation."""
    op = db.get(OperationPlanifiee, id_op)
    if not op:
        raise HTTPException(404, "Operation not found")

    open_pause = db.query(PausePointage).filter(
        PausePointage.id_op_plan == id_op,
        PausePointage.fin_pause.is_(None)
    ).first()
    if not open_pause:
        raise HTTPException(400, "No active pause found")

    open_pause.fin_pause = datetime.now()
    db.commit(); db.refresh(op)
    return _op_response(op, db)


@router.post("/ops/{id_op}/finish", response_model=OpTrackResponse)
def finish_op(id_op: int, db: Session = Depends(get_db),
              _user=Depends(require_permission("time_tracking"))):
    """Finish an operation (en_cours → terminee)."""
    op = db.get(OperationPlanifiee, id_op)
    if not op:
        raise HTTPException(404, "Operation not found")
    if op.statut != "en_cours":
        raise HTTPException(400, f"Cannot finish: current status is '{op.statut}'")

    # Close any open pause
    open_pause = db.query(PausePointage).filter(
        PausePointage.id_op_plan == id_op,
        PausePointage.fin_pause.is_(None)
    ).first()
    if open_pause:
        open_pause.fin_pause = datetime.now()

    op.date_fin_reelle = datetime.now()
    op.statut = "terminee"

    # Check if all ops of the OF are done → mark OF as termine
    of = db.get(OrdreFabrication, op.id_of)
    if of:
        all_ops = of.operations_planifiees
        if all(o.statut in ("terminee", "rebutee") for o in all_ops):
            of.statut = "termine"
            of.date_fin_reelle = datetime.now()
            # Check if all OFs of the OFAssemblage are done
            if of.of_assemblage:
                all_ofs = of.of_assemblage.ordres_fabrication
                if all(o.statut in ("termine", "annule") for o in all_ofs):
                    of.of_assemblage.statut = "termine"

    db.commit(); db.refresh(op)
    return _op_response(op, db)
