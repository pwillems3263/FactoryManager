"""drop_type_column_composant

Revision ID: c2a4d8f01e77
Revises: 9b1e2f6a7c3d
Create Date: 2026-09-15 00:00:00.000001

The "type" field on components (machining / welding / assembly / other)
was purely informational — no part of the app read it to drive any
behavior (cost calculation, routing, filtering, etc.) — so it's removed.

NOTE: this chains after '9b1e2f6a7c3d' (the app_setting migration). Run
`alembic heads` first to confirm that's still your current head before
upgrading; adjust down_revision below if something else was applied since.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2a4d8f01e77'
down_revision: Union[str, Sequence[str], None] = '9b1e2f6a7c3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('composant', 'type')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('composant', sa.Column('type', sa.String(length=50), nullable=True))
