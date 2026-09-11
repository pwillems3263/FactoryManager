"""
services/pointage_service.py
Gestion du pointage opérateur : début, pause, reprise, fin.
Remplace l'ancien fichier.
"""
from datetime import datetime
from sqlalchemy.orm import Session

from models import OperationPlanifiee, OrdreFabrication, Operation
from models.production import PausePointage


# ─────────────────────────────────────────────────────────────────────────────
# Début
# ─────────────────────────────────────────────────────────────────────────────

def pointer_debut_operation(
    session: Session,
    id_op_plan: int
) -> OperationPlanifiee:
    """
    Pointe le début réel d'une opération (mise en production).
    Statut requis : planifiee → en_cours
    """
    op_plan = session.get(OperationPlanifiee, id_op_plan)
    if not op_plan:
        raise ValueError(f"OperationPlanifiee {id_op_plan} introuvable")

    if op_plan.statut != "planifiee":
        raise ValueError(
            f"Impossible de démarrer : statut actuel '{op_plan.statut}'"
        )

    op_plan.date_debut_reelle = datetime.now()
    op_plan.statut            = "en_cours"

    # Cascade OF → en_cours
    of = session.get(OrdreFabrication, op_plan.id_of)
    if of and of.statut in ("a_planifier", "planifie"):
        of.statut = "en_cours"
        print(f"OF {of.id_of} passé en_cours")
        if of.of_assemblage and of.of_assemblage.statut == "planifie":
            of.of_assemblage.statut = "en_cours"
            print(f"OFAssemblage {of.of_assemblage.id_of_assemblage} passé en_cours")

    print(f"Opération {id_op_plan} démarrée à {op_plan.date_debut_reelle}")
    return op_plan


# ─────────────────────────────────────────────────────────────────────────────
# Pause
# ─────────────────────────────────────────────────────────────────────────────

def pointer_pause_debut(
    session: Session,
    id_op_plan: int,
    motif: str = "autre"
) -> PausePointage:
    """
    Démarre une pause sur une opération en cours.
    Crée un enregistrement PausePointage avec fin_pause = NULL.
    Statut requis : en_cours  (reste en_cours, la pause est dans PausePointage)
    """
    op_plan = session.get(OperationPlanifiee, id_op_plan)
    if not op_plan:
        raise ValueError(f"OperationPlanifiee {id_op_plan} introuvable")

    if op_plan.statut != "en_cours":
        raise ValueError(
            f"Impossible de pauser : statut actuel '{op_plan.statut}'"
        )

    # Sécurité : fermer toute pause ouverte précédente (ne devrait pas arriver)
    pause_ouverte = _get_pause_ouverte(session, id_op_plan)
    if pause_ouverte:
        print(f"  ⚠ Pause ouverte détectée sur op {id_op_plan}, fermeture automatique")
        _fermer_pause(pause_ouverte)

    pause = PausePointage(
        id_op_plan  = id_op_plan,
        debut_pause = datetime.now(),
        motif       = motif,
    )
    session.add(pause)
    print(f"Opération {id_op_plan} — pause débutée ({motif})")
    return pause


def pointer_pause_fin(
    session: Session,
    id_op_plan: int
) -> PausePointage:
    """
    Termine la pause active d'une opération.
    Calcule et stocke duree_min.
    Statut de l'opération : reste en_cours.
    """
    pause = _get_pause_ouverte(session, id_op_plan)
    if not pause:
        raise ValueError(
            f"Aucune pause ouverte sur l'opération {id_op_plan}"
        )

    _fermer_pause(pause)
    print(
        f"Opération {id_op_plan} — pause terminée "
        f"({pause.duree_min} min, motif={pause.motif})"
    )
    return pause


# ─────────────────────────────────────────────────────────────────────────────
# Fin
# ─────────────────────────────────────────────────────────────────────────────

def pointer_fin_operation(
    session: Session,
    id_op_plan: int,
    tps_prep_reel: int,
    tps_exec_reel: int
) -> OperationPlanifiee:
    """
    Pointe la fin réelle d'une opération avec les temps réels (hors pauses).
    - tps_prep_reel  : minutes de préparation réelles
    - tps_exec_reel  : minutes d'exécution réelles
    Les pauses éventuellement encore ouvertes sont fermées automatiquement.
    Déclenche le recalcul en cascade si l'écart dépasse 5 min.
    """
    from services.planning_service import get_prochaine_dispo_machine

    op_plan = session.get(OperationPlanifiee, id_op_plan)
    if not op_plan:
        raise ValueError(f"OperationPlanifiee {id_op_plan} introuvable")

    if op_plan.statut != "en_cours":
        raise ValueError(
            f"Impossible de terminer : statut actuel '{op_plan.statut}'"
        )

    # Fermeture automatique d'une pause encore ouverte
    pause_ouverte = _get_pause_ouverte(session, id_op_plan)
    if pause_ouverte:
        print(f"  ⚠ Pause ouverte sur op {id_op_plan} fermée automatiquement à la fin")
        _fermer_pause(pause_ouverte)

    # Enregistre les temps réels
    op_plan.date_fin_reelle  = datetime.now()
    op_plan.tps_prep_reel    = tps_prep_reel
    op_plan.tps_exec_reel    = tps_exec_reel
    op_plan.duree_reelle_min = tps_prep_reel + tps_exec_reel
    op_plan.statut           = "terminee"

    # Calcule l'écart prévisionnel vs réel
    tps_prevu = (
        op_plan.operation.tps_preparation +
        op_plan.operation.tps_execution * float(op_plan.of.quantite)
    )
    tps_reel  = tps_prep_reel + tps_exec_reel
    ecart_min = tps_reel - tps_prevu

    # Résumé pauses
    pauses_totales = get_duree_pauses_min(session, id_op_plan)
    print(
        f"Opération {id_op_plan} terminée | "
        f"tps prévu={tps_prevu:.0f}min | "
        f"tps réel={tps_reel}min | "
        f"pauses={pauses_totales}min | "
        f"écart={ecart_min:+.0f}min"
    )

    # Recalcul en cascade si écart significatif (> 5 minutes)
    if abs(ecart_min) > 5:
        print(f"Écart significatif ({ecart_min:+.0f}min) → recalcul en cascade...")
        date_fin_reelle = op_plan.date_fin_reelle

        of = session.get(OrdreFabrication, op_plan.id_of)
        if of:
            ops_suivantes_of = session.query(OperationPlanifiee).join(
                Operation
            ).filter(
                OperationPlanifiee.id_of == op_plan.id_of,
                Operation.ordre > op_plan.operation.ordre,
                OperationPlanifiee.statut == "planifiee"
            ).order_by(Operation.ordre).all()

            date_courante = date_fin_reelle
            for op_suiv in ops_suivantes_of:
                duree_suiv = op_suiv.date_fin - op_suiv.date_debut
                dispo = get_prochaine_dispo_machine(
                    session=session,
                    id_machine=op_suiv.id_machine,
                    apres=date_courante
                )
                nouvelle_debut = max(date_courante, dispo)
                op_suiv.date_debut = nouvelle_debut
                op_suiv.date_fin   = nouvelle_debut + duree_suiv
                date_courante      = op_suiv.date_fin
                print(f"  → Op {op_suiv.id_op_plan} recalculée : {str(nouvelle_debut)[:16]}")

            if ops_suivantes_of:
                of.date_fin_prevue = ops_suivantes_of[-1].date_fin

        ops_machine_suivantes = session.query(OperationPlanifiee).filter(
            OperationPlanifiee.id_machine == op_plan.id_machine,
            OperationPlanifiee.id_op_plan != id_op_plan,
            OperationPlanifiee.statut == "planifiee",
            OperationPlanifiee.date_debut >= op_plan.date_debut
        ).order_by(OperationPlanifiee.date_debut).all()

        date_courante = date_fin_reelle
        for op_mach in ops_machine_suivantes:
            duree = op_mach.date_fin - op_mach.date_debut
            if op_mach.date_debut < date_courante:
                op_mach.date_debut = date_courante
                op_mach.date_fin   = date_courante + duree
                date_courante      = op_mach.date_fin
                print(f"  → Op machine {op_mach.id_op_plan} décalée : {str(op_mach.date_debut)[:16]}")
            else:
                break

    # Cascade OF → termine si toutes les ops sont terminées
    of = session.get(OrdreFabrication, op_plan.id_of)
    if of:
        ops_restantes = session.query(OperationPlanifiee).filter(
            OperationPlanifiee.id_of == of.id_of,
            OperationPlanifiee.statut.notin_(["terminee", "rebutee"])
        ).count()
        if ops_restantes == 0:
            of.statut = "termine"
            of.date_fin_reelle = datetime.now()
            print(f"OF {of.id_of} terminé")

            if of.of_assemblage:
                from models import OrdreFabrication as OF
                ofs_non_termines = session.query(OF).filter(
                    OF.id_of_assemblage == of.of_assemblage.id_of_assemblage,
                    OF.statut.notin_(["termine", "rebute", "annule"])
                ).count()
                if ofs_non_termines == 0:
                    of.of_assemblage.statut = "termine"
                    print(f"OFAssemblage {of.of_assemblage.id_of_assemblage} terminé")

    return op_plan


# ─────────────────────────────────────────────────────────────────────────────
# Helpers lecture
# ─────────────────────────────────────────────────────────────────────────────

def get_pauses(session: Session, id_op_plan: int) -> list[PausePointage]:
    """Retourne toutes les pauses d'une opération, triées par début."""
    return (
        session.query(PausePointage)
        .filter(PausePointage.id_op_plan == id_op_plan)
        .order_by(PausePointage.debut_pause)
        .all()
    )


def get_duree_pauses_min(session: Session, id_op_plan: int) -> int:
    """Retourne la somme des durées de toutes les pauses terminées (en minutes)."""
    pauses = get_pauses(session, id_op_plan)
    return sum(p.duree_min or 0 for p in pauses if p.fin_pause is not None)


def get_ops_machine_du_jour(
    session: Session,
    id_machine: int,
    date_reference: datetime = None
) -> list[OperationPlanifiee]:
    """
    Retourne les opérations planifiées ou en cours pour une machine,
    pour la journée de date_reference (défaut = aujourd'hui).
    Triées par date_debut ASC.
    """
    from datetime import timedelta
    ref = date_reference or datetime.now()
    debut_journee = ref.replace(hour=0,  minute=0,  second=0,  microsecond=0)
    fin_journee   = ref.replace(hour=23, minute=59, second=59, microsecond=0)

    return (
        session.query(OperationPlanifiee)
        .filter(
            OperationPlanifiee.id_machine == id_machine,
            OperationPlanifiee.statut.in_(["planifiee", "en_cours"]),
            OperationPlanifiee.date_debut >= debut_journee,
            OperationPlanifiee.date_debut <= fin_journee,
        )
        .order_by(OperationPlanifiee.date_debut)
        .all()
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internes
# ─────────────────────────────────────────────────────────────────────────────

def _get_pause_ouverte(session: Session, id_op_plan: int) -> PausePointage | None:
    """Retourne la pause encore ouverte (fin_pause IS NULL) ou None."""
    return (
        session.query(PausePointage)
        .filter(
            PausePointage.id_op_plan == id_op_plan,
            PausePointage.fin_pause.is_(None)
        )
        .first()
    )


def _fermer_pause(pause: PausePointage) -> None:
    """Ferme une pause en calculant sa durée."""
    pause.fin_pause = datetime.now()
    delta = pause.fin_pause - pause.debut_pause
    pause.duree_min = max(1, int(delta.total_seconds() / 60))