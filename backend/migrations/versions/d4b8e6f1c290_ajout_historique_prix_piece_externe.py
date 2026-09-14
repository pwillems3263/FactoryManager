"""ajout_historique_prix_piece_externe

Revision ID: d4b8e6f1c290
Revises: a7f3c9d21b45
Create Date: 2026-09-14 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4b8e6f1c290'
down_revision: Union[str, Sequence[str], None] = 'a7f3c9d21b45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('historiqueprixpieceexterne',
    sa.Column('id_historique', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('id_piece_externe', sa.Integer(), nullable=False),
    sa.Column('ancien_prix', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('nouveau_prix', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('date_modification', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['id_piece_externe'], ['piece_externe.id_piece_externe'], ),
    sa.PrimaryKeyConstraint('id_historique')
    )
    op.create_index(op.f('ix_historiqueprixpieceexterne_id_piece_externe'), 'historiqueprixpieceexterne', ['id_piece_externe'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_historiqueprixpieceexterne_id_piece_externe'), table_name='historiqueprixpieceexterne')
    op.drop_table('historiqueprixpieceexterne')
