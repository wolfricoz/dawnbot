"""the economy round: factions and standing, jobs and claims, downtime, language study, recipes and crafting projects;
occupation work settings, faction and salvage data on catalog items, stacks and quality on owned gear

Phase E of design/roleplay-tools.md. Comes before the legacy drop, which stays last.

Revision ID: 0020_economy
Revises: 0019_languages_letters
Create Date: 2026-11-15 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0020_economy'
down_revision: Union[str, None] = '0019_languages_letters'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'factions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('colour', sa.Integer(), nullable=True),
        sa.Column('emoji', sa.String(length=64), nullable=True),
        sa.Column('hidden', sa.Boolean(), nullable=False),
        sa.Column('rivals', sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_factions_guild_id', 'factions', ['guild_id'])
    op.create_index('uq_faction_guild_name', 'factions', ['guild_id', sa.text('lower(name)')], unique=True)
    op.create_table(
        'character_reputation',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('character_id', sa.BigInteger(), nullable=False),
        sa.Column('faction_id', sa.BigInteger(), nullable=False),
        sa.Column('value', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['faction_id'], ['factions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('character_id', 'faction_id', name='uq_character_reputation'),
    )
    op.create_index('ix_character_reputation_character_id', 'character_reputation', ['character_id'])
    op.create_table(
        'reputation_log',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('character_id', sa.BigInteger(), nullable=False),
        sa.Column('faction_id', sa.BigInteger(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=32), nullable=False),
        sa.Column('actor_uid', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['faction_id'], ['factions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_reputation_log_character_id', 'reputation_log', ['character_id'])
    op.create_table(
        'jobs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('thread_id', sa.BigInteger(), nullable=True),
        sa.Column('message_id', sa.BigInteger(), nullable=True),
        sa.Column('poster_uid', sa.BigInteger(), nullable=False),
        sa.Column('poster_character_id', sa.BigInteger(), nullable=True),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('reward', sa.JSON(), nullable=False),
        sa.Column('slots', sa.Integer(), nullable=False),
        sa.Column('min_level', sa.Integer(), nullable=False),
        sa.Column('faction_id', sa.BigInteger(), nullable=True),
        sa.Column('rep_success', sa.Integer(), nullable=False),
        sa.Column('rep_failure', sa.Integer(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=True),
        sa.Column('deadline', sa.DateTime(timezone=True), nullable=True),
        sa.Column('state', sa.String(length=16), nullable=False),
        sa.Column('escrow', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['poster_character_id'], ['characters.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['faction_id'], ['factions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_jobs_guild_id', 'jobs', ['guild_id'])
    op.create_table(
        'job_claims',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('job_id', sa.BigInteger(), nullable=False),
        sa.Column('character_id', sa.BigInteger(), nullable=False),
        sa.Column('uid', sa.BigInteger(), nullable=False),
        sa.Column('state', sa.String(length=16), nullable=False),
        sa.Column('outcome', sa.String(length=16), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_job_claims_job_id', 'job_claims', ['job_id'])
    op.create_table(
        'downtime',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('character_id', sa.BigInteger(), nullable=False),
        sa.Column('day', sa.String(length=10), nullable=False),
        sa.Column('activity', sa.String(length=16), nullable=False),
        sa.Column('outcome', sa.String(length=16), nullable=False),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('character_id', 'day', name='uq_downtime_character_day'),
    )
    op.create_index('ix_downtime_character_id', 'downtime', ['character_id'])
    op.create_table(
        'study_progress',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('character_id', sa.BigInteger(), nullable=False),
        sa.Column('language_id', sa.BigInteger(), nullable=False),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['language_id'], ['languages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('character_id', 'language_id', name='uq_study_progress'),
    )
    op.create_index('ix_study_progress_character_id', 'study_progress', ['character_id'])
    op.create_table(
        'recipes',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('result_item_id', sa.BigInteger(), nullable=True),
        sa.Column('result_amount', sa.Integer(), nullable=False),
        sa.Column('ingredients', sa.JSON(), nullable=False),
        sa.Column('tool_item_id', sa.BigInteger(), nullable=True),
        sa.Column('stat', sa.String(length=16), nullable=False),
        sa.Column('dc', sa.Integer(), nullable=False),
        sa.Column('occupation_id', sa.BigInteger(), nullable=True),
        sa.Column('occupation_required', sa.Boolean(), nullable=False),
        sa.Column('min_level', sa.Integer(), nullable=False),
        sa.Column('faction_id', sa.BigInteger(), nullable=True),
        sa.Column('days', sa.Integer(), nullable=False),
        sa.Column('mishap_table_id', sa.BigInteger(), nullable=True),
        sa.Column('pack', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['result_item_id'], ['gear_items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tool_item_id'], ['gear_items.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['occupation_id'], ['occupations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['faction_id'], ['factions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['mishap_table_id'], ['roll_tables.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_recipes_guild_id', 'recipes', ['guild_id'])
    op.create_index('uq_recipe_guild_name', 'recipes', ['guild_id', sa.text('lower(name)')], unique=True)
    op.create_table(
        'craft_projects',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('character_id', sa.BigInteger(), nullable=False),
        sa.Column('recipe_id', sa.BigInteger(), nullable=True),
        sa.Column('days_done', sa.Integer(), nullable=False),
        sa.Column('masterwork', sa.Boolean(), nullable=False),
        sa.Column('state', sa.String(length=16), nullable=False),
        sa.Column('reserved', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_craft_projects_character_id', 'craft_projects', ['character_id'])
    op.add_column('occupations', sa.Column('pay', sa.Integer(), nullable=True))
    op.add_column('occupations', sa.Column('work_stat', sa.String(length=16), nullable=True))
    op.add_column('occupations', sa.Column('table_id', sa.BigInteger(), nullable=True))
    op.add_column('occupations', sa.Column('flavor', sa.JSON(), nullable=True))
    op.add_column('occupations', sa.Column('seer', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('gear_items', sa.Column('faction_id', sa.BigInteger(), nullable=True))
    op.add_column('gear_items', sa.Column('faction_tier', sa.String(length=16), nullable=True))
    op.add_column('gear_items', sa.Column('salvage', sa.JSON(), nullable=True))
    op.add_column('character_gear', sa.Column('quantity', sa.Integer(), server_default='1', nullable=False))
    op.add_column('character_gear', sa.Column('quality', sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column('character_gear', 'quality')
    op.drop_column('character_gear', 'quantity')
    op.drop_column('gear_items', 'salvage')
    op.drop_column('gear_items', 'faction_tier')
    op.drop_column('gear_items', 'faction_id')
    for column in ('seer', 'flavor', 'table_id', 'work_stat', 'pay'):
        op.drop_column('occupations', column)
    op.drop_index('ix_craft_projects_character_id', table_name='craft_projects')
    op.drop_table('craft_projects')
    op.drop_index('uq_recipe_guild_name', table_name='recipes')
    op.drop_index('ix_recipes_guild_id', table_name='recipes')
    op.drop_table('recipes')
    op.drop_index('ix_study_progress_character_id', table_name='study_progress')
    op.drop_table('study_progress')
    op.drop_index('ix_downtime_character_id', table_name='downtime')
    op.drop_table('downtime')
    op.drop_index('ix_job_claims_job_id', table_name='job_claims')
    op.drop_table('job_claims')
    op.drop_index('ix_jobs_guild_id', table_name='jobs')
    op.drop_table('jobs')
    op.drop_index('ix_reputation_log_character_id', table_name='reputation_log')
    op.drop_table('reputation_log')
    op.drop_index('ix_character_reputation_character_id', table_name='character_reputation')
    op.drop_table('character_reputation')
    op.drop_index('uq_faction_guild_name', table_name='factions')
    op.drop_index('ix_factions_guild_id', table_name='factions')
    op.drop_table('factions')
