"""gear: the gear catalog, owned gear and the currency ledger

Revision ID: 0007_gear
Revises: 0006_species_occupations
Create Date: 2026-11-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0007_gear'
down_revision: Union[str, None] = '0006_species_occupations'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('gear_items',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('price', sa.BigInteger(), nullable=False),
    sa.Column('requirements', sa.JSON(), nullable=False),
    sa.Column('effect_met', sa.Text(), nullable=True),
    sa.Column('effect_unmet', sa.Text(), nullable=True),
    sa.Column('effect', sa.Text(), nullable=True),
    sa.Column('combat', sa.JSON(), nullable=False),
    sa.Column('tag_ids', sa.JSON(), nullable=False),
    sa.Column('forum_thread_id', sa.BigInteger(), nullable=True),
    sa.Column('forum_message_id', sa.BigInteger(), nullable=True),
    sa.Column('pack', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_gear_items_guild_id'), 'gear_items', ['guild_id'], unique=False)
    op.create_index('uq_gear_item_guild_name', 'gear_items', ['guild_id', sa.literal_column('lower(name)')],
                    unique=True)
    op.create_table('character_gear',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('character_id', sa.BigInteger(), nullable=False),
    sa.Column('gear_item_id', sa.BigInteger(), nullable=True),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('equipped', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('source', sa.String(length=16), nullable=False),
    sa.Column('price_paid', sa.BigInteger(), nullable=False),
    sa.Column('changed_by', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['gear_item_id'], ['gear_items.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_character_gear_character_id'), 'character_gear', ['character_id'], unique=False)
    op.create_table('currency_transactions',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('character_id', sa.BigInteger(), nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('amount', sa.BigInteger(), nullable=False),
    sa.Column('reason', sa.String(length=16), nullable=False),
    sa.Column('actor_uid', sa.BigInteger(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_currency_transactions_character_id'), 'currency_transactions', ['character_id'],
                    unique=False)
    op.create_index(op.f('ix_currency_transactions_guild_id'), 'currency_transactions', ['guild_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_currency_transactions_guild_id'), table_name='currency_transactions')
    op.drop_index(op.f('ix_currency_transactions_character_id'), table_name='currency_transactions')
    op.drop_table('currency_transactions')
    op.drop_index(op.f('ix_character_gear_character_id'), table_name='character_gear')
    op.drop_table('character_gear')
    op.drop_index('uq_gear_item_guild_name', table_name='gear_items')
    op.drop_index(op.f('ix_gear_items_guild_id'), table_name='gear_items')
    op.drop_table('gear_items')
