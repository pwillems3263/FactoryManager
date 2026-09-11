from datetime import datetime, timedelta, time
from sqlalchemy.orm import Session
from models import OrdreFabrication, OperationPlanifiee, Gamme, Operation, Machine


# ── Définition des 3 pauses ─────────────────────────────────────────────────
# shift 0 : 06h00 – 14h00
# shift 1 : 14h00 – 22h00
# shift 2 : 22h00 – 06h00 (lendemain)

SHIFTS_DEF = [
    (time(6, 0),  time(14, 0)),   # 0
    (time(14, 0), time(22, 0)),   # 1
    (time(22, 0), time(6, 0)),    # 2  — crosses midnight
]

# Legacy constants kept for backward compat
PLAGE_8H  = (time(6, 0), time(14, 0))
PLAGE_16H = (time(6, 0), time(22, 0))


def get_active_shifts(session: Session, id_machine: int) -> set[int]:
    """
    Returns the set of active shift indices {0,1,2} for a machine.
    Priority 1: MachineShiftConfig rows in DB (if any exist for this machine)
    Priority 2: derive from machine.capacite_h_jour
    Priority 3: all shifts active (24h)
    """
    try:
        from models.production import MachineShiftConfig
        rows = session.query(MachineShiftConfig).filter_by(id_machine=id_machine).all()
        if rows:
            cfg = {r.shift_index: r.active for r in rows}
            return {i for i in range(3) if cfg.get(i, True)}
    except Exception:
        pass
    # Fallback: derive from capacite_h_jour
    machine = session.get(Machine, id_machine)
    if machine and machine.capacite_h_jour:
        return _active_shifts_from_cap(machine.capacite_h_jour)
    return {0, 1, 2}


def set_shift_active(session: Session, id_machine: int, shift_index: int, active: bool):
    """
    Creates or updates the shift config for a machine/shift.
    Returns the updated MachineShiftConfig row.
    """
    from models.production import MachineShiftConfig
    row = session.query(MachineShiftConfig).filter_by(
        id_machine=id_machine, shift_index=shift_index
    ).first()
    if row is None:
        row = MachineShiftConfig(id_machine=id_machine,
                                  shift_index=shift_index, active=active)
        session.add(row)
    else:
        row.active = active
    session.flush()
    return row


def _plage_machine(capacite_h_jour) -> tuple[time, time] | None:
    """
    Legacy helper — kept for backward compat with hover tooltip.
    Returns a simple (start, end) window based on capacite_h_jour only.
    Use the shift-aware functions for scheduling.
    """
    try:
        cap = float(capacite_h_jour)
    except (TypeError, ValueError):
        return None
    if cap <= 8:
        return PLAGE_8H
    if cap <= 16:
        return PLAGE_16H
    return None


def _active_shifts_from_cap(capacite_h_jour) -> set[int]:
    """
    Derives the default active shifts from capacite_h_jour, WITHOUT hitting the DB.
    Used only when there is no MachineShiftConfig row yet.
    8h  → {0}        (06h–14h only)
    16h → {0, 1}     (06h–22h)
    24h → {0, 1, 2}  (all)
    """
    try:
        cap = float(capacite_h_jour)
    except (TypeError, ValueError):
        return {0, 1, 2}
    if cap <= 8:
        return {0}
    if cap <= 16:
        return {0, 1}
    return {0, 1, 2}


def ajuster_selon_plage_machine(
    dt: datetime,
    machine: Machine | None,
    session: Session | None = None
) -> datetime:
    """
    Adjusts `dt` to fall within an active shift of the machine.
    If machine is None or all shifts are active → return dt unchanged.
    """
    if machine is None:
        return dt

    if session is not None:
        active = get_active_shifts(session, machine.id_machine)
    else:
        active = _active_shifts_from_cap(machine.capacite_h_jour)

    if len(active) == 3:
        return dt   # 24h machine

    return _snap_to_active_shift(dt, active)


def _snap_to_active_shift(dt: datetime, active: set[int]) -> datetime:
    """
    Returns the earliest datetime >= dt that falls within an active shift.
    Handles the overnight shift (22h–6h next day) correctly.
    """
    # Try today first, then tomorrow
    for day_offset in range(10):
        base_date = dt.date() + timedelta(days=day_offset)
        for shift_idx in sorted(active):
            h_start, h_end = SHIFTS_DEF[shift_idx]
            if shift_idx == 2:  # overnight: 22h → 06h next day
                s_start = datetime.combine(base_date, h_start)
                s_end   = datetime.combine(base_date + timedelta(days=1), h_end)
            else:
                s_start = datetime.combine(base_date, h_start)
                s_end   = datetime.combine(base_date, h_end)

            if dt <= s_end and s_start >= dt.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1):
                candidate = max(dt, s_start)
                if candidate < s_end:
                    return candidate
    return dt  # fallback


def ajuster_date_fin_selon_plage_machine(
    date_debut: datetime,
    duree: timedelta,
    machine: Machine | None,
    session: Session | None = None
) -> tuple[datetime, datetime]:
    """
    Calcule (date_debut_ajustée, date_fin_ajustée) en respectant
    les shifts actifs de la machine.
    """
    if machine is None:
        return date_debut, date_debut + duree

    if session is not None:
        active = get_active_shifts(session, machine.id_machine)
    else:
        active = _active_shifts_from_cap(machine.capacite_h_jour)

    if len(active) == 3:
        return date_debut, date_debut + duree

    date_debut = _snap_to_active_shift(date_debut, active)

    restant      = duree
    date_courante = date_debut
    date_fin     = date_debut

    for _ in range(365 * 3):   # safety limit
        if restant <= timedelta(0):
            break

        # Find which shift covers date_courante
        shift_end = _shift_end_for(date_courante, active)
        if shift_end is None:
            # Not in any active shift — snap forward
            date_courante = _snap_to_active_shift(date_courante, active)
            continue

        dispo = shift_end - date_courante
        if restant <= dispo:
            date_fin = date_courante + restant
            restant  = timedelta(0)
        else:
            restant      -= dispo
            date_courante = _snap_to_active_shift(shift_end, active)

    return date_debut, date_fin


def _shift_end_for(dt: datetime, active: set[int]) -> datetime | None:
    """
    If dt falls inside an active shift, return the end of that shift.
    Otherwise return None.
    """
    for shift_idx in active:
        h_start, h_end = SHIFTS_DEF[shift_idx]
        if shift_idx == 2:  # overnight
            s_start = datetime.combine(dt.date(), h_start)
            s_end   = datetime.combine(dt.date() + timedelta(days=1), h_end)
            # also check if dt is in the morning part (before 6h)
            s_start2 = datetime.combine(dt.date() - timedelta(days=1), h_start)
            s_end2   = datetime.combine(dt.date(), h_end)
            if s_start2 <= dt < s_end2:
                return s_end2
            if s_start <= dt < s_end:
                return s_end
        else:
            s_start = datetime.combine(dt.date(), h_start)
            s_end   = datetime.combine(dt.date(), h_end)
            if s_start <= dt < s_end:
                return s_end
    return None


def get_prochaine_dispo_machine(
    session: Session,
    id_machine: int,
    apres: datetime,
    exclure_id_of: int = None,
    exclure_id_op_plan: int = None
) -> datetime:
    """
    Returns the earliest datetime >= apres when the machine is free.
    """
    q = session.query(OperationPlanifiee).filter(
        OperationPlanifiee.id_machine == id_machine,
        OperationPlanifiee.statut == "planifiee",
        OperationPlanifiee.date_fin > apres
    )
    if exclure_id_of is not None:
        q = q.filter(OperationPlanifiee.id_of != exclure_id_of)
    if exclure_id_op_plan is not None:
        q = q.filter(OperationPlanifiee.id_op_plan != exclure_id_op_plan)
    ops = q.all()
    ops.sort(key=lambda o: o.date_debut)

    dispo = apres
    for op in ops:
        if op.date_debut <= dispo:
            dispo = max(dispo, op.date_fin)
        else:
            break

    return dispo


def get_prochaine_dispo_service(
    session: Session,
    id_service: int,
    apres: datetime,
    exclure_id_of: int = None,
    exclure_id_op_plan: int = None
) -> datetime:
    """
    Returns the earliest datetime >= apres when the service is free.
    """
    q = session.query(OperationPlanifiee).filter(
        OperationPlanifiee.id_service == id_service,
        OperationPlanifiee.statut == "planifiee",
        OperationPlanifiee.date_fin > apres
    )
    if exclure_id_of is not None:
        q = q.filter(OperationPlanifiee.id_of != exclure_id_of)
    if exclure_id_op_plan is not None:
        q = q.filter(OperationPlanifiee.id_op_plan != exclure_id_op_plan)
    ops = q.all()
    ops.sort(key=lambda o: o.date_debut)

    dispo = apres
    for op in ops:
        if op.date_debut <= dispo:
            dispo = max(dispo, op.date_fin)
        else:
            break

    return dispo


def calculer_duree_operation(
    operation: Operation,
    quantite: float
) -> timedelta:
    """
    Calcule la durée totale d'une opération :
    tps_preparation + (tps_execution × quantite)
    Les temps sont en minutes dans la DB.
    """
    duree_minutes = operation.tps_preparation + (operation.tps_execution * quantite)
    return timedelta(minutes=duree_minutes)


def planifier_of(
    session: Session,
    id_of: int,
    date_debut_souhaitee: datetime = None
) -> list[OperationPlanifiee]:
    """
    Planifie toutes les opérations d'un OF au plus tôt.
    """
    of = session.get(OrdreFabrication, id_of)
    if not of:
        raise ValueError(f"Production order {id_of} not found")

    gamme = session.query(Gamme).filter_by(
        id_composant=of.id_composant,
        active=True
    ).first()

    if not gamme:
        raise ValueError(
            f"No active routing for component id={of.id_composant}"
        )

    if not gamme.operations:
        raise ValueError(
            f"La gamme du composant '{of.composant.nom}' "
            f"ne contient aucune opération. "
            f"Ajoutez au moins une opération avant de planifier."
        )

    date_courante = date_debut_souhaitee or datetime.now()

    if date_courante < datetime.now():
        date_courante = datetime.now()
        print(f"Start date is in the past — reset to now: "
              f"{str(date_courante)[:16]}")

    operations_planifiees = []

    for operation in gamme.operations:
        id_machine = operation.id_machine
        id_service  = operation.id_service
        machine_obj = session.get(Machine, id_machine) if id_machine else None

        # Mode multi_taches : on ignore la disponibilité de la ressource,
        # seule la contrainte de précédence (fin de l'op précédente) s'applique.
        machine_multi = machine_obj is not None and bool(machine_obj.multi_taches)
        service_multi = False
        if id_service and not id_machine:
            from models import Service as _Srv
            _srv = session.get(_Srv, id_service)
            service_multi = _srv is not None and bool(_srv.multi_taches)

        if machine_multi or service_multi:
            dispo = date_courante  # pas d'attente de disponibilité ressource
        elif id_machine:
            dispo = get_prochaine_dispo_machine(
                session=session,
                id_machine=id_machine,
                apres=date_courante
            )
        elif id_service:
            dispo = get_prochaine_dispo_service(
                session=session,
                id_service=id_service,
                apres=date_courante
            )
        else:
            dispo = date_courante

        date_debut_brut = max(date_courante, dispo)
        date_debut_brut = ajuster_selon_plage_machine(date_debut_brut, machine_obj)

        duree = calculer_duree_operation(operation, float(of.quantite))
        date_debut, date_fin = ajuster_date_fin_selon_plage_machine(
            date_debut_brut, duree, machine_obj
        )

        duree_minutes = round(duree.total_seconds() / 60)
        op_plan = OperationPlanifiee(
            id_of=of.id_of,
            id_operation=operation.id_operation,
            id_machine=id_machine,
            id_service=id_service,
            date_debut=date_debut,
            date_fin=date_fin,
            duree_reelle_min=duree_minutes,
            statut="planifiee"
        )
        session.add(op_plan)
        session.flush()

        operations_planifiees.append(op_plan)
        date_courante = date_fin

    of.statut = "planifie"
    of.date_lancement = operations_planifiees[0].date_debut if operations_planifiees else None
    of.date_fin_prevue = operations_planifiees[-1].date_fin if operations_planifiees else None

    print(f"OF {id_of} planifié : "
          f"{len(operations_planifiees)} opérations | "
          f"début={of.date_lancement} | fin={of.date_fin_prevue}")

    return operations_planifiees


def planifier_of_assemblage(
    session: Session,
    id_of_assemblage: int,
    date_debut_souhaitee: datetime = None
) -> dict:
    """
    Planifie tous les OFs composants d'un OFAssemblage.
    """
    from models import OFAssemblage

    of_assemblage = session.get(OFAssemblage, id_of_assemblage)
    if not of_assemblage:
        raise ValueError(f"OFAssemblage {id_of_assemblage} not found")

    session.expire(of_assemblage)
    of_assemblage = session.get(OFAssemblage, id_of_assemblage)

    date_debut = date_debut_souhaitee or datetime.now()
    resultats = []

    print(f"[Planning] OFAssemblage {id_of_assemblage} — {len(of_assemblage.ordres_fabrication)} OF(s) trouvés")

    for of in of_assemblage.ordres_fabrication:
        print(f"  OF {of.id_of} statut={of.statut}")
        if of.statut == "a_planifier":
            ops = planifier_of(
                session=session,
                id_of=of.id_of,
                date_debut_souhaitee=date_debut
            )
            resultats.append({
                "id_of": of.id_of,
                "composant": of.composant.nom,
                "nb_operations": len(ops),
                "date_debut": of.date_lancement,
                "date_fin": of.date_fin_prevue
            })

    of_assemblage.statut = "planifie"
    dates_fin = [r["date_fin"] for r in resultats if r["date_fin"] is not None]
    of_assemblage.date_fin_prevue = max(dates_fin) if dates_fin else None

    return {
        "id_of_assemblage": id_of_assemblage,
        "nb_ofs": len(resultats),
        "ofs": resultats,
        "date_fin_prevue": of_assemblage.date_fin_prevue
    }


def changer_machine(
    session: Session,
    id_op_plan: int,
    id_nouvelle_machine: int
) -> OperationPlanifiee:
    """
    Permet au gestionnaire de changer la machine assignée à une opération planifiée.
    """
    op_plan = session.get(OperationPlanifiee, id_op_plan)
    if not op_plan:
        raise ValueError(f"Planned operation {id_op_plan} not found")

    if op_plan.statut != "planifiee":
        raise ValueError(
            f"Cannot change machine: "
            f"operation has status '{op_plan.statut}'"
        )

    nouvelle_machine = session.get(Machine, id_nouvelle_machine)
    if not nouvelle_machine:
        raise ValueError(f"Machine {id_nouvelle_machine} not found")

    dispo = get_prochaine_dispo_machine(
        session=session,
        id_machine=id_nouvelle_machine,
        apres=op_plan.date_debut
    )

    operation = session.get(Operation, op_plan.id_operation)
    of = session.get(OrdreFabrication, op_plan.id_of)
    duree = calculer_duree_operation(operation, float(of.quantite))

    op_plan.id_machine = id_nouvelle_machine
    op_plan.date_debut = dispo
    op_plan.date_fin = dispo + duree

    print(f"Machine changée pour OperationPlanifiee {id_op_plan} : "
          f"machine {id_nouvelle_machine} | "
          f"nouveau début={op_plan.date_debut}")

    return op_plan


def valider_deplacement(
    session: Session,
    id_op_plan: int,
    nouvelle_date_debut: datetime,
    id_nouvelle_machine: int = None
) -> tuple[bool, str]:
    """
    Vérifie si le déplacement d'une opération est possible.
    """
    op = session.get(OperationPlanifiee, id_op_plan)
    if not op:
        return False, "Planned operation not found"

    if op.statut in ("terminee", "rebutee"):
        return False, f"Cannot reschedule an operation with status '{op.statut}'"

    id_machine_cible = id_nouvelle_machine or op.id_machine
    duree = op.date_fin - op.date_debut
    nouvelle_date_fin = nouvelle_date_debut + duree

    # Règle 1 — Contrainte gamme (opération précédente)
    of = session.get(OrdreFabrication, op.id_of)
    if of:
        gamme = session.query(Gamme).filter_by(
            id_composant=of.id_composant, active=True
        ).first()
        if gamme:
            op_precedente = session.query(OperationPlanifiee).join(
                Operation
            ).filter(
                OperationPlanifiee.id_of == op.id_of,
                Operation.ordre < op.operation.ordre
            ).order_by(Operation.ordre.desc()).first()

            if op_precedente:
                fin_precedente = (
                    op_precedente.date_fin_reelle
                    if op_precedente.date_fin_reelle
                    else op_precedente.date_fin
                )
                if fin_precedente and nouvelle_date_debut < fin_precedente:
                    return False, (
                        f"Routing constraint: previous operation "
                        f"'{op_precedente.operation.description}' "
                        f"ends at {str(fin_precedente)[:16]}.\n"
                        f"New start date ({str(nouvelle_date_debut)[:16]}) "
                        f"must be after this date."
                    )

    # Règle 2 — Contrainte machine (pas de chevauchement, sauf si multi_taches)
    if id_machine_cible:
        machine_cible = session.get(Machine, id_machine_cible)
        machine_multi = machine_cible is not None and bool(machine_cible.multi_taches)
        if not machine_multi:
            chevauchements = session.query(OperationPlanifiee).filter(
                OperationPlanifiee.id_machine == id_machine_cible,
                OperationPlanifiee.id_op_plan != id_op_plan,
                OperationPlanifiee.statut == "planifiee",
                OperationPlanifiee.date_debut < nouvelle_date_fin,
                OperationPlanifiee.date_fin > nouvelle_date_debut
            ).first()

            if chevauchements:
                return False, (
                    f"Machine conflict: machine is busy with "
                    f"PO {chevauchements.id_of} — "
                    f"'{chevauchements.operation.description}' "
                    f"from {str(chevauchements.date_debut)[:16]} "
                    f"to {str(chevauchements.date_fin)[:16]}"
                )

    # Règle 2b — Contrainte service (pas de chevauchement, sauf si multi_taches)
    id_service_cible = op.id_service
    if id_service_cible:
        from models import Service as _Srv
        service_cible = session.get(_Srv, id_service_cible)
        service_multi = service_cible is not None and bool(service_cible.multi_taches)
        if not service_multi:
            chevauchements = session.query(OperationPlanifiee).filter(
                OperationPlanifiee.id_service == id_service_cible,
                OperationPlanifiee.id_op_plan != id_op_plan,
                OperationPlanifiee.statut == "planifiee",
                OperationPlanifiee.date_debut < nouvelle_date_fin,
                OperationPlanifiee.date_fin > nouvelle_date_debut
            ).first()

            if chevauchements:
                return False, (
                    f"Service conflict: service is busy with "
                    f"PO {chevauchements.id_of} — "
                    f"'{chevauchements.operation.description}' "
                    f"from {str(chevauchements.date_debut)[:16]} "
                    f"to {str(chevauchements.date_fin)[:16]}"
                )

    return True, ""


def deplacer_operation(
    session: Session,
    id_op_plan: int,
    nouvelle_date_debut: datetime,
    id_nouvelle_machine: int = None,
    nouvelle_duree_minutes: int = None
) -> list[OperationPlanifiee]:
    """
    Déplace une opération (nouvelle date, machine, ou durée) et recalcule
    en cascade toutes les opérations impactées sur toutes les ressources.
    """
    op = session.get(OperationPlanifiee, id_op_plan)
    if not op:
        raise ValueError(f"Planned operation {id_op_plan} not found")

    if nouvelle_duree_minutes is not None:
        duree = timedelta(minutes=nouvelle_duree_minutes)
    else:
        duree = op.date_fin - op.date_debut

    modifiees = []

    # ── 1. Applique le déplacement sur l'op cible ─────────────────────
    print(f"[deplacer] op={id_op_plan} OF={op.id_of} "
          f"ancienne_debut={str(op.date_debut)[:16]} ancienne_fin={str(op.date_fin)[:16]} "
          f"nouvelle_debut={str(nouvelle_date_debut)[:16]} duree={int(duree.total_seconds()//60)}min")

    op.date_debut = nouvelle_date_debut
    op.date_fin   = nouvelle_date_debut + duree
    if id_nouvelle_machine:
        op.id_machine = id_nouvelle_machine
    machine_op = session.get(Machine, op.id_machine) if op.id_machine else None
    _, op.date_fin = ajuster_date_fin_selon_plage_machine(op.date_debut, duree, machine_op)
    modifiees.append(op)

    session.flush()

    of = session.get(OrdreFabrication, op.id_of)
    if not of:
        return modifiees

    ordre_deplace = op.operation.ordre

    # ── 2. Cascade dans la même gamme (ops suivantes du même OF) ──────
    ops_suivantes = session.query(OperationPlanifiee).join(
        Operation,
        OperationPlanifiee.id_operation == Operation.id_operation
    ).filter(
        OperationPlanifiee.id_of  == op.id_of,
        Operation.ordre           >  ordre_deplace,
        OperationPlanifiee.statut == "planifiee"
    ).order_by(Operation.ordre).all()

    print(f"[deplacer] {len(ops_suivantes)} op(s) suivante(s) dans la même gamme")

    date_courante = op.date_fin
    for op_suiv in ops_suivantes:
        duree_suiv   = op_suiv.date_fin - op_suiv.date_debut
        machine_suiv = session.get(Machine, op_suiv.id_machine) if op_suiv.id_machine else None

        if op_suiv.id_machine:
            dispo = get_prochaine_dispo_machine(
                session=session,
                id_machine=op_suiv.id_machine,
                apres=date_courante,
                exclure_id_of=op.id_of
            )
        elif op_suiv.id_service:
            dispo = get_prochaine_dispo_service(
                session=session,
                id_service=op_suiv.id_service,
                apres=date_courante,
                exclure_id_of=op.id_of
            )
        else:
            dispo = date_courante

        nouvelle_debut_suiv = max(date_courante, dispo)
        nouvelle_debut_suiv = ajuster_selon_plage_machine(nouvelle_debut_suiv, machine_suiv)
        print(f"  [cascade] op_suiv={op_suiv.id_op_plan} "
              f"ancienne={str(op_suiv.date_debut)[:16]} "
              f"date_courante={str(date_courante)[:16]} dispo={str(dispo)[:16]} "
              f"→ nouvelle={str(nouvelle_debut_suiv)[:16]}")

        _, fin_suiv = ajuster_date_fin_selon_plage_machine(nouvelle_debut_suiv, duree_suiv, machine_suiv)
        op_suiv.date_debut = nouvelle_debut_suiv
        op_suiv.date_fin   = fin_suiv
        date_courante      = op_suiv.date_fin
        modifiees.append(op_suiv)
        session.flush()

    # ── 3. Recalcul cross-gammes : conflit et récupération de gap ─────
    ressources_machines = {o.id_machine for o in modifiees if o.id_machine}
    ressources_services = {o.id_service for o in modifiees if o.id_service}
    ids_traites = {o.id_op_plan for o in modifiees}

    def _fin_op_precedente_gamme(op_r):
        prec = session.query(OperationPlanifiee).join(
            Operation, OperationPlanifiee.id_operation == Operation.id_operation
        ).filter(
            OperationPlanifiee.id_of  == op_r.id_of,
            Operation.ordre           <  op_r.operation.ordre,
            OperationPlanifiee.statut.in_(["planifiee", "en_cours", "terminee"])
        ).order_by(Operation.ordre.desc()).first()
        if prec is None:
            return None
        return prec.date_fin_reelle if prec.date_fin_reelle else prec.date_fin

    def _appliquer_op_cross(op_r, blocker_fin, id_machine=None, id_service=None):
        duree_r   = op_r.date_fin - op_r.date_debut
        fin_prec  = _fin_op_precedente_gamme(op_r)
        apres     = max(blocker_fin, fin_prec) if fin_prec else blocker_fin
        machine_r = session.get(Machine, id_machine) if id_machine else None

        if id_machine:
            dispo = get_prochaine_dispo_machine(
                session, id_machine, apres,
                exclure_id_op_plan=op_r.id_op_plan
            )
        else:
            dispo = get_prochaine_dispo_service(
                session, id_service, apres,
                exclure_id_op_plan=op_r.id_op_plan
            )
        nouvelle = ajuster_selon_plage_machine(max(apres, dispo), machine_r)

        if nouvelle == op_r.date_debut:
            ids_traites.add(op_r.id_op_plan)
            return False

        print(f"  [cross] op{op_r.id_op_plan} OF={op_r.id_of}: "
              f"{str(op_r.date_debut)[11:16]} → {str(nouvelle)[11:16]}"
              f"  (blocker_fin={str(blocker_fin)[11:16]}"
              f" fin_prec={str(fin_prec)[11:16] if fin_prec else 'None'})")
        op_r.date_debut = nouvelle
        _, op_r.date_fin = ajuster_date_fin_selon_plage_machine(nouvelle, duree_r, machine_r)
        modifiees.append(op_r)
        ids_traites.add(op_r.id_op_plan)
        session.flush()

        ordre_r   = op_r.operation.ordre
        suivantes = session.query(OperationPlanifiee).join(
            Operation, OperationPlanifiee.id_operation == Operation.id_operation
        ).filter(
            OperationPlanifiee.id_of  == op_r.id_of,
            Operation.ordre           >  ordre_r,
            OperationPlanifiee.statut == "planifiee"
        ).order_by(Operation.ordre).all()
        date_c = op_r.date_fin
        for op_s in suivantes:
            duree_s   = op_s.date_fin - op_s.date_debut
            machine_s = session.get(Machine, op_s.id_machine) if op_s.id_machine else None
            if op_s.id_machine:
                d = get_prochaine_dispo_machine(session, op_s.id_machine, date_c,
                                               exclure_id_of=op_r.id_of)
            elif op_s.id_service:
                d = get_prochaine_dispo_service(session, op_s.id_service, date_c,
                                               exclure_id_of=op_r.id_of)
            else:
                d = date_c
            debut_s = ajuster_selon_plage_machine(max(date_c, d), machine_s)
            _, fin_s = ajuster_date_fin_selon_plage_machine(debut_s, duree_s, machine_s)
            if debut_s != op_s.date_debut:
                op_s.date_debut = debut_s
                op_s.date_fin   = fin_s
                modifiees.append(op_s)
                session.flush()
            ids_traites.add(op_s.id_op_plan)
            if op_s.id_machine: ressources_machines.add(op_s.id_machine)
            if op_s.id_service: ressources_services.add(op_s.id_service)
            date_c = op_s.date_fin
        return True

    MAX_PASSES = 15
    for _pass in range(MAX_PASSES):
        modifs_ce_pass = 0

        for id_machine in list(ressources_machines):
            toutes = session.query(OperationPlanifiee).filter(
                OperationPlanifiee.id_machine == id_machine,
                OperationPlanifiee.statut     == "planifiee",
            ).all()
            toutes.sort(key=lambda o: o.date_debut)
            print(f"  [check machine={id_machine}] " +
                  " | ".join(f"op{o.id_op_plan}({str(o.date_debut)[11:16]}-{str(o.date_fin)[11:16]})" for o in toutes))
            for idx, op_r in enumerate(toutes):
                if op_r.id_op_plan in ids_traites:
                    continue
                blocker = None
                for prev in reversed(toutes[:idx]):
                    if prev.id_op_plan in ids_traites:
                        blocker = prev
                        break
                if blocker is None:
                    continue
                chevauchement   = op_r.date_debut < blocker.date_fin
                gap_recuperable = op_r.date_debut > blocker.date_fin
                if chevauchement or gap_recuperable:
                    if _appliquer_op_cross(op_r, blocker.date_fin, id_machine=id_machine):
                        modifs_ce_pass += 1

        for id_service in list(ressources_services):
            toutes = session.query(OperationPlanifiee).filter(
                OperationPlanifiee.id_service == id_service,
                OperationPlanifiee.statut     == "planifiee",
            ).all()
            toutes.sort(key=lambda o: o.date_debut)
            for idx, op_r in enumerate(toutes):
                if op_r.id_op_plan in ids_traites:
                    continue
                blocker = None
                for prev in reversed(toutes[:idx]):
                    if prev.id_op_plan in ids_traites:
                        blocker = prev
                        break
                if blocker is None:
                    continue
                chevauchement   = op_r.date_debut < blocker.date_fin
                gap_recuperable = op_r.date_debut > blocker.date_fin
                if chevauchement or gap_recuperable:
                    if _appliquer_op_cross(op_r, blocker.date_fin, id_service=id_service):
                        modifs_ce_pass += 1

        print(f"[deplacer] pass {_pass+1}: {modifs_ce_pass} modification(s)")
        if modifs_ce_pass == 0:
            break

    # ── 4. Mise à jour des dates de tous les OFs impactés ────────────
    session.flush()
    ids_of_modifies = {o.id_of for o in modifiees}
    for id_of_mod in ids_of_modifies:
        of_mod = session.get(OrdreFabrication, id_of_mod)
        if of_mod:
            session.expire(of_mod)
            of_mod = session.get(OrdreFabrication, id_of_mod)
            all_ops_mod = session.query(OperationPlanifiee).filter(
                OperationPlanifiee.id_of == id_of_mod
            ).all()
            ops_actives = [o for o in all_ops_mod if o.date_debut and o.date_fin]
            if ops_actives:
                of_mod.date_lancement  = min(o.date_debut for o in ops_actives)
                of_mod.date_fin_prevue = max(o.date_fin   for o in ops_actives)

    print(f"[deplacer] terminé : {len(modifiees)} ops recalculées sur {len(ids_of_modifies)} OF(s)")
    return modifiees


def recalculer_planning_global(session: Session) -> dict:
    """
    Replanifie au plus tôt TOUTES les opérations planifiées,
    en conservant les durées personnalisées (modifiées via le dialog).
    Recalcule aussi la date_fin des ops en_cours selon les shifts actifs.

    Ordre de replanification :
      Phase A — OFs dont au moins une opération est en_cours
                → triés par date_lancement (ancienneté), la fabrication a déjà commencé.
      Phase B — OFs entièrement en attente (aucune op en_cours)
                → triés par (priorité de l'OFAssemblage ASC, date_lancement ASC)
    """
    print("[recalcul_global] Démarrage...")

    # ── 0. Recalcule date_fin des ops en_cours ────────────────────────
    ops_en_cours = session.query(OperationPlanifiee).filter(
        OperationPlanifiee.statut == "en_cours"
    ).all()
    now = datetime.now()
    for op in ops_en_cours:
        if not op.id_machine or not op.operation or not op.of:
            continue
        machine_obj = session.get(Machine, op.id_machine)
        if not machine_obj:
            continue
        # Durée de référence : duree_reelle_min (saisie ou modifiée) sinon gamme
        if op.duree_reelle_min:
            duree_totale = timedelta(minutes=int(op.duree_reelle_min))
        else:
            duree_totale = calculer_duree_operation(op.operation, float(op.of.quantite))
        # Temps déjà travaillé depuis debut_reel
        debut_reel = op.date_debut_reelle or op.date_debut or now
        active = get_active_shifts(session, op.id_machine)
        deja = timedelta(minutes=_calculer_duree_travail(debut_reel, now, active))
        restant = duree_totale - deja
        if restant <= timedelta(0):
            restant = timedelta(minutes=1)
        _, nouvelle_fin = ajuster_date_fin_selon_plage_machine(
            now, restant, machine_obj, session)
        op.date_fin = nouvelle_fin
        print(f"  [en_cours] op {op.id_op_plan} duree_ref={int(duree_totale.total_seconds()/60)}min "
              f"deja={int(deja.total_seconds()/60)}min restant={int(restant.total_seconds()/60)}min "
              f"→ fin: {str(nouvelle_fin)[:16]}")
    session.flush()

    # ── 1. Collecte des OFs ayant des ops planifiées ──────────────────
    ofs_ids = session.query(OperationPlanifiee.id_of).filter(
        OperationPlanifiee.statut == "planifiee"
    ).distinct().all()
    ofs_ids = [r[0] for r in ofs_ids]

    ofs = []
    for id_of in ofs_ids:
        of = session.get(OrdreFabrication, id_of)
        if of and of.statut not in ("termine", "rebute"):
            ofs.append(of)

    # ── 2. Sépare OFs en cours vs entièrement en attente ─────────────
    # Un OF est "en cours" s'il a au moins une opération avec statut en_cours.
    ids_of_en_cours = {
        op.id_of for op in session.query(OperationPlanifiee).filter(
            OperationPlanifiee.statut == "en_cours"
        ).all()
    }

    ofs_commences  = [o for o in ofs if o.id_of in ids_of_en_cours]
    ofs_en_attente = [o for o in ofs if o.id_of not in ids_of_en_cours]

    # Phase A : ancienneté (fabrication déjà démarrée, on ne change pas l'ordre)
    ofs_commences.sort(key=lambda o: o.date_lancement or datetime.min)

    # Phase B : priorité assemblage ASC puis ancienneté ASC
    ofs_en_attente.sort(key=lambda o: (
        o.of_assemblage.priorite if o.of_assemblage else 5,
        o.date_lancement or datetime.min
    ))

    ofs_ordonnes = ofs_commences + ofs_en_attente
    print(f"[recalcul_global] {len(ofs_ordonnes)} OF(s) à replanifier "
          f"({len(ofs_commences)} en cours, {len(ofs_en_attente)} en attente)")

    # ── 3. Sauvegarde des durées personnalisées ───────────────────────
    durees_sauvegardees = {}
    for of in ofs_ordonnes:
        ops = session.query(OperationPlanifiee).filter(
            OperationPlanifiee.id_of  == of.id_of,
            OperationPlanifiee.statut == "planifiee"
        ).all()
        for op in ops:
            # Priorité : durée personnalisée (duree_reelle_min) si disponible,
            # sinon durée théorique de la gamme.
            if op.duree_reelle_min:
                duree_min = int(op.duree_reelle_min)
            elif op.operation:
                duree_min = round(calculer_duree_operation(
                    op.operation, float(of.quantite)
                ).total_seconds() / 60)
            else:
                duree_min = round(
                    (op.date_fin - op.date_debut).total_seconds() / 60)

            # ── Machine/service : toujours utiliser la gamme comme référence ──
            # Si l'opération planifiée a été glissée sur une mauvaise machine
            # (manuellement ou suite à un bug), on repart de la gamme lors d'un
            # recalcul global pour ne pas perpétuer l'erreur.
            gamme_id_machine = op.operation.id_machine if op.operation else None
            gamme_id_service = op.operation.id_service if op.operation else None
            durees_sauvegardees[(of.id_of, op.id_operation)] = {
                "duree_minutes": duree_min,
                "id_machine": gamme_id_machine,
                "id_service": gamme_id_service,
                "duree_reelle_min": op.duree_reelle_min,  # conserve le flag
            }
            print(f"  [save] OF={of.id_of} op={op.id_operation} "
                  f"durée={duree_min}min (custom={op.duree_reelle_min is not None}) "
                  f"machine={gamme_id_machine} service={gamme_id_service} "
                  f"[gamme ref — op had machine={op.id_machine} service={op.id_service}]")

    # ── 4. Supprime les anciennes ops planifiées ──────────────────────
    for of in ofs_ordonnes:
        ops_a_supprimer = session.query(OperationPlanifiee).filter(
            OperationPlanifiee.id_of  == of.id_of,
            OperationPlanifiee.statut == "planifiee"
        ).all()
        for op in ops_a_supprimer:
            session.delete(op)
    session.flush()
    print("[recalcul_global] Anciennes ops supprimées, replanification...")

    # ── 5. Replanifie dans l'ordre calculé ───────────────────────────
    nb_ops = 0
    now    = datetime.now()

    for of in ofs_ordonnes:
        gamme = session.query(Gamme).filter_by(
            id_composant=of.id_composant, active=True
        ).first()
        if not gamme:
            print(f"  OF {of.id_of} ERREUR: pas de gamme active")
            continue
        if not gamme.operations:
            print(f"  OF {of.id_of} ERREUR: gamme sans opérations")
            continue

        # Pour les OFs déjà commencés, la première op planifiée ne peut démarrer
        # qu'après la fin estimée de l'op en_cours de cet OF.
        fin_en_cours_of = datetime.min
        if of.id_of in ids_of_en_cours:
            op_ec = session.query(OperationPlanifiee).filter(
                OperationPlanifiee.id_of  == of.id_of,
                OperationPlanifiee.statut == "en_cours"
            ).order_by(OperationPlanifiee.date_fin.desc()).first()
            if op_ec and op_ec.date_fin:
                fin_en_cours_of = op_ec.date_fin

        date_courante     = max(now, fin_en_cours_of)
        ops_planifiees_of = []

        priorite_ofa = of.of_assemblage.priorite if of.of_assemblage else 5
        print(f"  OF {of.id_of} ({of.code_of}) — OFA priorité={priorite_ofa} "
              f"{'[en cours]' if of.id_of in ids_of_en_cours else '[en attente]'}")

        for operation in gamme.operations:
            sauvegarde = durees_sauvegardees.get((of.id_of, operation.id_operation))

            if sauvegarde:
                duree      = timedelta(minutes=sauvegarde["duree_minutes"])
                id_machine = sauvegarde["id_machine"]
                id_service = sauvegarde["id_service"]
            else:
                duree      = calculer_duree_operation(operation, float(of.quantite))
                id_machine = operation.id_machine
                id_service = operation.id_service

            machine_obj = session.get(Machine, id_machine) if id_machine else None

            # Mode multi_taches : on ignore la disponibilité de la ressource
            machine_multi = machine_obj is not None and bool(machine_obj.multi_taches)
            service_multi = False
            if id_service and not id_machine:
                from models import Service as _Srv
                _srv = session.get(_Srv, id_service)
                service_multi = _srv is not None and bool(_srv.multi_taches)

            if machine_multi or service_multi:
                dispo = date_courante
            elif id_machine:
                dispo = get_prochaine_dispo_machine(session, id_machine, date_courante)
            elif id_service:
                dispo = get_prochaine_dispo_service(session, id_service, date_courante)
            else:
                dispo = date_courante

            date_debut_brut = max(date_courante, dispo)
            date_debut_brut = ajuster_selon_plage_machine(date_debut_brut, machine_obj)
            date_debut, date_fin = ajuster_date_fin_selon_plage_machine(
                date_debut_brut, duree, machine_obj
            )

            # Conserve le flag de durée personnalisée
            saved_duree_reelle_min = sauvegarde.get("duree_reelle_min") if sauvegarde else None

            op_plan = OperationPlanifiee(
                id_of            = of.id_of,
                id_operation     = operation.id_operation,
                id_machine       = id_machine,
                id_service       = id_service,
                date_debut       = date_debut,
                date_fin         = date_fin,
                duree_reelle_min = saved_duree_reelle_min,
                statut           = "planifiee"
            )
            session.add(op_plan)
            session.flush()
            ops_planifiees_of.append(op_plan)
            date_courante = date_fin

        nb_ops += len(ops_planifiees_of)
        if ops_planifiees_of:
            of.statut          = "planifie"
            of.date_lancement  = ops_planifiees_of[0].date_debut
            of.date_fin_prevue = ops_planifiees_of[-1].date_fin
            print(f"    → {len(ops_planifiees_of)} op(s) : "
                  f"{str(of.date_lancement)[:16]} … {str(of.date_fin_prevue)[:16]}")

    # Propage date_fin_prevue sur chaque OFAssemblage impacté
    ids_ofa_modifies = {of.id_of_assemblage for of in ofs_ordonnes if of.id_of_assemblage}
    from models.production import OFAssemblage as _OFA
    for id_ofa in ids_ofa_modifies:
        ofa = session.get(_OFA, id_ofa)
        if ofa:
            dates = [o.date_fin_prevue for o in ofa.ordres_fabrication if o.date_fin_prevue]
            if dates:
                ofa.date_fin_prevue = max(dates)

    session.flush()
    print(f"[recalcul_global] Terminé : {len(ofs_ordonnes)} OFs, {nb_ops} ops replanifiées")
    return {"nb_ofs": len(ofs_ordonnes), "nb_ops": nb_ops}


def _calculer_duree_travail(date_debut: datetime, date_fin: datetime,
                            active: set[int]) -> int:
    """
    Calcule la durée de travail en minutes entre date_debut et date_fin,
    en ne comptant que les heures dans les shifts actifs.
    """
    if len(active) == 3:
        return int((date_fin - date_debut).total_seconds() / 60)

    total = 0
    cur = date_debut
    while cur < date_fin:
        shift_end = _shift_end_for(cur, active)
        if shift_end is None:
            # Pas dans un shift actif → avancer au prochain
            next_slot = _snap_to_active_shift(cur, active)
            if next_slot <= cur:
                break  # sécurité
            cur = next_slot
            continue
        segment_end = min(shift_end, date_fin)
        total += int((segment_end - cur).total_seconds() / 60)
        cur = segment_end
    return total


def recalculer_planning_machine(session: Session, id_machine: int) -> dict:
    """
    Replanifie toutes les opérations futures d'une machine après changement de shifts.
    - Les ops 'en_cours' : recalcule leur date_fin avec les nouveaux shifts
      (la date_debut_reelle reste inchangée)
    - Les ops 'planifiee' : recalcule debut et fin au plus tôt
    """
    print(f"[recalcul_machine] machine={id_machine}")

    machine_obj = session.get(Machine, id_machine)
    if not machine_obj:
        raise ValueError(f"Machine {id_machine} introuvable")

    # Sauvegarde les anciens shifts AVANT de lire les nouveaux
    # (get_active_shifts lit la DB qui vient d'être mise à jour par set_shift_active)
    new_active = get_active_shifts(session, id_machine)
    # Pour calculer les durées de travail des anciennes planifications,
    # on utilise capacite_h_jour comme proxy des anciens shifts
    cap_active = _active_shifts_from_cap(machine_obj.capacite_h_jour)

    # ── 1. Recalcule date_fin des ops en_cours ────────────────────────
    ops_en_cours = session.query(OperationPlanifiee).filter(
        OperationPlanifiee.id_machine == id_machine,
        OperationPlanifiee.statut     == "en_cours",
    ).all()

    for op in ops_en_cours:
        debut_reel = op.date_debut_reelle or op.date_debut or datetime.now()
        now = datetime.now()

        # Durée totale de travail prévue (en minutes de travail effectif)
        stored = getattr(op, 'duree_reelle_min', None)
        if stored:
            duree_totale = timedelta(minutes=int(stored))
        elif op.date_debut and op.date_fin:
            # Calcule depuis les dates planifiées avec les anciens shifts (capacite_h_jour)
            duree_travail = _calculer_duree_travail(op.date_debut, op.date_fin, cap_active)
            duree_totale = timedelta(minutes=max(duree_travail, 1))
        else:
            continue

        # Temps déjà travaillé avec les anciens shifts (avant la modif)
        deja_travaille = timedelta(minutes=_calculer_duree_travail(
            debut_reel, now, cap_active))

        restant = duree_totale - deja_travaille
        if restant <= timedelta(0):
            restant = timedelta(minutes=1)

        # Recalcule date_fin depuis maintenant avec les NOUVEAUX shifts
        _, nouvelle_fin = ajuster_date_fin_selon_plage_machine(
            now, restant, machine_obj, session)
        op.date_fin = nouvelle_fin
        session.flush()
        print(f"  [en_cours] op {op.id_op_plan} → fin recalculée : {str(nouvelle_fin)[:16]}")

    # ── 2. Recalcule les ops planifiee ────────────────────────────────
    ops = session.query(OperationPlanifiee).filter(
        OperationPlanifiee.id_machine == id_machine,
        OperationPlanifiee.statut     == "planifiee",
    ).order_by(OperationPlanifiee.date_debut).all()

    if not ops:
        return {"nb_ops": len(ops_en_cours)}

    # Calcule les durées de travail avec les anciens shifts (capacite_h_jour)
    durees = {}
    for op in ops:
        stored = getattr(op, 'duree_reelle_min', None)
        if stored:
            durees[op.id_op_plan] = timedelta(minutes=int(stored))
        elif op.date_debut and op.date_fin:
            duree_travail = _calculer_duree_travail(op.date_debut, op.date_fin, cap_active)
            durees[op.id_op_plan] = timedelta(minutes=max(duree_travail, 1))
        else:
            durees[op.id_op_plan] = timedelta(0)

    # Replanifie chaque op en respectant les nouveaux shifts
    now = datetime.now()
    date_courante = now
    nb_ops = 0

    # Group by OF to maintain routing order within each OF
    # But also respect inter-OF ordering on this machine → process in date order
    ids_of_modifies = set()
    for op in ops:
        duree = durees[op.id_op_plan]

        # Respect routing: op cannot start before the previous op of same OF finishes
        ops_precedentes_of = session.query(OperationPlanifiee).join(
            Operation
        ).filter(
            OperationPlanifiee.id_of       == op.id_of,
            Operation.ordre                < op.operation.ordre,
            OperationPlanifiee.statut.in_(["planifiee", "en_cours", "terminee"])
        ).order_by(Operation.ordre.desc()).first()

        date_min_of = datetime.min
        if ops_precedentes_of:
            date_min_of = ops_precedentes_of.date_fin or datetime.min

        dispo_machine = get_prochaine_dispo_machine(
            session, id_machine, date_courante,
            exclure_id_op_plan=op.id_op_plan
        )

        date_debut_brut = max(now, date_min_of, dispo_machine)
        date_debut_brut = ajuster_selon_plage_machine(date_debut_brut, machine_obj, session)
        date_debut, date_fin = ajuster_date_fin_selon_plage_machine(
            date_debut_brut, duree, machine_obj, session
        )

        op.date_debut = date_debut
        op.date_fin   = date_fin
        session.flush()

        date_courante = date_fin
        ids_of_modifies.add(op.id_of)
        nb_ops += 1
        print(f"  op {op.id_op_plan} → {str(date_debut)[:16]} … {str(date_fin)[:16]}")

    # Mise à jour date_fin_prevue de chaque OF touché
    for id_of_mod in ids_of_modifies:
        of_mod = session.get(OrdreFabrication, id_of_mod)
        if of_mod:
            all_ops = session.query(OperationPlanifiee).filter(
                OperationPlanifiee.id_of == id_of_mod
            ).all()
            ops_actives = [o for o in all_ops if o.date_debut and o.date_fin]
            if ops_actives:
                of_mod.date_lancement  = min(o.date_debut for o in ops_actives)
                of_mod.date_fin_prevue = max(o.date_fin   for o in ops_actives)

    session.flush()
    print(f"[recalcul_machine] Terminé : {nb_ops} ops planifiées + {len(ops_en_cours)} en_cours recalculées sur {len(ids_of_modifies)} OF(s)")
    return {"nb_ops": nb_ops + len(ops_en_cours), "nb_ofs": len(ids_of_modifies)}


def calculer_duree_travail_reelle_op(date_debut: datetime, date_fin: datetime, plage) -> int:
    """
    Calcule la durée de travail réelle en minutes entre date_debut et date_fin,
    en excluant les heures hors plage.
    """
    h_debut, h_fin = plage

    total = 0
    courant = date_debut
    while courant.date() <= date_fin.date():
        debut_plage = datetime.combine(courant.date(), h_debut)
        fin_plage   = datetime.combine(courant.date(), h_fin)
        debut_eff   = max(courant, debut_plage)
        fin_eff     = min(date_fin, fin_plage)
        if fin_eff > debut_eff:
            total += int((fin_eff - debut_eff).total_seconds() / 60)
        courant = datetime.combine(courant.date() + timedelta(days=1), h_debut)
    return total