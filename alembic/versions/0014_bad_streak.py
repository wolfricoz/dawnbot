"""bad-roll protection: characters count their failed rolls in a row

Comes before 0029_drop_legacy_combat, which waits until the old tables have been imported.

Revision ID: 0014_bad_streak
Revises: 0013_passive_abilities
Create Date: 2026-11-16 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0014_bad_streak'
down_revision: Union[str, None] = '0013_passive_abilities'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('characters', sa.Column('bad_streak', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('characters', 'bad_streak')
