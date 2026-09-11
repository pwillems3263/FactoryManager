from datetime import datetime
from sqlalchemy.orm import Session
from models import Rebut, OperationPlanifiee, OrdreFabrication


def constater_rebut(
    session: Session,
    id_of: int,
    id_op_plan: int,
    quantite_rebutee: float,
    cause: str,
    decision: str
) -> Rebut:
    """
    Enregistre un constat de rebut sur une opération.

    decision = 'rebut_definitif' → clôture l'OF pour la quantité rebutée
    decision = 'retouche'        → génère un OF fils de retouche
    """
    of = session.get(OrdreFabrication, id_of)
    if not of:
        raise ValueError(f"Production order {id_of} not found")

    op_plan = session.get(OperationPlanifiee, id_op_plan)
    if not op_plan:
        raise ValueError(f"Planned operation {id_op_plan} not found")

    if quantite_rebutee <= 0:
        raise ValueError("Scrapped quantity must be positive")

    if quantite_rebutee > float(of.quantite):
        raise ValueError(
            f"Scrapped quantity ({quantite_rebutee}) exceeds OF quantity ({of.quantite})"
        )

    if decision not in ("rebut_definitif", "retouche"):
        raise ValueError(
            f"Invalid decision: '{decision}'. Accepted: 'rebut_definitif' or 'retouche'"
        )

    # Crée le constat de rebut
    rebut = Rebut(
        id_of=id_of,
        id_op_plan=id_op_plan,
        date_constat=datetime.now(),
        quantite_rebutee=quantite_rebutee,
        cause=cause,
        decision=decision
    )
    session.add(rebut)
    session.flush()

    # Set actual end date to now and close the scrapped operation
    now = datetime.now()
    op_plan.statut          = "rebutee"
    # Force planned dates to reflect reality — scrap cannot be in the future
    if op_plan.date_debut and op_plan.date_debut > now:
        op_plan.date_debut = now
    op_plan.date_fin        = now   # planned end = scrap moment
    op_plan.date_fin_reelle = now
    if not op_plan.date_debut_reelle:
        op_plan.date_debut_reelle = op_plan.date_debut or now

    # Reschedule following operations starting from now
    from services.planning_service import deplacer_operation
    from models import Operation
    ops_suivantes = session.query(OperationPlanifiee).join(
        Operation
    ).filter(
        OperationPlanifiee.id_of == id_of,
        Operation.ordre > op_plan.operation.ordre,
        OperationPlanifiee.statut == "planifiee"
    ).order_by(Operation.ordre).all()

    date_courante = now
    for op_suiv in ops_suivantes:
        from services.planning_service import get_prochaine_dispo_machine, get_prochaine_dispo_service
        duree_suiv = op_suiv.date_fin - op_suiv.date_debut
        if op_suiv.id_machine:
            dispo = get_prochaine_dispo_machine(
                session, op_suiv.id_machine, date_courante
            )
        elif op_suiv.id_service:
            dispo = get_prochaine_dispo_service(
                session, op_suiv.id_service, date_courante
            )
        else:
            dispo = date_courante
        nouvelle_debut = max(date_courante, dispo)
        op_suiv.date_debut = nouvelle_debut
        op_suiv.date_fin   = nouvelle_debut + duree_suiv
        date_courante      = op_suiv.date_fin

    print(f"Scrap recorded: OF {id_of} | "
          f"qty={quantite_rebutee} | "
          f"cause={cause} | decision={decision} | "
          f"end_date={str(now)[:16]} | "
          f"{len(ops_suivantes)} following op(s) rescheduled")

    # Traitement selon la décision
    if decision == "rebut_definitif":
        _traiter_rebut_definitif(session, of, quantite_rebutee)
    elif decision == "retouche":
        from services.of_service import generer_of_retouche
        of_retouche = generer_of_retouche(
            session=session,
            id_of_original=id_of,
            quantite_rebutee=quantite_rebutee
        )
        print(f"Rework order generated: id={of_retouche.id_of}")

    return rebut


def _traiter_rebut_definitif(
    session: Session,
    of: OrdreFabrication,
    quantite_rebutee: float
):
    """
    Traitement d'un rebut définitif :
    - Si toute la quantité est rebutée → clôture l'OF
    - Si partielle → met à jour la quantité restante
    """
    quantite_restante = float(of.quantite) - quantite_rebutee

    if quantite_restante <= 0:
        of.statut = "rebute"
        print(f"OF {of.id_of} closed (total scrap)")
    else:
        of.quantite = quantite_restante
        print(f"OF {of.id_of}: quantity updated → {quantite_restante}")