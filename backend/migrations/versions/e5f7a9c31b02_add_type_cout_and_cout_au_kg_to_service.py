"""add_type_cout_and_cout_au_kg_to_service

Revision ID: e5f7a9c31b02
Revises: c2a4d8f01e77
Create Date: 2026-09-15 00:00:00.000002

Services can now be priced three ways: per hour (existing "cout_horaire"),
per kg (new "cout_au_kg", computed against the component's raw stock
weight), or a flat fixed price (existing "cout_fixe"). "type_cout" makes
the choice explicit instead of inferring it from which field happens to be
filled in.

Run `alembic heads` first to confirm 'c2a4d8f01e77' is still your current
head before upgrading; adjust down_revision below if something else was
applied since.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f7a9c31b02'
down_revision: Union[str, Sequence[str], None] = 'c2a4d8f01e77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'service',
        sa.Column('type_cout', sa.String(length=20), nullable=False, server_default='horaire')
    )
    op.add_column(
        'service',
        sa.Column('cout_au_kg', sa.Numeric(precision=10, scale=4), nullable=True)
    )

    # Best-effort inference for existing rows: if a service only had a fixed
    # cost (no hourly rate), mark it as 'fixe'; everything else defaults to
    # 'horaire' via the column default above.
    op.execute(
        "UPDATE service SET type_cout = 'fixe' "
        "WHERE cout_fixe IS NOT NULL AND cout_horaire IS NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('service', 'cout_au_kg')
    op.drop_column('service', 'type_cout')
