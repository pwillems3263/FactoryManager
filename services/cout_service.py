import math
from sqlalchemy.orm import Session
from models import Composant, Gamme, Operation, Machine, Assemblage, Nomenclature


def format_prix(valeur) -> str:
    """Formate un prix avec séparateur de milliers."""
    if valeur is None:
        return "—"
    return f"{float(valeur):,.2f} €".replace(",", "\u202f")


def calculer_cout_matiere(composant: Composant) -> float:
    """Calcule le coût matière selon la forme et les dimensions."""
    if not composant.id_matiere_brut or not composant.forme_brut:
        return 0.0

    matiere = composant.matiere_brut
    if not matiere or not matiere.poids_volumique or not matiere.prix_au_kg:
        return 0.0

    volume_cm3 = 0.0
    forme = composant.forme_brut

    if forme == "axe":
        if composant.brut_diametre and composant.brut_longueur:
            r = float(composant.brut_diametre) / 2 / 10
            l = float(composant.brut_longueur) / 10
            volume_cm3 = math.pi * r ** 2 * l

    elif forme == "tube":
        if (composant.brut_diam_ext and composant.brut_diam_int
                and composant.brut_longueur):
            r_ext = float(composant.brut_diam_ext) / 2 / 10
            r_int = float(composant.brut_diam_int) / 2 / 10
            l     = float(composant.brut_longueur) / 10
            volume_cm3 = math.pi * (r_ext ** 2 - r_int ** 2) * l

    elif forme == "plaque":
        if (composant.brut_largeur and composant.brut_hauteur
                and composant.brut_epaisseur):
            la = float(composant.brut_largeur) / 10
            ha = float(composant.brut_hauteur) / 10
            ep = float(composant.brut_epaisseur) / 10
            volume_cm3 = la * ha * ep

    if volume_cm3 <= 0:
        return 0.0

    masse_kg = volume_cm3 * float(matiere.poids_volumique)
    return round(masse_kg * float(matiere.prix_au_kg), 4)


def calculer_cout_operations(
    session: Session,
    composant: Composant,
    quantite: float = 1.0
) -> float:
    """Calcule le coût total des opérations (machine + opérateur + services + pièces externes)."""
    gamme = session.query(Gamme).filter_by(
        id_composant=composant.id_composant,
        active=True
    ).first()

    if not gamme:
        return 0.0

    cout_total = 0.0

    for op in gamme.operations:
        # Coût machine + opérateur
        if op.machine:
            machine = op.machine
            tps_prep = float(op.tps_preparation or 0)
            tps_exec = float(op.tps_execution or 0)
            duree_h  = (tps_prep + tps_exec * quantite) / 60.0

            if machine.tarif_horaire:
                cout_total += duree_h * float(machine.tarif_horaire)

            if machine.cout_operateur and machine.charge_operateur:
                charge = float(machine.charge_operateur) / 100.0
                cout_total += duree_h * float(machine.cout_operateur) * charge

        # Coût service
        elif op.service:
            s = op.service
            if s.cout_horaire:
                tps_exec = float(op.tps_execution or 0)
                duree_h  = (tps_exec * quantite) / 60.0
                cout_total += duree_h * float(s.cout_horaire)
            elif s.cout_fixe:
                cout_total += float(s.cout_fixe) * quantite

        # Coût pièce externe
        elif op.piece_externe:
            p = op.piece_externe
            if p.prix_unitaire:
                cout_total += float(p.prix_unitaire) * quantite

    return round(cout_total, 4)


def calculer_prix_revient(
    session: Session,
    id_composant: int,
    quantite: float = 1.0
) -> dict:
    """Calcule le prix de revient complet d'un composant."""
    composant = session.get(Composant, id_composant)
    if not composant:
        return {"total": 0.0, "matiere": 0.0, "operations": 0.0, "composant": "—"}

    cout_mat = calculer_cout_matiere(composant)
    cout_ops = calculer_cout_operations(session, composant, quantite)
    total    = round(cout_mat + cout_ops, 4)

    return {
        "total":      total,
        "matiere":    cout_mat,
        "operations": cout_ops,
        "composant":  composant.nom,
        "quantite":   quantite,
    }


def recalculer_et_sauvegarder_composant(
    session: Session,
    id_composant: int
) -> float:
    """
    Recalcule et sauvegarde le prix de revient d'un composant.
    Retourne le nouveau prix.
    """
    composant = session.get(Composant, id_composant)
    if not composant:
        return 0.0

    result = calculer_prix_revient(session, id_composant, quantite=1.0)
    composant.prix_revient = result["total"]

    print(f"Composant '{composant.nom}' → prix_revient = {result['total']:.4f} €")
    return result["total"]


def recalculer_assemblage(
    session: Session,
    id_assemblage: int
) -> float:
    """
    Recalcule et sauvegarde le prix de revient d'un assemblage.
    Somme des prix des composants × quantités + pièces externes + services.
    Retourne le nouveau prix.
    """
    assemblage = session.get(Assemblage, id_assemblage)
    if not assemblage:
        return 0.0

    nomenclatures = session.query(Nomenclature).filter_by(
        id_parent=id_assemblage,
        type_parent="assemblage"
    ).all()

    total = 0.0
    for n in nomenclatures:
        qte = float(n.quantite)

        if n.composant and n.composant.prix_revient:
            total += float(n.composant.prix_revient) * qte

        elif n.piece_externe and n.piece_externe.prix_unitaire:
            total += float(n.piece_externe.prix_unitaire) * qte

        elif n.service:
            s = n.service
            # Services in BOM use a fixed cost × quantity (simple and predictable)
            if s.cout_fixe:
                total += float(s.cout_fixe) * qte

    assemblage.prix_revient = round(total, 4)
    print(f"Assemblage '{assemblage.nom}' → prix_revient = {total:.4f} €")
    return round(total, 4)


def recalculer_composants_par_machine(
    session: Session,
    id_machine: int
):
    """
    Recalcule tous les composants qui utilisent cette machine.
    Appelé quand le tarif d'une machine change.
    """
    ops = session.query(Operation).filter_by(id_machine=id_machine).all()
    id_composants = set()

    for op in ops:
        if op.gamme and op.gamme.active:
            id_composants.add(op.gamme.id_composant)

    for id_c in id_composants:
        recalculer_et_sauvegarder_composant(session, id_c)
        _recalculer_assemblages_du_composant(session, id_c)

    print(f"Machine {id_machine} → {len(id_composants)} composant(s) recalculé(s)")


def recalculer_composants_par_matiere(
    session: Session,
    id_matiere: int
):
    """
    Recalcule tous les composants qui utilisent cette matière.
    Appelé quand le prix d'une matière change.
    """
    composants = session.query(Composant).filter_by(
        id_matiere_brut=id_matiere
    ).all()

    for c in composants:
        recalculer_et_sauvegarder_composant(session, c.id_composant)
        _recalculer_assemblages_du_composant(session, c.id_composant)

    print(f"Matière {id_matiere} → {len(composants)} composant(s) recalculé(s)")


def _recalculer_assemblages_du_composant(
    session: Session,
    id_composant: int
):
    """Recalcule tous les assemblages qui contiennent ce composant."""
    nomenclatures = session.query(Nomenclature).filter_by(
        id_composant=id_composant,
        type_parent="assemblage"
    ).all()

    id_assemblages = set(n.id_parent for n in nomenclatures)
    for id_a in id_assemblages:
        recalculer_assemblage(session, id_a)

def recalculer_composants_par_service(session: Session, id_service: int):
    """Recalcule tous les composants qui utilisent ce service dans leur gamme."""
    from models import Operation, Gamme
    ops = session.query(Operation).filter_by(id_service=id_service).all()
    id_composants = set()
    for op in ops:
        gamme = session.get(Gamme, op.id_gamme)
        if gamme and gamme.active:
            id_composants.add(gamme.id_composant)
    for id_c in id_composants:
        recalculer_et_sauvegarder_composant(session, id_c)
        _recalculer_assemblages_du_composant(session, id_c)
    print(f"Service {id_service} → {len(id_composants)} composant(s) recalculé(s)")


def recalculer_composants_par_piece_externe(session: Session, id_piece_externe: int):
    """Recalcule tous les composants qui utilisent cette pièce externe dans leur gamme."""
    from models import Operation, Gamme
    ops = session.query(Operation).filter_by(id_piece_externe=id_piece_externe).all()
    id_composants = set()
    for op in ops:
        gamme = session.get(Gamme, op.id_gamme)
        if gamme and gamme.active:
            id_composants.add(gamme.id_composant)
    for id_c in id_composants:
        recalculer_et_sauvegarder_composant(session, id_c)
        _recalculer_assemblages_du_composant(session, id_c)
    print(f"Pièce externe {id_piece_externe} → {len(id_composants)} composant(s) recalculé(s)")