"""proxying: the log of messages posted as characters, and autoproxy channels

Revision ID: 0005_proxying
Revises: 0004_characters
Create Date: 2026-11-14 20:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005_proxying'
down_revision: Union[str, None] = '0004_characters'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('proxy_messages',
    sa.Column('message_id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('first_message_id', sa.BigInteger(), nullable=False),
    sa.Column('character_id', sa.BigInteger(), nullable=True),
    sa.Column('uid', sa.BigInteger(), nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('channel_id', sa.BigInteger(), nullable=False),
    sa.Column('length', sa.Integer(), nullable=False),
    sa.Column('counted', sa.Boolean(), nullable=False),
    sa.Column('xp_awarded', sa.BigInteger(), nullable=False),
    sa.Column('currency_awarded', sa.BigInteger(), nullable=False),
    sa.Column('deleted', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('message_id')
    )
    op.create_index(op.f('ix_proxy_messages_character_id'), 'proxy_messages', ['character_id'], unique=False)
    op.create_index(op.f('ix_proxy_messages_first_message_id'), 'proxy_messages', ['first_message_id'], unique=False)
    op.create_index(op.f('ix_proxy_messages_guild_id'), 'proxy_messages', ['guild_id'], unique=False)
    op.create_index(op.f('ix_proxy_messages_uid'), 'proxy_messages', ['uid'], unique=False)
    op.create_table('autoproxy',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('uid', sa.BigInteger(), nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('channel_id', sa.BigInteger(), nullable=False),
    sa.Column('character_id', sa.BigInteger(), nullable=False),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('uid', 'channel_id', name='uq_autoproxy_uid_channel')
    )


def downgrade() -> None:
    op.drop_table('autoproxy')
    op.drop_index(op.f('ix_proxy_messages_uid'), table_name='proxy_messages')
    op.drop_index(op.f('ix_proxy_messages_guild_id'), table_name='proxy_messages')
    op.drop_index(op.f('ix_proxy_messages_first_message_id'), table_name='proxy_messages')
    op.drop_index(op.f('ix_proxy_messages_character_id'), table_name='proxy_messages')
    op.drop_table('proxy_messages')
