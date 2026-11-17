"""the world: in-world calendar and events, regions, locations, routes, weather and travel; character birthdays

Phase B of design/roleplay-tools.md. Comes before the legacy drop (0026_drop_legacy_combat).

Revision ID: 0017_world
Revises: 0016_checks_tables
Create Date: 2026-11-15 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0017_world'
down_revision: Union[str, None] = '0016_checks_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'calendars',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('preset', sa.String(length=32), nullable=False),
        sa.Column('months', sa.JSON(), nullable=False),
        sa.Column('weekdays', sa.JSON(), nullable=False),
        sa.Column('era', sa.String(length=32), nullable=True),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('day', sa.Integer(), nullable=False),
        sa.Column('part', sa.Integer(), nullable=False),
        sa.Column('moon_cycle', sa.Integer(), nullable=True),
        sa.Column('last_tick', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('guild_id'),
    )
    op.create_table(
        'calendar_events',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('day', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('last_year', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_calendar_events_guild_id', 'calendar_events', ['guild_id'])
    op.create_table(
        'regions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('climate', sa.String(length=16), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_regions_guild_id', 'regions', ['guild_id'])
    op.create_index('uq_region_guild_name', 'regions', ['guild_id', sa.text('lower(name)')], unique=True)
    op.create_table(
        'locations',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('channel_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('image_id', sa.BigInteger(), nullable=True),
        sa.Column('region_id', sa.BigInteger(), nullable=True),
        sa.Column('climate', sa.String(length=16), nullable=True),
        sa.Column('indoor', sa.Boolean(), nullable=False),
        sa.Column('danger', sa.Integer(), nullable=False),
        sa.Column('hazards', sa.Text(), nullable=True),
        sa.Column('table_id', sa.BigInteger(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(['image_id'], ['stored_images.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['region_id'], ['regions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['table_id'], ['roll_tables.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('channel_id'),
    )
    op.create_index('ix_locations_guild_id', 'locations', ['guild_id'])
    op.create_table(
        'routes',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('from_id', sa.BigInteger(), nullable=False),
        sa.Column('to_id', sa.BigInteger(), nullable=False),
        sa.Column('hours', sa.Integer(), nullable=False),
        sa.Column('danger', sa.Integer(), nullable=False),
        sa.Column('table_id', sa.BigInteger(), nullable=True),
        sa.Column('two_way', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['from_id'], ['locations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['to_id'], ['locations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['table_id'], ['roll_tables.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_routes_guild_id', 'routes', ['guild_id'])
    op.create_table(
        'weather_states',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('region_id', sa.BigInteger(), nullable=True),
        sa.Column('climate', sa.String(length=16), nullable=False),
        sa.Column('weather', sa.String(length=32), nullable=False),
        sa.Column('forced', sa.Boolean(), nullable=False),
        sa.Column('world_day', sa.Integer(), nullable=True),
        sa.Column('since', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['region_id'], ['regions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_weather_states_guild_id', 'weather_states', ['guild_id'])
    op.create_table(
        'travels',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('character_id', sa.BigInteger(), nullable=False),
        sa.Column('from_id', sa.BigInteger(), nullable=True),
        sa.Column('to_id', sa.BigInteger(), nullable=False),
        sa.Column('arrive_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('state', sa.String(length=16), nullable=False),
        sa.Column('encounter', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['from_id'], ['locations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['to_id'], ['locations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_travels_guild_id', 'travels', ['guild_id'])
    op.add_column('characters', sa.Column('birthday', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('characters', 'birthday')
    for table in ('travels', 'weather_states', 'routes', 'locations'):
        op.drop_index(f'ix_{table}_guild_id', table_name=table)
        op.drop_table(table)
    op.drop_index('uq_region_guild_name', table_name='regions')
    op.drop_index('ix_regions_guild_id', table_name='regions')
    op.drop_table('regions')
    op.drop_index('ix_calendar_events_guild_id', table_name='calendar_events')
    op.drop_table('calendar_events')
    op.drop_table('calendars')
