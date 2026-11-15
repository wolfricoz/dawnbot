"""languages and letters: languages, who knows them, originals of posts made in them, letters; characters' speaking
language and omen, species languages

Phase D of design/roleplay-tools.md (the omen column is used by phase F). Comes before the legacy drop, which stays
last.

Revision ID: 0019_languages_letters
Revises: 0018_scenes
Create Date: 2026-11-15 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0019_languages_letters'
down_revision: Union[str, None] = '0018_scenes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'languages',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sound', sa.String(length=16), nullable=False),
        sa.Column('syllables', sa.JSON(), nullable=True),
        sa.Column('common', sa.Boolean(), nullable=False),
        sa.Column('pack', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_languages_guild_id', 'languages', ['guild_id'])
    op.create_index('uq_language_guild_name', 'languages', ['guild_id', sa.text('lower(name)')], unique=True)
    op.create_table(
        'character_languages',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('character_id', sa.BigInteger(), nullable=False),
        sa.Column('language_id', sa.BigInteger(), nullable=False),
        sa.Column('fluency', sa.String(length=16), nullable=False),
        sa.Column('source', sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['language_id'], ['languages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('character_id', 'language_id', name='uq_character_language'),
    )
    op.create_index('ix_character_languages_character_id', 'character_languages', ['character_id'])
    op.create_table(
        'proxy_languages',
        sa.Column('first_message_id', sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column('character_id', sa.BigInteger(), nullable=True),
        sa.Column('segments', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('first_message_id'),
    )
    op.create_table(
        'letters',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('from_character_id', sa.BigInteger(), nullable=True),
        sa.Column('to_character_id', sa.BigInteger(), nullable=True),
        sa.Column('from_uid', sa.BigInteger(), nullable=False),
        sa.Column('from_name', sa.String(length=255), nullable=False),
        sa.Column('to_name', sa.String(length=255), nullable=False),
        sa.Column('subject', sa.String(length=200), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('language_id', sa.BigInteger(), nullable=True),
        sa.Column('sealed', sa.Boolean(), nullable=False),
        sa.Column('seal_broken', sa.Boolean(), nullable=False),
        sa.Column('express', sa.Boolean(), nullable=False),
        sa.Column('world_date', sa.JSON(), nullable=True),
        sa.Column('deliver_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('state', sa.String(length=16), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reply_to_id', sa.BigInteger(), nullable=True),
        sa.Column('reported_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('intercepted_by', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['from_character_id'], ['characters.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['to_character_id'], ['characters.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['language_id'], ['languages.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_letters_guild_id', 'letters', ['guild_id'])
    op.add_column('characters', sa.Column('speaking_language_id', sa.BigInteger(), nullable=True))
    op.add_column('characters', sa.Column('omen', sa.JSON(), nullable=True))
    op.add_column('species', sa.Column('language_ids', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('species', 'language_ids')
    op.drop_column('characters', 'omen')
    op.drop_column('characters', 'speaking_language_id')
    op.drop_index('ix_letters_guild_id', table_name='letters')
    op.drop_table('letters')
    op.drop_table('proxy_languages')
    op.drop_index('ix_character_languages_character_id', table_name='character_languages')
    op.drop_table('character_languages')
    op.drop_index('uq_language_guild_name', table_name='languages')
    op.drop_index('ix_languages_guild_id', table_name='languages')
    op.drop_table('languages')
