"""economy phase 4: merchants, their stock, haggles, lodgings and stashes

Phase 4 of design/economy.md: merchants (NPC shops at locations), merchant_stock, merchant_haggles, lodgings, and
character_gear.stash_location_id for stashed items. Comes after the legacy drop (0026_drop_legacy_combat). A downgrade gives
stashed items back to their owners.

Revision ID: 0027_economy_merchants
Revises: 0026_drop_legacy_combat
Create Date: 2026-11-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0027_economy_merchants'
down_revision: Union[str, None] = '0026_drop_legacy_combat'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('character_gear', sa.Column('stash_location_id', sa.BigInteger(), nullable=True))
    op.create_table('merchants',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('avatar_url', sa.String(length=500), nullable=True),
    sa.Column('location_ids', sa.JSON(), nullable=False),
    sa.Column('faction_id', sa.BigInteger(), nullable=True),
    sa.Column('markup', sa.Float(), nullable=False),
    sa.Column('buys', sa.JSON(), nullable=False),
    sa.Column('pays', sa.Float(), nullable=False),
    sa.Column('services', sa.JSON(), nullable=False),
    sa.Column('lodging_price', sa.Integer(), nullable=False),
    sa.Column('haggle_dc', sa.Integer(), nullable=True),
    sa.Column('restock', sa.String(length=16), nullable=False),
    sa.Column('last_restock', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cycle', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_merchants_guild_id'), 'merchants', ['guild_id'], unique=False)
    op.create_index('uq_merchant_guild_name', 'merchants', ['guild_id', sa.text('lower(name)')], unique=True)
    op.create_table('merchant_stock',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('merchant_id', sa.BigInteger(), nullable=False),
    sa.Column('gear_item_id', sa.BigInteger(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=True),
    sa.Column('chance', sa.Integer(), nullable=False),
    sa.Column('price', sa.BigInteger(), nullable=True),
    sa.Column('in_stock', sa.Integer(), nullable=True),
    sa.Column('available', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['gear_item_id'], ['gear_items.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_merchant_stock_merchant_id'), 'merchant_stock', ['merchant_id'], unique=False)
    op.create_table('merchant_haggles',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('merchant_id', sa.BigInteger(), nullable=False),
    sa.Column('character_id', sa.BigInteger(), nullable=False),
    sa.Column('gear_item_id', sa.BigInteger(), nullable=True),
    sa.Column('cycle', sa.Integer(), nullable=False),
    sa.Column('discount', sa.Integer(), nullable=False),
    sa.Column('refused', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_merchant_haggles_merchant_id'), 'merchant_haggles', ['merchant_id'], unique=False)
    op.create_table('lodgings',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('character_id', sa.BigInteger(), nullable=False),
    sa.Column('location_id', sa.BigInteger(), nullable=False),
    sa.Column('merchant_id', sa.BigInteger(), nullable=True),
    sa.Column('paid_until', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_lodgings_character_id'), 'lodgings', ['character_id'], unique=False)


def downgrade() -> None:
    op.execute("UPDATE character_gear SET status = 'owned' WHERE status = 'stashed'")
    op.drop_index(op.f('ix_lodgings_character_id'), table_name='lodgings')
    op.drop_table('lodgings')
    op.drop_index(op.f('ix_merchant_haggles_merchant_id'), table_name='merchant_haggles')
    op.drop_table('merchant_haggles')
    op.drop_index(op.f('ix_merchant_stock_merchant_id'), table_name='merchant_stock')
    op.drop_table('merchant_stock')
    op.drop_index('uq_merchant_guild_name', table_name='merchants')
    op.drop_index(op.f('ix_merchants_guild_id'), table_name='merchants')
    op.drop_table('merchants')
    op.drop_column('character_gear', 'stash_location_id')
