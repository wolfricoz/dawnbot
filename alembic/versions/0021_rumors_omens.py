"""rumors and omens: rumors, who heard them, rumor listens and blocks, omen draws

Phase F of design/roleplay-tools.md (characters.omen came in 0019). Comes before the legacy drop, which stays last.

Revision ID: 0021_rumors_omens
Revises: 0020_economy
Create Date: 2026-11-15 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0021_rumors_omens'
down_revision: Union[str, None] = '0020_economy'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'rumors',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('author_uid', sa.BigInteger(), nullable=False),
        sa.Column('character_id', sa.BigInteger(), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=True),
        sa.Column('region_id', sa.BigInteger(), nullable=True),
        sa.Column('truth', sa.String(length=16), nullable=False),
        sa.Column('secret', sa.Boolean(), nullable=False),
        sa.Column('planted', sa.Boolean(), nullable=False),
        sa.Column('heard', sa.Integer(), nullable=False),
        sa.Column('spread_message_id', sa.BigInteger(), nullable=True),
        sa.Column('pinned', sa.Boolean(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['region_id'], ['regions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_rumors_guild_id', 'rumors', ['guild_id'])
    op.create_table(
        'rumor_heard',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('rumor_id', sa.BigInteger(), nullable=False),
        sa.Column('character_id', sa.BigInteger(), nullable=False),
        sa.Column('heard_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['rumor_id'], ['rumors.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_rumor_heard_rumor_id', 'rumor_heard', ['rumor_id'])
    op.create_index('ix_rumor_heard_character_id', 'rumor_heard', ['character_id'])
    op.create_table(
        'rumor_marks',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('uid', sa.BigInteger(), nullable=True),
        sa.Column('character_id', sa.BigInteger(), nullable=True),
        sa.Column('day', sa.String(length=10), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_rumor_marks_guild_id', 'rumor_marks', ['guild_id'])
    op.create_table(
        'omen_draws',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('character_id', sa.BigInteger(), nullable=False),
        sa.Column('deck', sa.String(length=32), nullable=False),
        sa.Column('card', sa.String(length=100), nullable=False),
        sa.Column('cycle', sa.Integer(), nullable=False),
        sa.Column('reader_uid', sa.BigInteger(), nullable=True),
        sa.Column('drawn_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_omen_draws_character_id', 'omen_draws', ['character_id'])


def downgrade() -> None:
    op.drop_index('ix_omen_draws_character_id', table_name='omen_draws')
    op.drop_table('omen_draws')
    op.drop_index('ix_rumor_marks_guild_id', table_name='rumor_marks')
    op.drop_table('rumor_marks')
    op.drop_index('ix_rumor_heard_character_id', table_name='rumor_heard')
    op.drop_index('ix_rumor_heard_rumor_id', table_name='rumor_heard')
    op.drop_table('rumor_heard')
    op.drop_index('ix_rumors_guild_id', table_name='rumors')
    op.drop_table('rumors')
