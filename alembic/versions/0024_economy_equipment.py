"""economy phase 2: equipment slots, condition, carry weight, ammunition and repairing occupations

Phase 2 of design/economy.md.
- gear_items: weight (kg) and slot (where an accessory is worn).
- character_gear: slot (where it is equipped), condition (good, worn, damaged, broken) and ammo_die.
- occupations: repairs (the kinds of gear its characters can repair).
- Broken stops being a status: broken items become owned items in Broken condition, so they can be repaired.
- Equipped gear gets a slot: worn armor the body, the first equipped shield the off hand, the first other equipped
  weapon the main hand. Other equipped weapons are put away; every owned weapon can still be used in a fight.

Comes before the legacy drop (0026_drop_legacy_combat). A downgrade turns Broken items back into the broken status.

Revision ID: 0024_economy_equipment
Revises: 0023_economy_money
Create Date: 2026-11-16 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0024_economy_equipment'
down_revision: Union[str, None] = '0023_economy_money'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Broken items become owned items in Broken condition; equipped gear gets a slot (armor the body, the first equipped
# shield the off hand, the first other equipped weapon the main hand) and other equipped weapons are put away.
DATA_STATEMENTS = [
    "UPDATE character_gear SET status = 'owned', condition = 'broken' WHERE status = 'broken'",
    "UPDATE character_gear SET slot = 'body' WHERE kind = 'armor' AND equipped",
    """WITH ranked AS (
        SELECT character_gear.id AS id, hands.hand AS hand,
               row_number() OVER (PARTITION BY character_gear.character_id, hands.hand ORDER BY character_gear.id) AS n
        FROM character_gear
        LEFT JOIN gear_items ON gear_items.id = character_gear.gear_item_id
        CROSS JOIN LATERAL (SELECT CASE WHEN COALESCE((gear_items.combat::jsonb -> 'properties') ? 'shield', false)
                                        THEN 'off_hand' ELSE 'main_hand' END AS hand) AS hands
        WHERE character_gear.kind = 'weapon' AND character_gear.equipped)
    UPDATE character_gear SET slot = ranked.hand FROM ranked WHERE character_gear.id = ranked.id AND ranked.n = 1""",
    "UPDATE character_gear SET equipped = false WHERE kind = 'weapon' AND equipped AND slot IS NULL",
]


def upgrade() -> None:
    op.add_column('gear_items', sa.Column('weight', sa.Float(), nullable=True))
    op.add_column('gear_items', sa.Column('slot', sa.String(length=16), nullable=True))
    op.add_column('character_gear', sa.Column('slot', sa.String(length=16), nullable=True))
    op.add_column('character_gear', sa.Column('condition', sa.String(length=16), server_default='good',
                                              nullable=False))
    op.add_column('character_gear', sa.Column('ammo_die', sa.String(length=8), nullable=True))
    op.add_column('occupations', sa.Column('repairs', sa.JSON(), nullable=True))
    for statement in DATA_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    op.execute("UPDATE character_gear SET status = 'broken' WHERE condition = 'broken' AND status = 'owned'")
    op.drop_column('occupations', 'repairs')
    op.drop_column('character_gear', 'ammo_die')
    op.drop_column('character_gear', 'condition')
    op.drop_column('character_gear', 'slot')
    op.drop_column('gear_items', 'slot')
    op.drop_column('gear_items', 'weight')
