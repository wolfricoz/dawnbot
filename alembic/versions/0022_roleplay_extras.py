"""roleplay extras: occupations can need faction standing, locations belong to a faction, crafting projects can be
flawed

The pieces of design/roleplay-tools.md built after phases A to F. Comes before the legacy drop (0026_drop_legacy_combat).

Revision ID: 0022_roleplay_extras
Revises: 0021_rumors_omens
Create Date: 2026-11-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0022_roleplay_extras'
down_revision: Union[str, None] = '0021_rumors_omens'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('occupations', sa.Column('faction_id', sa.BigInteger(), nullable=True))
    op.add_column('occupations', sa.Column('faction_tier', sa.String(length=16), nullable=True))
    op.add_column('locations', sa.Column('faction_id', sa.BigInteger(), nullable=True))
    op.add_column('craft_projects', sa.Column('flawed', sa.Boolean(), server_default=sa.text('false'), nullable=False))


def downgrade() -> None:
    op.drop_column('craft_projects', 'flawed')
    op.drop_column('locations', 'faction_id')
    op.drop_column('occupations', 'faction_tier')
    op.drop_column('occupations', 'faction_id')
