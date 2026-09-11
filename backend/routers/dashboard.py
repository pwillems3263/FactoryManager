"""
backend/routers/dashboard.py
----------------------------
Endpoint dashboard : GET /dashboard
Retourne les 6 KPIs et les 3 tableaux de la page d'accueil.
Requiert niveau >= 2 (Coordinator).
"""

from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import require_permission
from database import get_db
from models import (
    Commande, OrdreFabrication, OFAssemblage,
    Rebut, Machine, ArretMachine, OperationPlanifiee, LigneCommande
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# ─── Schémas de réponse ──────────────────────────────────────────────────────

class KPIs(BaseModel):
    commandes_en_production: int
    ofs_a_planifier:         int
    ofs_en_cours:            int
    rebuts_ce_mois:          int
    machines_disponibles:    int
    machines_arret:          int


class OFUrgent(BaseModel):
    id_of_assemblage: int
    assemblage_nom:   str
    quantite:         float
    priorite:         int
    statut:           str
    statut_label:     str


class ArretMachineItem(BaseModel):
    id_arret:    int
    machine_nom: str
    type_arret:  str
    depuis:      str
    duree_h:     float


class OFRetard(BaseModel):
    id_of:          int
    code_of:        str | None
    composant_nom:  str
    quantite:       float
    date_fin_prevue: str
    statut:         str
    statut_label:   str


class DashboardResponse(BaseModel):
    kpis:            KPIs
    ofs_urgents:     list[OFUrgent]
    arrets_machines: list[ArretMachineItem]
    ofs_retard:      list[OFRetard]
    updated_at:      str


# ─── Endpoint ────────────────────────────────────────────────────────────────

STATUT_MAP = {
    "a_planifier": "To Schedule",
    "planifie":    "Planned",
    "en_cours":    "In Progress",
    "termine":     "Completed",
    "terminee":    "Completed",
    "annule":      "Cancelled",
    "rebutee":     "Scrapped",
}


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    _user=Depends(require_permission("dashboard"))
):
    """
    Retourne toutes les données du dashboard en un seul appel.
    Rafraîchissement recommandé toutes les 60 secondes côté frontend.
    """
    now = datetime.now()

    # ── KPI : Commandes en production ────────────────────────────────────────
    nb_commandes = db.query(Commande).filter(
        db.query(OFAssemblage).join(
            LigneCommande,
            OFAssemblage.id_ligne == LigneCommande.id_ligne
        ).filter(
            LigneCommande.id_commande == Commande.id_commande,
            OFAssemblage.statut.in_(["planifie", "en_cours"])
        ).exists()
    ).count()

    # ── KPI : OFs à planifier ────────────────────────────────────────────────
    nb_a_planifier = db.query(OFAssemblage).filter(
        db.query(OrdreFabrication).filter(
            OrdreFabrication.id_of_assemblage == OFAssemblage.id_of_assemblage,
            OrdreFabrication.statut == "a_planifier"
        ).exists()
    ).count()

    # ── KPI : OFs en cours ───────────────────────────────────────────────────
    nb_en_cours = db.query(OFAssemblage).filter(
        db.query(OperationPlanifiee).join(
            OrdreFabrication,
            OperationPlanifiee.id_of == OrdreFabrication.id_of
        ).filter(
            OrdreFabrication.id_of_assemblage == OFAssemblage.id_of_assemblage,
            OperationPlanifiee.statut == "en_cours"
        ).exists()
    ).count()

    # ── KPI : Rebuts ce mois ─────────────────────────────────────────────────
    debut_mois = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    nb_rebuts = db.query(Rebut).filter(
        Rebut.date_constat >= debut_mois
    ).count()

    # ── KPI : Machines ───────────────────────────────────────────────────────
    nb_dispo = db.query(Machine).filter(Machine.statut == "available").count()
    nb_arret = db.query(Machine).filter(Machine.statut != "available").count()

    # ── OFs urgents (priorité <= 2) ──────────────────────────────────────────
    ofa_urgents = db.query(OFAssemblage).filter(
        OFAssemblage.priorite <= 2,
        OFAssemblage.statut.in_(["planifie", "en_cours"])
    ).order_by(OFAssemblage.priorite).all()

    ofs_urgents_list = []
    for ofa in ofa_urgents:
        ids_ofs = [of.id_of for of in ofa.ordres_fabrication]
        ops = db.query(OperationPlanifiee).filter(
            OperationPlanifiee.id_of.in_(ids_ofs)
        ).all() if ids_ofs else []

        if ops and any(o.statut == "en_cours" for o in ops):
            statut_effectif = "en_cours"
        elif ops and all(o.statut in ("terminee", "rebutee") for o in ops):
            statut_effectif = "termine"
        else:
            statut_effectif = ofa.statut

        ofs_urgents_list.append(OFUrgent(
            id_of_assemblage=ofa.id_of_assemblage,
            assemblage_nom=ofa.assemblage.nom if ofa.assemblage else "—",
            quantite=float(ofa.quantite),
            priorite=ofa.priorite,
            statut=statut_effectif,
            statut_label=STATUT_MAP.get(statut_effectif, statut_effectif),
        ))

    # ── Machines en arrêt ────────────────────────────────────────────────────
    arrets = db.query(ArretMachine).filter(
        ArretMachine.date_fin.is_(None)
    ).all()

    arrets_list = []
    for a in arrets:
        duree_h = (now - a.date_debut).total_seconds() / 3600 if a.date_debut else 0
        arrets_list.append(ArretMachineItem(
            id_arret=a.id_arret,
            machine_nom=a.machine.nom if a.machine else "—",
            type_arret=a.type_arret,
            depuis=str(a.date_debut)[:16] if a.date_debut else "—",
            duree_h=round(duree_h, 1),
        ))

    # ── OFs en retard ────────────────────────────────────────────────────────
    ofs_retard = db.query(OrdreFabrication).filter(
        OrdreFabrication.date_fin_prevue < now,
        OrdreFabrication.statut.in_(["planifie", "en_cours"])
    ).order_by(OrdreFabrication.date_fin_prevue).all()

    retards_list = []
    for of in ofs_retard:
        retards_list.append(OFRetard(
            id_of=of.id_of,
            code_of=of.code_of,
            composant_nom=of.composant.nom if of.composant else "—",
            quantite=float(of.quantite),
            date_fin_prevue=str(of.date_fin_prevue)[:16] if of.date_fin_prevue else "—",
            statut=of.statut,
            statut_label=STATUT_MAP.get(of.statut, of.statut),
        ))

    return DashboardResponse(
        kpis=KPIs(
            commandes_en_production=nb_commandes,
            ofs_a_planifier=nb_a_planifier,
            ofs_en_cours=nb_en_cours,
            rebuts_ce_mois=nb_rebuts,
            machines_disponibles=nb_dispo,
            machines_arret=nb_arret,
        ),
        ofs_urgents=ofs_urgents_list,
        arrets_machines=arrets_list,
        ofs_retard=retards_list,
        updated_at=now.strftime("%Y-%m-%d %H:%M:%S"),
    )
