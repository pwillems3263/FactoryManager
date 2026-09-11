from sqlalchemy.orm import Session
from models import Nomenclature, Composant


def exploser_nomenclature(
    session: Session,
    id_parent: int,
    type_parent: str,
    quantite_parent: float = 1.0
) -> list[dict]:
    """
    Explose récursivement la nomenclature d'un assemblage ou composant.

    Retourne une liste de dicts :
    [
        {
            "id_composant": 12,
            "nom": "Bride",
            "quantite_totale": 20.0
        },
        ...
    ]
    Seuls les composants feuilles (sans sous-composants) sont retournés.
    """
    resultats = []

    # Récupère les lignes de nomenclature pour ce parent
    lignes = session.query(Nomenclature).filter_by(
        id_parent=id_parent,
        type_parent=type_parent
    ).all()

    if not lignes:
        # Pas de sous-composants → c'est un composant feuille
        # (cas terminal de la récursion)
        return resultats

    for ligne in lignes:
        quantite_courante = quantite_parent * float(ligne.quantite)

        # Skip services and external parts — only composants generate production orders
        if ligne.id_composant is None:
            continue

        # Vérifie si ce composant a lui-même des sous-composants
        sous_lignes = session.query(Nomenclature).filter_by(
            id_parent=ligne.id_composant,
            type_parent="composant"
        ).all()

        if sous_lignes:
            # Ce composant est un sous-assemblage → on descend
            sous_resultats = exploser_nomenclature(
                session=session,
                id_parent=ligne.id_composant,
                type_parent="composant",
                quantite_parent=quantite_courante
            )
            resultats.extend(sous_resultats)
        else:
            # Composant feuille → on l'ajoute au résultat
            composant = session.get(Composant, ligne.id_composant)
            if not composant:
                raise ValueError(
                    f"Component with id={ligne.id_composant} not found in database"
                )
            resultats.append({
                "id_composant": ligne.id_composant,
                "nom": composant.nom,
                "quantite_totale": quantite_courante
            })

    return resultats


def exploser_pour_commande(
    session: Session,
    id_assemblage: int,
    quantite_commandee: float
) -> list[dict]:
    """
    Point d'entrée principal.
    Explose la nomenclature d'un assemblage pour une quantité commandée.

    Exemple :
        exploser_pour_commande(session, id_assemblage=7, quantite_commandee=10)
        → [{"id_composant": 12, "nom": "Bride", "quantite_totale": 20.0}, ...]
    """
    resultats = exploser_nomenclature(
        session=session,
        id_parent=id_assemblage,
        type_parent="assemblage",
        quantite_parent=quantite_commandee
    )

    # Regroupe les composants identiques si présents dans plusieurs branches
    regroupes = {}
    for item in resultats:
        cle = item["id_composant"]
        if cle in regroupes:
            regroupes[cle]["quantite_totale"] += item["quantite_totale"]
        else:
            regroupes[cle] = item.copy()

    return list(regroupes.values())