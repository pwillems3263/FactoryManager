"""add_shift_config_and_duree_reelle

Revision ID: f588c19b6fa3
Revises: a1b2c3d4e5f6
Create Date: 2026-05-09 17:14:04.005324

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'f588c19b6fa3'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    insp = inspect(conn)

    # ── Table machineshiftconfig — créée seulement si absente ──────────────
    if 'machineshiftconfig' not in insp.get_table_names():
        op.create_table('machineshiftconfig',
        sa.Column('id_config', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('id_machine', sa.Integer(), nullable=False),
        sa.Column('shift_index', sa.Integer(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['id_machine'], ['machine.id_machine'], ),
        sa.PrimaryKeyConstraint('id_config')
        )

    # ── Colonnes de operationplanifiee — vérifiées individuellement ────────
    cols = {c['name'] for c in insp.get_columns('operationplanifiee')}

    if 'duree_reelle_min' not in cols:
        op.add_column('operationplanifiee', sa.Column('duree_reelle_min', sa.Integer(), nullable=True))

    if 'duree_estimee_minutes' in cols:
        op.drop_column('operationplanifiee', 'duree_estimee_minutes')


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    insp = inspect(conn)
    cols = {c['name'] for c in insp.get_columns('operationplanifiee')}

    if 'duree_estimee_minutes' not in cols:
        op.add_column('operationplanifiee', sa.Column('duree_estimee_minutes', sa.INTEGER(), autoincrement=False, nullable=True))
    if 'duree_reelle_min' in cols:
        op.drop_column('operationplanifiee', 'duree_reelle_min')
    if 'machineshiftconfig' in insp.get_table_names():
        op.drop_table('machineshiftconfig')
