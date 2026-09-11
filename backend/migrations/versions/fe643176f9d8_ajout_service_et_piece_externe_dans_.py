"""ajout service et piece externe dans nomenclature

Revision ID: fe643176f9d8
Revises: 3cfa73f3cebb
Create Date: 2026-05-02 08:37:44.262518

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fe643176f9d8'
down_revision: Union[str, Sequence[str], None] = '3cfa73f3cebb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ajout des nouvelles colonnes
    op.add_column('nomenclature',
        sa.Column('id_service', sa.Integer(), nullable=True))
    op.add_column('nomenclature',
        sa.Column('id_piece_externe', sa.Integer(), nullable=True))

    # Ajout des foreign keys
    op.create_foreign_key(
        None, 'nomenclature', 'service',
        ['id_service'], ['id_service']
    )
    op.create_foreign_key(
        None, 'nomenclature', 'piece_externe',
        ['id_piece_externe'], ['id_piece_externe']
    )
    # NOTE: id_composant reste NOT NULL car il est PK
    # La logique nullable sera gérée au niveau applicatif

def downgrade() -> None:
    op.drop_constraint(None, 'nomenclature', type_='foreignkey')
    op.drop_column('nomenclature', 'id_piece_externe')
    op.drop_column('nomenclature', 'id_service')
