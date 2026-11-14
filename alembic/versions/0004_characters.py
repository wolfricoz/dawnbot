"""characters: review states, sheets, DM interview drafts and stored images

Revision ID: 0004_characters
Revises: 0003_server_setup
Create Date: 2026-11-14 18:49:29.952250

Reworks characters for the character sheet, staff review and SPECIAL rules.

THIS DELETES EVERY EXISTING CHARACTER, together with its info fields and its entries in combat instances. The old
characters were made with other stat rules and never went through a review; the old system was never really used.
Armor sets, weapons and members' XP and currency are not touched.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004_characters'
down_revision: Union[str, None] = '0003_server_setup'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # character_info and combat_instance_entities reference characters with ON DELETE CASCADE.
    op.execute("DELETE FROM characters")

    op.create_table('sheet_fields',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('section', sa.String(length=100), nullable=True),
    sa.Column('label', sa.String(length=100), nullable=False),
    sa.Column('help', sa.Text(), nullable=True),
    sa.Column('type', sa.String(length=16), nullable=False),
    sa.Column('required', sa.Boolean(), nullable=False),
    sa.Column('max_length', sa.Integer(), nullable=True),
    sa.Column('min_value', sa.BigInteger(), nullable=True),
    sa.Column('max_value', sa.BigInteger(), nullable=True),
    sa.Column('choices', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sheet_fields_guild_id'), 'sheet_fields', ['guild_id'], unique=False)
    op.create_table('stored_images',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('storage_channel_id', sa.BigInteger(), nullable=False),
    sa.Column('storage_message_id', sa.BigInteger(), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('drafts',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('uid', sa.BigInteger(), nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('target_id', sa.BigInteger(), nullable=True),
    sa.Column('step', sa.String(length=64), nullable=False),
    sa.Column('answers', sa.JSON(), nullable=False),
    sa.Column('rolled_values', sa.JSON(), nullable=True),
    sa.Column('rerolls', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['target_id'], ['characters.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('uid')
    )

    op.add_column('character_info', sa.Column('sheet_field_id', sa.BigInteger(), nullable=True))
    op.alter_column('character_info', 'value',
               existing_type=sa.VARCHAR(length=1024),
               type_=sa.Text(),
               existing_nullable=False)
    op.create_foreign_key('character_info_sheet_field_id_fkey', 'character_info', 'sheet_fields', ['sheet_field_id'],
                          ['id'], ondelete='SET NULL')

    # The single armor slot goes; characters get their armor from their gear later on.
    op.drop_constraint(op.f('characters_armor_fkey'), 'characters', type_='foreignkey')
    op.drop_column('characters', 'armor')
    # prestige always held a character's spare points.
    op.alter_column('characters', 'prestige', new_column_name='unspent_points')

    op.add_column('characters', sa.Column('state', sa.String(length=16), server_default='pending', nullable=False))
    op.add_column('characters', sa.Column('suffix', sa.String(length=255), nullable=True))
    op.add_column('characters', sa.Column('avatar_id', sa.BigInteger(), nullable=True))
    op.add_column('characters', sa.Column('stat_method', sa.String(length=16), nullable=True))
    op.add_column('characters', sa.Column('rerolls', sa.Integer(), server_default='0', nullable=False))
    op.add_column('characters', sa.Column('xp', sa.BigInteger(), server_default='0', nullable=False))
    op.add_column('characters', sa.Column('level', sa.Integer(), server_default='1', nullable=False))
    op.add_column('characters', sa.Column('currency', sa.BigInteger(), server_default='0', nullable=False))
    op.add_column('characters', sa.Column('forum_thread_id', sa.BigInteger(), nullable=True))
    op.add_column('characters', sa.Column('forum_message_ids', sa.JSON(), nullable=True))
    op.add_column('characters', sa.Column('review_message_id', sa.BigInteger(), nullable=True))
    op.add_column('characters', sa.Column('pending_changes', sa.JSON(), nullable=True))
    op.add_column('characters', sa.Column('approved_by', sa.BigInteger(), nullable=True))
    op.add_column('characters', sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key('characters_avatar_id_fkey', 'characters', 'stored_images', ['avatar_id'], ['id'],
                          ondelete='SET NULL')

    # Names were unique per user; they are now unique per user per server, compared without case.
    op.drop_constraint(op.f('uq_character_uid_name'), 'characters', type_='unique')
    op.create_index('uq_character_uid_guild_name', 'characters', ['uid', 'guild_id', sa.literal_column('lower(name)')],
                    unique=True)


def downgrade() -> None:
    # Characters made under the new rules do not fit the old table (their names can repeat across servers).
    op.execute("DELETE FROM characters")

    op.drop_index('uq_character_uid_guild_name', table_name='characters')
    op.create_unique_constraint(op.f('uq_character_uid_name'), 'characters', ['uid', 'name'])

    op.drop_constraint('characters_avatar_id_fkey', 'characters', type_='foreignkey')
    op.drop_column('characters', 'approved_at')
    op.drop_column('characters', 'approved_by')
    op.drop_column('characters', 'pending_changes')
    op.drop_column('characters', 'review_message_id')
    op.drop_column('characters', 'forum_message_ids')
    op.drop_column('characters', 'forum_thread_id')
    op.drop_column('characters', 'currency')
    op.drop_column('characters', 'level')
    op.drop_column('characters', 'xp')
    op.drop_column('characters', 'rerolls')
    op.drop_column('characters', 'stat_method')
    op.drop_column('characters', 'avatar_id')
    op.drop_column('characters', 'suffix')
    op.drop_column('characters', 'state')

    op.alter_column('characters', 'unspent_points', new_column_name='prestige')
    op.add_column('characters', sa.Column('armor', sa.BIGINT(), autoincrement=False, nullable=True))
    op.create_foreign_key(op.f('characters_armor_fkey'), 'characters', 'armors', ['armor'], ['id'])

    op.drop_constraint('character_info_sheet_field_id_fkey', 'character_info', type_='foreignkey')
    op.alter_column('character_info', 'value',
               existing_type=sa.Text(),
               type_=sa.VARCHAR(length=1024),
               existing_nullable=False)
    op.drop_column('character_info', 'sheet_field_id')

    op.drop_table('drafts')
    op.drop_table('stored_images')
    op.drop_index(op.f('ix_sheet_fields_guild_id'), table_name='sheet_fields')
    op.drop_table('sheet_fields')
