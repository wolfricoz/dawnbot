"""economy phase 5: magic items, attunement, identification, enchanting designs and loot

Phase 5 of design/economy.md: gear_items.enchantments, unidentified_name and crafted_only; character_gear.attuned,
charges_left, charges_day, extra_charges and identified; bestiary.loot; recipes.enchanting; and the enchant_designs and
fight_loot tables. Comes after the legacy drop (0026_drop_legacy_combat).

Revision ID: 0028_economy_magic
Revises: 0027_economy_merchants
Create Date: 2026-11-17 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0028_economy_magic'
down_revision: Union[str, None] = '0027_economy_merchants'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('gear_items', sa.Column('enchantments', sa.JSON(), nullable=True))
    op.add_column('gear_items', sa.Column('unidentified_name', sa.String(length=100), nullable=True))
    op.add_column('gear_items', sa.Column('crafted_only', sa.Boolean(), server_default=sa.text('false'),
                                          nullable=False))
    op.add_column('character_gear', sa.Column('attuned', sa.Boolean(), server_default=sa.text('false'),
                                              nullable=False))
    op.add_column('character_gear', sa.Column('charges_left', sa.Integer(), nullable=True))
    op.add_column('character_gear', sa.Column('charges_day', sa.String(length=10), nullable=True))
    op.add_column('character_gear', sa.Column('extra_charges', sa.Integer(), server_default='0', nullable=False))
    op.add_column('character_gear', sa.Column('identified', sa.Boolean(), server_default=sa.text('true'),
                                              nullable=False))
    op.add_column('bestiary', sa.Column('loot', sa.JSON(), nullable=True))
    op.add_column('recipes', sa.Column('enchanting', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.create_table('enchant_designs',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('creator_uid', sa.BigInteger(), nullable=False),
    sa.Column('character_id', sa.BigInteger(), nullable=True),
    sa.Column('base_item_id', sa.BigInteger(), nullable=True),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('rarity', sa.String(length=16), nullable=False),
    sa.Column('enchantments', sa.JSON(), nullable=False),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('review_message_id', sa.BigInteger(), nullable=True),
    sa.Column('result_item_id', sa.BigInteger(), nullable=True),
    sa.Column('recipe_id', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['base_item_id'], ['gear_items.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_enchant_designs_guild_id'), 'enchant_designs', ['guild_id'], unique=False)
    op.create_table('fight_loot',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('fight_id', sa.BigInteger(), nullable=False),
    sa.Column('channel_id', sa.BigInteger(), nullable=True),
    sa.Column('message_id', sa.BigInteger(), nullable=True),
    sa.Column('currency', sa.Integer(), nullable=False),
    sa.Column('items', sa.JSON(), nullable=False),
    sa.Column('mode', sa.String(length=16), nullable=False),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fight_loot_guild_id'), 'fight_loot', ['guild_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_fight_loot_guild_id'), table_name='fight_loot')
    op.drop_table('fight_loot')
    op.drop_index(op.f('ix_enchant_designs_guild_id'), table_name='enchant_designs')
    op.drop_table('enchant_designs')
    op.drop_column('recipes', 'enchanting')
    op.drop_column('bestiary', 'loot')
    for column in ('identified', 'extra_charges', 'charges_day', 'charges_left', 'attuned'):
        op.drop_column('character_gear', column)
    for column in ('crafted_only', 'unidentified_name', 'enchantments'):
        op.drop_column('gear_items', column)
