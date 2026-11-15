"""passive abilities: an ability is active (used on a turn) or passive (always on, with its parts in passive)

Comes before 0014_drop_legacy_combat, which waits until the old tables have been imported.

Revision ID: 0013_passive_abilities
Revises: 0012_bestiary_special
Create Date: 2026-11-16 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0013_passive_abilities'
down_revision: Union[str, None] = '0012_bestiary_special'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('abilities', sa.Column('activation', sa.String(length=16), server_default='active', nullable=False))
    op.add_column('abilities', sa.Column('passive', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('abilities', 'passive')
    op.drop_column('abilities', 'activation')
