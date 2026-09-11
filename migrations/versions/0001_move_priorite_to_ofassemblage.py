"""Move priorite from ordrefabrication to ofassemblage

Revision ID: move_priorite_ofa
Revises: <previous_revision_id>
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa

revision = 'move_priorite_ofa'
down_revision = '4cf39ade8e41'   # ← remplace par l'ID de ta dernière migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Ajoute priorite sur ofassemblage (défaut 5 = Normal)
    op.add_column(
        'ofassemblage',
        sa.Column('priorite', sa.Integer(), nullable=False,
                  server_default='5')
    )
    # 2. Supprime priorite de ordrefabrication
    op.drop_column('ordrefabrication', 'priorite')


def downgrade() -> None:
    # Inverse : remet priorite sur ordrefabrication, retire de ofassemblage
    op.add_column(
        'ordrefabrication',
        sa.Column('priorite', sa.Integer(), nullable=False,
                  server_default='5')
    )
    op.drop_column('ofassemblage', 'priorite')