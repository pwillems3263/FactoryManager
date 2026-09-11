from datetime import datetime, date
from database import SessionLocal
from models import (
    Commande, LigneCommande, Assemblage, Composant,
    Nomenclature, Machine, Gamme, Operation
)
from services.of_service import generer_of_depuis_ligne
from services.planning_service import planifier_of_assemblage
from services.rebut_service import (
    pointer_debut_operation,
    pointer_fin_operation,
    constater_rebut
)


def creer_donnees_test(session):
    """
    Crée un jeu de données minimal pour tester la chaîne complète :
    Machine → Composant → Gamme → Opérations
    Assemblage → Nomenclature
    Commande → LigneCommande
    """
    print("\n=== CRÉATION DES DONNÉES DE TEST ===")

    # 1. Machines
    tour = Machine(nom="Tour CN 1", type="tournage",
                   capacite_h_jour=8, statut="disponible")
    fraiseuse = Machine(nom="Fraiseuse 5 axes", type="fraisage",
                        capacite_h_jour=8, statut="disponible")
    session.add_all([tour, fraiseuse])
    session.flush()
    print(f"Machines créées : {tour.nom} (id={tour.id_machine}), "
          f"{fraiseuse.nom} (id={fraiseuse.id_machine})")

    # 2. Composants
    bride = Composant(nom="Bride", type="usine")
    chapeau = Composant(nom="Chapeau", type="usine")
    session.add_all([bride, chapeau])
    session.flush()
    print(f"Composants créés : {bride.nom} (id={bride.id_composant}), "
          f"{chapeau.nom} (id={chapeau.id_composant})")

    # 3. Gammes et Opérations
    gamme_bride = Gamme(id_composant=bride.id_composant, version=1, active=True)
    session.add(gamme_bride)
    session.flush()

    op1 = Operation(
        id_gamme=gamme_bride.id_gamme,
        id_machine=tour.id_machine,
        ordre=1,
        description="Tournage ébauche",
        tps_preparation=15,
        tps_execution=10
    )
    op2 = Operation(
        id_gamme=gamme_bride.id_gamme,
        id_machine=fraiseuse.id_machine,
        ordre=2,
        description="Fraisage finition",
        tps_preparation=10,
        tps_execution=8
    )
    session.add_all([op1, op2])

    gamme_chapeau = Gamme(id_composant=chapeau.id_composant, version=1, active=True)
    session.add(gamme_chapeau)
    session.flush()

    op3 = Operation(
        id_gamme=gamme_chapeau.id_gamme,
        id_machine=tour.id_machine,
        ordre=1,
        description="Tournage chapeau",
        tps_preparation=10,
        tps_execution=12
    )
    session.add(op3)
    session.flush()
    print("Gammes et opérations créées")

    # 4. Assemblage + Nomenclature
    vanne = Assemblage(nom="Vanne DN50", reference="VAN-DN50")
    session.add(vanne)
    session.flush()

    nom1 = Nomenclature(
        id_parent=vanne.id_assemblage,
        type_parent="assemblage",
        id_composant=bride.id_composant,
        quantite=2
    )
    nom2 = Nomenclature(
        id_parent=vanne.id_assemblage,
        type_parent="assemblage",
        id_composant=chapeau.id_composant,
        quantite=1
    )
    session.add_all([nom1, nom2])
    session.flush()
    print(f"Assemblage créé : {vanne.nom} (id={vanne.id_assemblage})")
    print(f"  → 2x Bride + 1x Chapeau")

    # 5. Commande + LigneCommande
    commande = Commande(
        date_commande=date.today(),
        client="Client Test SA",
        statut="planifiee"
    )
    session.add(commande)
    session.flush()

    ligne = LigneCommande(
        id_commande=commande.id_commande,
        id_assemblage=vanne.id_assemblage,
        quantite=5
    )
    session.add(ligne)
    session.flush()
    print(f"Commande créée : {commande.client} | "
          f"5x {vanne.nom} (ligne id={ligne.id_ligne})")

    return ligne


def main():
    session = SessionLocal()
    try:
        # ÉTAPE 1 — Données de test
        ligne = creer_donnees_test(session)

        # ÉTAPE 2 — Génération des OFs
        print("\n=== GÉNÉRATION DES OFs ===")
        of_assemblage = generer_of_depuis_ligne(session, ligne.id_ligne)

        # ÉTAPE 3 — Planification
        print("\n=== PLANIFICATION ===")
        resultat = planifier_of_assemblage(
            session=session,
            id_of_assemblage=of_assemblage.id_of_assemblage,
            date_debut_souhaitee=datetime.now()
        )
        print(f"Planification terminée : {resultat['nb_ofs']} OFs planifiés")
        print(f"Date fin prévue assemblage : {resultat['date_fin_prevue']}")

        # ÉTAPE 4 — Pointage début opération
        print("\n=== POINTAGE ===")
        premier_of = of_assemblage.ordres_fabrication[0]
        premiere_op = premier_of.operations_planifiees[0]

        pointer_debut_operation(session, premiere_op.id_op_plan)
        pointer_fin_operation(
            session=session,
            id_op_plan=premiere_op.id_op_plan,
            tps_prep_reel=18,
            tps_exec_reel=55
        )

        # ÉTAPE 5 — Constat de rebut
        print("\n=== REBUT ===")
        deuxieme_op = premier_of.operations_planifiees[1]
        pointer_debut_operation(session, deuxieme_op.id_op_plan)

        constater_rebut(
            session=session,
            id_of=premier_of.id_of,
            id_op_plan=deuxieme_op.id_op_plan,
            quantite_rebutee=1.0,
            cause="Défaut matière",
            decision="retouche"
        )

        # Commit final
        session.commit()
        print("\n✅ Test complet réussi — données enregistrées en base")

    except Exception as e:
        session.rollback()
        print(f"\n❌ Erreur : {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()