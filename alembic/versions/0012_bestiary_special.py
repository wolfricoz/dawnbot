"""bestiary entries built from SPECIAL, with catalog weapons and armor

Comes before 0017_drop_legacy_combat, so the old npcs, monsters, armors and weapons can be imported
(/bestiary import legacy, /armory import legacy) before they are dropped.

Revision ID: 0012_bestiary_special
Revises: 0011_combat
Create Date: 2026-11-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0012_bestiary_special'
down_revision: Union[str, None] = '0011_combat'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bestiary', sa.Column('special', sa.JSON(), nullable=True))
    op.add_column('bestiary', sa.Column('level', sa.Integer(), server_default='1', nullable=False))
    # Existing rows get an empty list; the column keeps no server default (autogenerate can't compare JSON ones).
    op.add_column('bestiary', sa.Column('weapon_ids', sa.JSON(), server_default='[]', nullable=False))
    op.alter_column('bestiary', 'weapon_ids', server_default=None)
    op.add_column('bestiary', sa.Column('armor_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key('bestiary_armor_id_fkey', 'bestiary', 'gear_items', ['armor_id'], ['id'],
                          ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('bestiary_armor_id_fkey', 'bestiary', type_='foreignkey')
    op.drop_column('bestiary', 'armor_id')
    op.drop_column('bestiary', 'weapon_ids')
    op.drop_column('bestiary', 'level')
    op.drop_column('bestiary', 'special')
