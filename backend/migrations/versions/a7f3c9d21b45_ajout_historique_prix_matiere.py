"""ajout_historique_prix_matiere

Revision ID: a7f3c9d21b45
Revises: 5c65fb48951f
Create Date: 2026-09-14 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7f3c9d21b45'
down_revision: Union[str, Sequence[str], None] = '5c65fb48951f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('historiqueprixmatiere',
    sa.Column('id_historique', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('id_matiere', sa.Integer(), nullable=False),
    sa.Column('ancien_prix', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('nouveau_prix', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('date_modification', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['id_matiere'], ['matierepremiere.id_matiere'], ),
    sa.PrimaryKeyConstraint('id_historique')
    )
    op.create_index(op.f('ix_historiqueprixmatiere_id_matiere'), 'historiqueprixmatiere', ['id_matiere'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_historiqueprixmatiere_id_matiere'), table_name='historiqueprixmatiere')
    op.drop_table('historiqueprixmatiere')
