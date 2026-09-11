"""Migration : création de la table typemachine et ajout de id_type_machine dans machine.

Usage (depuis le dossier migrations/) :
    python migration_typemachine.py
"""
import sys
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

from sqlalchemy import text
from database import engine


def run():
    with engine.connect() as conn:

        # 1. Crée la table typemachine (PostgreSQL)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS typemachine (
                id_type     SERIAL PRIMARY KEY,
                nom         VARCHAR(100) NOT NULL UNIQUE,
                description VARCHAR(255)
            )
        """))
        conn.commit()
        print("✓ Table typemachine créée (ou déjà existante).")

        # 2. Peuple avec les types déjà présents dans machine.type
        conn.execute(text("""
            INSERT INTO typemachine (nom)
            SELECT DISTINCT TRIM(type)
            FROM machine
            WHERE type IS NOT NULL AND TRIM(type) <> ''
            ON CONFLICT (nom) DO NOTHING
        """))
        conn.commit()
        print("✓ Types existants migrés dans typemachine.")

        # 3. Ajoute la colonne id_type_machine si elle n'existe pas
        exists = conn.execute(text("""
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_name = 'machine'
              AND column_name = 'id_type_machine'
        """)).scalar()

        if not exists:
            conn.execute(text("""
                ALTER TABLE machine
                ADD COLUMN id_type_machine INTEGER
                    REFERENCES typemachine(id_type)
            """))
            conn.commit()
            print("✓ Colonne id_type_machine ajoutée dans machine.")
        else:
            print("  Colonne id_type_machine déjà présente — ignorée.")

        # 4. Met à jour les FK pour les machines existantes
        conn.execute(text("""
            UPDATE machine
            SET id_type_machine = t.id_type
            FROM typemachine t
            WHERE TRIM(machine.type) = t.nom
              AND machine.id_type_machine IS NULL
        """))
        conn.commit()
        print("✓ Clés étrangères id_type_machine mises à jour.")

    print("\nMigration terminée avec succès.")


if __name__ == "__main__":
    run()