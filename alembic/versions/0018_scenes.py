"""scenes and the chronicle: scenes with their participants, chronicles with their characters, and members' away dates

Phase C of design/roleplay-tools.md. Comes before the legacy drop, which stays last.

Revision ID: 0018_scenes
Revises: 0017_world
Create Date: 2026-11-15 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0018_scenes'
down_revision: Union[str, None] = '0017_world'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('away_until', sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        'scenes',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('channel_id', sa.BigInteger(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('host_uid', sa.BigInteger(), nullable=False),
        sa.Column('mode', sa.String(length=16), nullable=False),
        sa.Column('state', sa.String(length=16), nullable=False),
        sa.Column('paused_by_fight', sa.BigInteger(), nullable=True),
        sa.Column('location_id', sa.BigInteger(), nullable=True),
        sa.Column('turn_index', sa.Integer(), nullable=False),
        sa.Column('turn_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('card_message_id', sa.BigInteger(), nullable=True),
        sa.Column('last_post_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('idle_warned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('world_start', sa.JSON(), nullable=True),
        sa.Column('world_end', sa.JSON(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('chronicle_id', sa.BigInteger(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_scenes_guild_id', 'scenes', ['guild_id'])
    op.create_index('ix_scenes_channel_id', 'scenes', ['channel_id'])
    op.create_table(
        'scene_participants',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('scene_id', sa.BigInteger(), nullable=False),
        sa.Column('character_id', sa.BigInteger(), nullable=False),
        sa.Column('uid', sa.BigInteger(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('state', sa.String(length=16), nullable=False),
        sa.Column('posts', sa.Integer(), nullable=False),
        sa.Column('words', sa.Integer(), nullable=False),
        sa.Column('skips', sa.Integer(), nullable=False),
        sa.Column('last_post_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_nudged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['scene_id'], ['scenes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_scene_participants_scene_id', 'scene_participants', ['scene_id'])
    op.create_table(
        'chronicles',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('scene_id', sa.BigInteger(), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('channel_id', sa.BigInteger(), nullable=False),
        sa.Column('first_message_id', sa.BigInteger(), nullable=True),
        sa.Column('last_message_id', sa.BigInteger(), nullable=True),
        sa.Column('thread_id', sa.BigInteger(), nullable=True),
        sa.Column('message_id', sa.BigInteger(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('created_by', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['scene_id'], ['scenes.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_chronicles_guild_id', 'chronicles', ['guild_id'])
    op.create_table(
        'chronicle_characters',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('chronicle_id', sa.BigInteger(), nullable=False),
        sa.Column('character_id', sa.BigInteger(), nullable=False),
        sa.Column('posts', sa.Integer(), nullable=False),
        sa.Column('words', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['chronicle_id'], ['chronicles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_chronicle_characters_chronicle_id', 'chronicle_characters', ['chronicle_id'])
    op.create_index('ix_chronicle_characters_character_id', 'chronicle_characters', ['character_id'])


def downgrade() -> None:
    op.drop_index('ix_chronicle_characters_character_id', table_name='chronicle_characters')
    op.drop_index('ix_chronicle_characters_chronicle_id', table_name='chronicle_characters')
    op.drop_table('chronicle_characters')
    op.drop_index('ix_chronicles_guild_id', table_name='chronicles')
    op.drop_table('chronicles')
    op.drop_index('ix_scene_participants_scene_id', table_name='scene_participants')
    op.drop_table('scene_participants')
    op.drop_index('ix_scenes_channel_id', table_name='scenes')
    op.drop_index('ix_scenes_guild_id', table_name='scenes')
    op.drop_table('scenes')
    op.drop_column('users', 'away_until')
