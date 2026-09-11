"""ajout_travaille_samedi_dimanche_machine

Revision ID: a1b2c3d4e5f6
Revises: fed0bec774cc
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '219f2db5bf56'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('machine',
        sa.Column('travaille_samedi',   sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('machine',
        sa.Column('travaille_dimanche', sa.Boolean(), nullable=False, server_default='0'))

def downgrade():
    op.drop_column('machine', 'travaille_dimanche')
    op.drop_column('machine', 'travaille_samedi')