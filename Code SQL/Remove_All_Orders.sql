-- ============================================================
-- SCRIPT : Nettoyage complet des commandes et données liées
-- FactoryManager — à exécuter dans pgAdmin
-- ATTENTION : suppression irréversible de toutes les commandes
-- ============================================================

BEGIN;

-- 1. Rebuts (dépend de operationplanifiee et ordrefabrication)
DELETE FROM rebut;

-- 2. Livraisons partielles (dépend de ordrefabrication)
DELETE FROM livraisonpartielle;

-- 3. Opérations planifiées (dépend de ordrefabrication)
DELETE FROM operationplanifiee;

-- 4. Ordres de fabrication (dépend de ofassemblage)
DELETE FROM ordrefabrication;

-- 5. OF Assemblages (dépend de lignecommande)
DELETE FROM ofassemblage;

-- 6. Lignes de commande (dépend de commande)
DELETE FROM lignecommande;

-- 7. Commandes
DELETE FROM commande;

-- 8. Réinitialisation des séquences (auto-increment repart à 1)
ALTER SEQUENCE rebut_id_rebut_seq RESTART WITH 1;
ALTER SEQUENCE livraisonpartielle_id_livraison_seq RESTART WITH 1;
ALTER SEQUENCE operationplanifiee_id_op_plan_seq RESTART WITH 1;
ALTER SEQUENCE ordrefabrication_id_of_seq RESTART WITH 1;
ALTER SEQUENCE ofassemblage_id_of_assemblage_seq RESTART WITH 1;
ALTER SEQUENCE lignecommande_id_ligne_seq RESTART WITH 1;
ALTER SEQUENCE commande_id_commande_seq RESTART WITH 1;

COMMIT;