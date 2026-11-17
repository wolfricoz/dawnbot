"""economy phase 3: trades between characters and the market

Phase 3 of design/economy.md: the trades table (a trade window's offers and who accepted) and market_listings (items
offered on the market forum). Comes before the legacy drop (0026_drop_legacy_combat).

Revision ID: 0025_economy_trading
Revises: 0024_economy_equipment
Create Date: 2026-11-16 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0025_economy_trading'
down_revision: Union[str, None] = '0024_economy_equipment'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('trades',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('channel_id', sa.BigInteger(), nullable=True),
    sa.Column('message_id', sa.BigInteger(), nullable=True),
    sa.Column('left_character_id', sa.BigInteger(), nullable=False),
    sa.Column('right_character_id', sa.BigInteger(), nullable=False),
    sa.Column('left_uid', sa.BigInteger(), nullable=False),
    sa.Column('right_uid', sa.BigInteger(), nullable=False),
    sa.Column('offers', sa.JSON(), nullable=False),
    sa.Column('accepted', sa.JSON(), nullable=False),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['left_character_id'], ['characters.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['right_character_id'], ['characters.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trades_guild_id'), 'trades', ['guild_id'], unique=False)
    op.create_table('market_listings',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('entry_id', sa.BigInteger(), nullable=True),
    sa.Column('seller_character_id', sa.BigInteger(), nullable=True),
    sa.Column('seller_uid', sa.BigInteger(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('price', sa.BigInteger(), nullable=False),
    sa.Column('fee', sa.BigInteger(), nullable=False),
    sa.Column('thread_id', sa.BigInteger(), nullable=True),
    sa.Column('message_id', sa.BigInteger(), nullable=True),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('buyer_character_id', sa.BigInteger(), nullable=True),
    sa.Column('buyer_uid', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['entry_id'], ['character_gear.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['seller_character_id'], ['characters.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_market_listings_guild_id'), 'market_listings', ['guild_id'], unique=False)


def downgrade() -> None:
    # Items still listed go back to their owners.
    op.execute("UPDATE character_gear SET status = 'owned' WHERE status = 'listed'")
    op.drop_index(op.f('ix_market_listings_guild_id'), table_name='market_listings')
    op.drop_table('market_listings')
    op.drop_index(op.f('ix_trades_guild_id'), table_name='trades')
    op.drop_table('trades')
