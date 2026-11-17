"""economy phase 1: catalog items get a rarity; existing servers keep their money settings

Phase 1 of design/economy.md. The defaults for starting money (3000 → 1500), post pay (30 → 8 characters per unit)
and downtime work pay (50 → 125) change, but servers that already exist keep what they have: each server without its
own STARTING_CURRENCY, CURRENCY_GAIN or WORK_PAY setting gets the old default written as its setting. Servers added
later use the new defaults. Comes before the legacy drop (0026_drop_legacy_combat).

A downgrade drops the rarity column and leaves the written settings, which hold the values those servers used anyway.

Revision ID: 0023_economy_money
Revises: 0022_roleplay_extras
Create Date: 2026-11-16 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0023_economy_money'
down_revision: Union[str, None] = '0022_roleplay_extras'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The defaults before this round, kept by existing servers.
OLD_DEFAULTS = {"STARTING_CURRENCY" : "3000", "CURRENCY_GAIN" : "30", "WORK_PAY" : "50"}


def upgrade() -> None:
    op.add_column('gear_items', sa.Column('rarity', sa.String(length=16), nullable=True))
    for key, value in OLD_DEFAULTS.items():
        op.execute(sa.text(
            "INSERT INTO config (guild, key, value) "
            "SELECT servers.id, :key, :value FROM servers "
            "WHERE NOT EXISTS (SELECT 1 FROM config WHERE config.guild = servers.id AND upper(config.key) = :key)"
        ).bindparams(key=key, value=value))


def downgrade() -> None:
    op.drop_column('gear_items', 'rarity')
