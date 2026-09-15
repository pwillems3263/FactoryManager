"""add_date_livraison_reelle_to_commande

Revision ID: a3b4c5d6e7f8
Revises: f1a2b3c4d5e6
Create Date: 2026-09-15 00:00:00.000004

Adds a separate "actual delivery date" column, kept independent from the
existing "date_livraison" (estimated delivery date) so the two can be
compared later (on-time / early / late delivery reporting).

Run `alembic heads` first to confirm 'f1a2b3c4d5e6' is still your current
head before upgrading; adjust down_revision below if something else was
applied since.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('commande', sa.Column('date_livraison_reelle', sa.Date(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('commande', 'date_livraison_reelle')
