"""add_app_setting_table

Revision ID: 9b1e2f6a7c3d
Revises: d4b8e6f1c290
Create Date: 2026-09-15 00:00:00.000000

NOTE: down_revision was set to 'd4b8e6f1c290', which appears to be the
current head of this migration chain based on the versions available at
the time this was written. Before running `alembic upgrade head`, please
verify with `alembic heads` that 'd4b8e6f1c290' is indeed your current
head — if not, update down_revision below to match your actual head
revision id.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b1e2f6a7c3d'
down_revision: Union[str, Sequence[str], None] = 'd4b8e6f1c290'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'app_setting',
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.String(length=2000), nullable=True),
        sa.PrimaryKeyConstraint('key'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('app_setting')
