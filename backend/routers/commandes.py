"""
backend/routers/commandes.py
-----------------------------
CRUD Orders (Commande + LigneCommande)
"""

from typing import Optional, Literal
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

# Order-level status (Commande.statut). Drives real behavior — see
# create/update/delete_order below — not just a display label:
#   estimation      -> can still be freely edited and deleted
#   part_confirmed  -> delivery date is frozen
#   confirmed       -> delivery date is frozen
#   finished        -> a delivery date must be on record
ORDER_STATUSES = ["estimation", "part_confirmed", "confirmed", "finished"]
ORDER_STATUSES_LOCKING_DELIVERY = {"part_confirmed", "confirmed"}

STATUT_LABELS = {
    "estimation":      "Estimation",
    "part_confirmed":  "Part. Confirmed",
    "confirmed":       "Confirmed",
    "finished":        "Finished",
    # Order-line statuses (LigneCommande.statut) — separate domain, kept
    # here since the same STATUT_LABELS/STATUT_COLORS dicts are reused for
    # both order and line responses.
    "on_hold":    "On Hold",
    "released":   "Released",
    "completed":  "Completed",
}

STATUT_COLORS = {
    "estimation":      "#95a5a6",
    "part_confirmed":  "#e67e22",
    "confirmed":       "#3498db",
    "finished":        "#27ae60",
    "on_hold":   "#e67e22",
    "released":  "#3498db",
    "completed": "#27ae60",
}


# ─── Schemas ─────────────────────────────────────────────────────────────────

class CommandeBase(BaseModel):
    date_commande:  date
    client:         str
    numero_externe: Optional[str] = None
    date_livraison: Optional[date] = None          # estimated delivery date
    date_livraison_reelle: Optional[date] = None   # actual delivery date, recorded separately for later comparison
    statut:         Literal["estimation", "part_confirmed", "confirmed", "finished"] = "estimation"


class CommandeCreate(CommandeBase):
    pass


class CommandeUpdate(BaseModel):
    date_commande:  Optional[date] = None
    client:         Optional[str]  = None
    numero_externe: Optional[str]  = None
    date_livraison: Optional[date] = None
    date_livraison_reelle: Optional[date] = None
    statut:         Optional[Literal["estimation", "part_confirmed", "confirmed", "finished"]] = None


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
    prix_revient_actuel:   Optional[float]  # live unit cost of the assembly right now — always shown
    prix_revient_snapshot: Optional[float]  # unit cost frozen at Release time (or the special price used then)

    class Config:
        from_attributes = True


class CommandeResponse(BaseModel):
    id_commande:    int
    code_commande:  Optional[str]
    numero_externe: Optional[str]
    client:         str
    date_commande:  str
    date_livraison: Optional[str]
    date_livraison_reelle: Optional[str]
    statut:         str
    statut_label:   str
    statut_color:   str
    nb_lignes:      int
    total_prix_actuel:   Optional[float] = None  # sum of (live unit price x qty) across all lines
    total_prix_snapshot: Optional[float] = None  # sum of (frozen unit price x qty), only for released/completed lines — None if none released yet
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
    quantite:      int  # whole units only


class LigneUpdate(BaseModel):
    quantite: Optional[int] = None  # whole units only
    statut:   Optional[str] = None


class ReleaseLineRequest(BaseModel):
    # Optional negotiated price overriding the calculated cost for this
    # line, in case a special deal was made with the customer. If omitted,
    # the assembly's currently calculated cost is used as-is.
    prix_special: Optional[float] = None


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
        prix_revient_actuel=float(asm.prix_revient) if asm and asm.prix_revient else None,
        prix_revient_snapshot=float(l.prix_revient_snapshot) if l.prix_revient_snapshot else None,
    )


def _to_response(c: Commande, db: Session, with_lignes: bool = False) -> CommandeResponse:
    # Always computed (needed for the order-level totals below), but only
    # included in the response's "lignes" field when with_lignes is True —
    # list views stay light, detail views get the full breakdown.
    lignes = [_ligne_to_response(l, db) for l in c.lignes]

    # Current total: sum of (live unit price x qty) over every line — always
    # computable, gives a running "what would it cost if released today".
    total_actuel = None
    if c.lignes:
        vals = [l.prix_revient_actuel * l.quantite for l in lignes if l.prix_revient_actuel is not None]
        if vals:
            total_actuel = round(sum(vals), 2)

    # Snapshot total: sum of (frozen unit price x qty) — only meaningful
    # once at least one line has actually been released.
    total_snapshot = None
    snap_vals = [l.prix_revient_snapshot * l.quantite for l in lignes if l.prix_revient_snapshot is not None]
    if snap_vals:
        total_snapshot = round(sum(snap_vals), 2)

    return CommandeResponse(
        id_commande=c.id_commande,
        code_commande=c.code_commande,
        numero_externe=c.numero_externe,
        client=c.client,
        date_commande=str(c.date_commande),
        date_livraison=str(c.date_livraison) if c.date_livraison else None,
        date_livraison_reelle=str(c.date_livraison_reelle) if c.date_livraison_reelle else None,
        statut=c.statut,
        statut_label=STATUT_LABELS.get(c.statut, c.statut),
        statut_color=STATUT_COLORS.get(c.statut, "#95a5a6"),
        nb_lignes=len(c.lignes),
        total_prix_actuel=total_actuel,
        total_prix_snapshot=total_snapshot,
        lignes=lignes if with_lignes else [],
    )


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/customers", response_model=list[str])
def list_customers(
    db: Session = Depends(get_db),
    _user       = Depends(require_permission("orders")),
):
    """Distinct customer names already used on orders, for the Customer
    field's autocomplete suggestions in the New/Edit Order form."""
    rows = (
        db.query(Commande.client)
        .filter(Commande.client.isnot(None), Commande.client != "")
        .distinct()
        .order_by(Commande.client)
        .all()
    )
    return [r[0] for r in rows]


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

    updates = payload.model_dump(exclude_unset=True)
    resulting_statut = updates.get("statut", c.statut)

    # Delivery date is frozen while the order stays Part. Confirmed /
    # Confirmed. It can still be changed when the update simultaneously
    # moves the order OUT of one of those statuses (e.g. into Finished, to
    # record the actual delivery date).
    if ("date_livraison" in updates
            and c.statut in ORDER_STATUSES_LOCKING_DELIVERY
            and resulting_statut in ORDER_STATUSES_LOCKING_DELIVERY):
        raise HTTPException(
            409,
            "Delivery date is locked while the order is Part. Confirmed or Confirmed."
        )

    # Finished orders must have an ACTUAL delivery date on record — kept in
    # its own field (date_livraison_reelle), separate from the estimated
    # delivery date (date_livraison), so the two can be compared later
    # (e.g. was the order delivered on time, early, or late).
    if resulting_statut == "finished":
        final_date = updates.get("date_livraison_reelle", c.date_livraison_reelle)
        if not final_date:
            raise HTTPException(
                400,
                "An actual delivery date must be recorded before marking the order as Finished."
            )

    for field, value in updates.items():
        setattr(c, field, value)
    db.commit(); db.refresh(c)
    return _to_response(c, db, with_lignes=True)


@router.delete("/{id_commande}", status_code=204)
def delete_order(id_commande: int, db: Session = Depends(get_db),
                 _user=Depends(require_permission("orders"))):
    c = db.get(Commande, id_commande)
    if not c:
        raise HTTPException(404, "Order not found")
    if c.statut != "estimation":
        raise HTTPException(409, "Only orders still in 'Estimation' status can be deleted.")
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
                  payload: Optional[ReleaseLineRequest] = None,
                  db: Session = Depends(get_db),
                  _user=Depends(require_permission("orders"))):
    """
    Release a line: generates the OFAssemblage + component OFs from the BOM,
    schedules them at the earliest possible date, snapshots the cost price,
    and marks the line as 'released'.
    Mirrors the desktop app's "Release Line" action.

    By default the assembly's currently calculated cost is frozen as the
    snapshot. If payload.prix_special is provided (a negotiated deal with
    the customer), that value is frozen instead.
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

        # 3. Snapshot the cost price — a special negotiated price overrides
        # the calculated one if one was given.
        ligne = db.get(LigneCommande, id_ligne)
        if ligne and ligne.assemblage:
            prix = recalculer_assemblage(db, ligne.id_assemblage)
            if payload and payload.prix_special is not None:
                if payload.prix_special <= 0:
                    raise HTTPException(400, "Special price must be greater than 0")
                ligne.prix_revient_snapshot = payload.prix_special
            else:
                ligne.prix_revient_snapshot = prix

        ligne.statut = "released"
        db.commit()
        db.refresh(ligne)
    except HTTPException:
        db.rollback()
        raise
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
    updates = payload.model_dump(exclude_unset=True)
    # A released or completed line has already generated real production
    # orders sized off its current quantity — silently changing it here
    # would desync it from those OFs, so quantity edits are only allowed
    # while the line is still on hold (mirrors delete_line's restriction).
    if "quantite" in updates and l.statut in ("released", "completed"):
        raise HTTPException(409, "Cannot change the quantity of a released or completed line")
    for field, value in updates.items():
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
