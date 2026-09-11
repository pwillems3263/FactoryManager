from datetime import datetime
from sqlalchemy.orm import Session
from models import LigneCommande, OFAssemblage, OrdreFabrication, Gamme
from services.bom_service import exploser_pour_commande

def generer_code_commande(session, date_commande):
    """
    Génère le code commande YYMM-OOO.
    Recherche le plus grand numéro existant pour le mois en cours.
    """
    from models import Commande
    yymm = date_commande.strftime("%y%m")

    dernier = session.query(Commande).filter(
        Commande.code_commande.like(f"{yymm}-%")
    ).order_by(Commande.code_commande.desc()).first()

    if dernier and dernier.code_commande:
        numero = int(dernier.code_commande.split("-")[1]) + 1
    else:
        numero = 1

    return f"{yymm}-{numero:03d}"


def generer_code_ligne(code_commande, numero_ligne):
    """
    Génère le code ligne YYMM-OOO-LL.
    numero_ligne : position séquentielle de la ligne dans la commande (1, 2, 3...)
    """
    return f"{code_commande}-{numero_ligne:02d}"


def generer_code_of(code_ligne, numero_composant):
    """
    Génère le code OF YYMM-OOO-LL-CC.
    numero_composant : position séquentielle du composant dans la ligne (1, 2, 3...)
    """
    return f"{code_ligne}-{numero_composant:02d}"


def generer_of_depuis_ligne(
    session: Session,
    id_ligne: int
) -> OFAssemblage:
    """
    Génère un OFAssemblage et tous les OFs composants
    à partir d'une LigneCommande.
    """
    from models import Commande

    # 1. Récupère la ligne de commande
    ligne = session.get(LigneCommande, id_ligne)
    if not ligne:
        raise ValueError(f"Order line {id_ligne} not found")

    # 2. Génère le code ligne si pas encore fait
    if not ligne.code_ligne:
        # Compte les lignes existantes dans cette commande
        from models import LigneCommande as LC
        nb_lignes = session.query(LC).filter_by(
            id_commande=ligne.id_commande
        ).count()
        ligne.code_ligne = generer_code_ligne(
            ligne.commande.code_commande,
            nb_lignes
        )

    # 3. Crée l'OFAssemblage
    of_assemblage = OFAssemblage(
        id_ligne=ligne.id_ligne,
        id_assemblage=ligne.id_assemblage,
        quantite=ligne.quantite,
        date_lancement=datetime.now(),
        statut="planifie"
    )
    session.add(of_assemblage)
    session.flush()

    # 4. Explose la BOM
    composants = exploser_pour_commande(
        session=session,
        id_assemblage=ligne.id_assemblage,
        quantite_commandee=float(ligne.quantite)
    )

    if not composants:
        raise ValueError(
            f"No component found in the bill of materials "
            f"for assembly {ligne.id_assemblage}"
        )

    # 5. Crée un OF par composant feuille avec code de traçabilité
    ofs_crees = []
    for numero, item in enumerate(composants, start=1):

        gamme = session.query(Gamme).filter_by(
            id_composant=item["id_composant"],
            active=True
        ).first()

        if not gamme:
            raise ValueError(
                f"No active routing found for component "
                f"'{item['nom']}' (id={item['id_composant']})"
            )

        # Génère le code OF
        code_of = generer_code_of(ligne.code_ligne, numero)

        of = OrdreFabrication(
            id_of_assemblage=of_assemblage.id_of_assemblage,
            id_composant=item["id_composant"],
            type_of="normal",
            quantite=item["quantite_totale"],
            date_lancement=datetime.now(),
            statut="a_planifier",
            code_of=code_of
        )
        session.add(of)
        ofs_crees.append(of)

    session.flush()

    print(f"OFAssemblage {of_assemblage.id_of_assemblage} créé")
    print(f"{len(ofs_crees)} OFs composants créés :")
    for of in ofs_crees:
        print(f"  → {of.code_of} | Composant id={of.id_composant} "
              f"| qte={of.quantite}")

    return of_assemblage


def generer_of_retouche(
    session: Session,
    id_of_original: int,
    quantite_rebutee: float
) -> OrdreFabrication:
    """
    Génère un OF de retouche à partir d'un OF original suite à un rebut.
    """
    of_original = session.get(OrdreFabrication, id_of_original)
    if not of_original:
        raise ValueError(f"Production order {id_of_original} not found")

    of_retouche = OrdreFabrication(
        id_of_assemblage=of_original.id_of_assemblage,
        id_composant=of_original.id_composant,
        id_of_parent=of_original.id_of,
        type_of="retouche",
        quantite=quantite_rebutee,
        date_lancement=datetime.now(),
        statut="a_planifier"
    )
    session.add(of_retouche)
    session.flush()

    print(f"OF retouche {of_retouche.id_of} créé "
          f"depuis OF original {id_of_original} "
          f"| qte={quantite_rebutee}")

    return of_retouche