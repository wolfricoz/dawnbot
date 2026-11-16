"""checks and roll tables: GM checks with their rolls, roll tables with their entries, and rolls made on tables

Phase A of design/roleplay-tools.md. Comes before 0025_drop_legacy_combat, which waits until the old tables have been
imported.

Revision ID: 0016_checks_tables
Revises: 0015_ability_effects
Create Date: 2026-11-15 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0016_checks_tables'
down_revision: Union[str, None] = '0015_ability_effects'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'checks',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('channel_id', sa.BigInteger(), nullable=False),
        sa.Column('message_id', sa.BigInteger(), nullable=True),
        sa.Column('caller_uid', sa.BigInteger(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=True),
        sa.Column('stat', sa.String(length=16), nullable=False),
        sa.Column('dc', sa.Integer(), nullable=True),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('visibility', sa.String(length=16), nullable=False),
        sa.Column('modifier', sa.Integer(), nullable=False),
        sa.Column('allowed', sa.JSON(), nullable=False),
        sa.Column('opposed', sa.JSON(), nullable=True),
        sa.Column('helps', sa.JSON(), nullable=False),
        sa.Column('state', sa.String(length=16), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_checks_guild_id', 'checks', ['guild_id'])

    op.create_table(
        'check_rolls',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('check_id', sa.BigInteger(), nullable=False),
        sa.Column('character_id', sa.BigInteger(), nullable=True),
        sa.Column('uid', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('side', sa.Integer(), nullable=False),
        sa.Column('stat', sa.String(length=16), nullable=False),
        sa.Column('natural', sa.Integer(), nullable=False),
        sa.Column('total', sa.Integer(), nullable=False),
        sa.Column('outcome', sa.String(length=16), nullable=False),
        sa.Column('helped_by', sa.String(length=255), nullable=True),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['check_id'], ['checks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('check_id', 'character_id', name='uq_check_roll_character'),
    )
    op.create_index('ix_check_rolls_check_id', 'check_rolls', ['check_id'])

    op.create_table(
        'roll_tables',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('dice', sa.String(length=16), nullable=False),
        sa.Column('luck', sa.Boolean(), nullable=False),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('visibility', sa.String(length=16), nullable=False),
        sa.Column('pack', sa.String(length=50), nullable=True),
        sa.Column('creator_uid', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_roll_tables_guild_id', 'roll_tables', ['guild_id'])
    op.create_index('uq_roll_table_guild_name', 'roll_tables', ['guild_id', sa.text('lower(name)')], unique=True)

    op.create_table(
        'roll_table_entries',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('table_id', sa.BigInteger(), nullable=False),
        sa.Column('low', sa.Integer(), nullable=True),
        sa.Column('high', sa.Integer(), nullable=True),
        sa.Column('weight', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('actions', sa.JSON(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['table_id'], ['roll_tables.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_roll_table_entries_table_id', 'roll_table_entries', ['table_id'])

    op.create_table(
        'table_rolls',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('table_id', sa.BigInteger(), nullable=True),
        sa.Column('table_name', sa.String(length=100), nullable=False),
        sa.Column('uid', sa.BigInteger(), nullable=False),
        sa.Column('character_id', sa.BigInteger(), nullable=True),
        sa.Column('channel_id', sa.BigInteger(), nullable=True),
        sa.Column('natural', sa.Integer(), nullable=False),
        sa.Column('rolled', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('actions', sa.JSON(), nullable=False),
        sa.Column('granted_to', sa.JSON(), nullable=False),
        sa.Column('fight_id', sa.BigInteger(), nullable=True),
        sa.Column('secret', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['table_id'], ['roll_tables.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_table_rolls_guild_id', 'table_rolls', ['guild_id'])


def downgrade() -> None:
    op.drop_index('ix_table_rolls_guild_id', table_name='table_rolls')
    op.drop_table('table_rolls')
    op.drop_index('ix_roll_table_entries_table_id', table_name='roll_table_entries')
    op.drop_table('roll_table_entries')
    op.drop_index('uq_roll_table_guild_name', table_name='roll_tables')
    op.drop_index('ix_roll_tables_guild_id', table_name='roll_tables')
    op.drop_table('roll_tables')
    op.drop_index('ix_check_rolls_check_id', table_name='check_rolls')
    op.drop_table('check_rolls')
    op.drop_index('ix_checks_guild_id', table_name='checks')
    op.drop_table('checks')
