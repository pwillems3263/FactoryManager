"""refonte nomenclature avec id auto

Revision ID: 2466a6dad30b
Revises: e144a9902132
Create Date: 2026-05-02 12:59:11.894846

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '2466a6dad30b'
down_revision: Union[str, Sequence[str], None] = 'e144a9902132'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    insp = inspect(conn)

    # Colonne id_nomenclature (auto-increment) ajoutée en premier
    op.add_column('nomenclature', sa.Column('id_nomenclature', sa.Integer(), autoincrement=True, nullable=False))

    # ── Remplace l'ancienne PK (probablement sur id_composant, ou composite)
    #    par une PK sur id_nomenclature. On détecte le nom réel de la
    #    contrainte au lieu de le supposer, pour être robuste quel que soit
    #    l'historique exact de la table sur cette base. ──
    pk = insp.get_pk_constraint('nomenclature')
    old_pk_name = pk.get('name')
    if old_pk_name:
        op.drop_constraint(old_pk_name, 'nomenclature', type_='primary')

    op.create_primary_key('nomenclature_pkey', 'nomenclature', ['id_nomenclature'])

    # Maintenant que id_composant n'est plus PK, on peut la rendre nullable
    op.alter_column('nomenclature', 'id_composant',
               existing_type=sa.INTEGER(),
               nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('nomenclature', 'id_composant',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.drop_constraint('nomenclature_pkey', 'nomenclature', type_='primary')
    op.create_primary_key('nomenclature_pkey', 'nomenclature', ['id_composant'])
    op.drop_column('nomenclature', 'id_nomenclature')
