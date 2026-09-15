"""remap_commande_statut_to_4_statuses

Revision ID: f1a2b3c4d5e6
Revises: e5f7a9c31b02
Create Date: 2026-09-15 00:00:00.000003

Order status is now one of exactly 4 values, each tied to real behavior
(see backend/routers/commandes.py): estimation, part_confirmed, confirmed,
finished. Existing rows are remapped from the old free-form values:

    planifiee -> estimation
    en_cours  -> part_confirmed
    terminee  -> finished
    annulee   -> estimation   (no direct equivalent in the new 4-status
                                model; "estimation" was chosen as the
                                safest, fully-reversible default — these
                                orders can still be freely edited/deleted.
                                Review any remapped "annulee" orders after
                                this migration and reassign manually if a
                                different status fits better.)

Run `alembic heads` first to confirm 'e5f7a9c31b02' is still your current
head before upgrading; adjust down_revision below if something else was
applied since.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e5f7a9c31b02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("UPDATE commande SET statut = 'estimation'     WHERE statut = 'planifiee'")
    op.execute("UPDATE commande SET statut = 'part_confirmed' WHERE statut = 'en_cours'")
    op.execute("UPDATE commande SET statut = 'finished'       WHERE statut = 'terminee'")
    op.execute("UPDATE commande SET statut = 'estimation'     WHERE statut = 'annulee'")
    op.alter_column('commande', 'statut', server_default='estimation')


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE commande SET statut = 'planifiee' WHERE statut = 'estimation'")
    op.execute("UPDATE commande SET statut = 'en_cours'  WHERE statut = 'part_confirmed'")
    op.execute("UPDATE commande SET statut = 'terminee'  WHERE statut = 'finished'")
    # Note: 'confirmed' has no old-schema equivalent; downgraded to 'planifiee'.
    op.execute("UPDATE commande SET statut = 'planifiee' WHERE statut = 'confirmed'")
    op.alter_column('commande', 'statut', server_default='planifiee')
