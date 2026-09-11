"""
backend/routers/machines.py
---------------------------
CRUD Machines + Machine Types + Machine Events (ArretMachine)
"""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import require_permission
from database import get_db
from models import Machine, TypeMachine, ArretMachine

router = APIRouter(prefix="/machines", tags=["Machines"])

STATUT_LABELS = {
    "available":    "Available",
    "disponible":   "Available",
    "maintenance":  "Maintenance",
    "hors_service": "Out of Service",
}


# ─── Schemas ─────────────────────────────────────────────────────────────────

class MachineBase(BaseModel):
    nom:               str
    id_type_machine:   Optional[int]   = None
    capacite_h_jour:   Optional[float] = None
    statut:            str             = "available"
    tarif_horaire:     Optional[float] = None
    cout_operateur:    Optional[float] = None
    charge_operateur:  Optional[float] = None
    travaille_samedi:  bool            = False
    travaille_dimanche: bool           = False
    multi_taches:      bool            = False


class MachineCreate(MachineBase):
    pass


class MachineUpdate(BaseModel):
    nom:               Optional[str]   = None
    id_type_machine:   Optional[int]   = None
    capacite_h_jour:   Optional[float] = None
    statut:            Optional[str]   = None
    tarif_horaire:     Optional[float] = None
    cout_operateur:    Optional[float] = None
    charge_operateur:  Optional[float] = None
    travaille_samedi:  Optional[bool]  = None
    travaille_dimanche: Optional[bool] = None
    multi_taches:      Optional[bool]  = None


class MachineResponse(BaseModel):
    id_machine:        int
    nom:               str
    id_type_machine:   Optional[int]
    type_nom:          Optional[str]
    capacite_h_jour:   Optional[float]
    statut:            str
    statut_label:      str
    tarif_horaire:     Optional[float]
    cout_operateur:    Optional[float]
    charge_operateur:  Optional[float]
    travaille_samedi:  bool
    travaille_dimanche: bool
    multi_taches:      bool
    nb_arrets_actifs:  int

    class Config:
        from_attributes = True


class MachineListResponse(BaseModel):
    items: list[MachineResponse]
    total: int
    page:  int
    pages: int


class ArretBase(BaseModel):
    type_arret:  str
    description: Optional[str] = None
    date_debut:  Optional[datetime] = None
    date_fin:    Optional[datetime] = None


class ArretResponse(BaseModel):
    id_arret:    int
    id_machine:  int
    type_arret:  str
    description: Optional[str]
    date_debut:  Optional[str]
    date_fin:    Optional[str]
    en_cours:    bool

    class Config:
        from_attributes = True


class TypeMachineResponse(BaseModel):
    id_type:     int
    nom:         str
    description: Optional[str]

    class Config:
        from_attributes = True


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _to_response(m: Machine, db: Session) -> MachineResponse:
    nb_actifs = db.query(ArretMachine).filter(
        ArretMachine.id_machine == m.id_machine,
        ArretMachine.date_fin.is_(None)
    ).count()
    return MachineResponse(
        id_machine=m.id_machine,
        nom=m.nom,
        id_type_machine=m.id_type_machine,
        type_nom=m.type_machine.nom if m.type_machine else None,
        capacite_h_jour=float(m.capacite_h_jour) if m.capacite_h_jour else None,
        statut=m.statut,
        statut_label=STATUT_LABELS.get(m.statut, m.statut),
        tarif_horaire=float(m.tarif_horaire) if m.tarif_horaire else None,
        cout_operateur=float(m.cout_operateur) if m.cout_operateur else None,
        charge_operateur=float(m.charge_operateur) if m.charge_operateur else None,
        travaille_samedi=m.travaille_samedi,
        travaille_dimanche=m.travaille_dimanche,
        multi_taches=m.multi_taches,
        nb_arrets_actifs=nb_actifs,
    )


# ─── Machine Types ────────────────────────────────────────────────────────────

@router.get("/types", response_model=list[TypeMachineResponse])
def list_types(db: Session = Depends(get_db),
               _user=Depends(require_permission("machines"))):
    return db.query(TypeMachine).order_by(TypeMachine.nom).all()


@router.post("/types", response_model=TypeMachineResponse, status_code=201)
def create_type(payload: dict, db: Session = Depends(get_db),
                _user=Depends(require_permission("machines"))):
    t = TypeMachine(nom=payload["nom"], description=payload.get("description"))
    db.add(t); db.commit(); db.refresh(t)
    return t


# ─── Machines ────────────────────────────────────────────────────────────────

@router.get("", response_model=MachineListResponse)
def list_machines(
    search: Optional[str] = Query(None),
    statut: Optional[str] = Query(None),
    page:   int           = Query(1, ge=1),
    limit:  int           = Query(100, ge=1, le=500),
    db:     Session       = Depends(get_db),
    _user                 = Depends(require_permission("machines")),
):
    q = db.query(Machine)
    if search:
        q = q.filter(Machine.nom.ilike(f"%{search}%"))
    if statut:
        q = q.filter(Machine.statut == statut)
    q = q.order_by(Machine.nom)
    total = q.count()
    items = q.offset((page-1)*limit).limit(limit).all()
    pages = max(1, (total + limit - 1) // limit)
    return MachineListResponse(
        items=[_to_response(m, db) for m in items],
        total=total, page=page, pages=pages,
    )


@router.get("/{id_machine}", response_model=MachineResponse)
def get_machine(id_machine: int, db: Session = Depends(get_db),
                _user=Depends(require_permission("machines"))):
    m = db.get(Machine, id_machine)
    if not m:
        raise HTTPException(404, "Machine not found")
    return _to_response(m, db)


@router.post("", response_model=MachineResponse, status_code=201)
def create_machine(payload: MachineCreate, db: Session = Depends(get_db),
                   _user=Depends(require_permission("machines"))):
    m = Machine(**payload.model_dump())
    db.add(m); db.commit(); db.refresh(m)
    return _to_response(m, db)


@router.put("/{id_machine}", response_model=MachineResponse)
def update_machine(id_machine: int, payload: MachineUpdate,
                   db: Session = Depends(get_db),
                   _user=Depends(require_permission("machines"))):
    m = db.get(Machine, id_machine)
    if not m:
        raise HTTPException(404, "Machine not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(m, field, value)
    db.commit(); db.refresh(m)
    return _to_response(m, db)


@router.delete("/{id_machine}", status_code=204)
def delete_machine(id_machine: int, db: Session = Depends(get_db),
                   _user=Depends(require_permission("machines"))):
    m = db.get(Machine, id_machine)
    if not m:
        raise HTTPException(404, "Machine not found")
    db.delete(m); db.commit()


# ─── Machine Events (Arrêts) ──────────────────────────────────────────────────

@router.get("/{id_machine}/events", response_model=list[ArretResponse])
def list_events(id_machine: int, db: Session = Depends(get_db),
                _user=Depends(require_permission("machines"))):
    return [
        ArretResponse(
            id_arret=a.id_arret,
            id_machine=a.id_machine,
            type_arret=a.type_arret,
            description=a.description,
            date_debut=str(a.date_debut)[:16] if a.date_debut else None,
            date_fin=str(a.date_fin)[:16] if a.date_fin else None,
            en_cours=a.date_fin is None,
        )
        for a in db.query(ArretMachine).filter(
            ArretMachine.id_machine == id_machine
        ).order_by(ArretMachine.date_debut.desc()).all()
    ]


@router.post("/{id_machine}/events", response_model=ArretResponse, status_code=201)
def create_event(id_machine: int, payload: ArretBase,
                 db: Session = Depends(get_db),
                 _user=Depends(require_permission("machines"))):
    m = db.get(Machine, id_machine)
    if not m:
        raise HTTPException(404, "Machine not found")
    a = ArretMachine(
        id_machine=id_machine,
        type_arret=payload.type_arret,
        description=payload.description,
        date_debut=payload.date_debut or datetime.now(),
        date_fin=payload.date_fin,
    )
    db.add(a); db.commit(); db.refresh(a)
    return ArretResponse(
        id_arret=a.id_arret, id_machine=a.id_machine,
        type_arret=a.type_arret, description=a.description,
        date_debut=str(a.date_debut)[:16] if a.date_debut else None,
        date_fin=str(a.date_fin)[:16] if a.date_fin else None,
        en_cours=a.date_fin is None,
    )


@router.put("/{id_machine}/events/{id_arret}/close", response_model=ArretResponse)
def close_event(id_machine: int, id_arret: int,
                db: Session = Depends(get_db),
                _user=Depends(require_permission("machines"))):
    """Close an ongoing machine event (set end date to now)."""
    a = db.get(ArretMachine, id_arret)
    if not a or a.id_machine != id_machine:
        raise HTTPException(404, "Event not found")
    a.date_fin = datetime.now()
    db.commit(); db.refresh(a)
    return ArretResponse(
        id_arret=a.id_arret, id_machine=a.id_machine,
        type_arret=a.type_arret, description=a.description,
        date_debut=str(a.date_debut)[:16] if a.date_debut else None,
        date_fin=str(a.date_fin)[:16] if a.date_fin else None,
        en_cours=False,
    )
