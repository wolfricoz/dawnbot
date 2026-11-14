"""species, occupations and forum tag requirements

Revision ID: 0006_species_occupations
Revises: 0005_proxying
Create Date: 2026-11-14 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006_species_occupations'
down_revision: Union[str, None] = '0005_proxying'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('species',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('creator_uid', sa.BigInteger(), nullable=True),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('benefits', sa.Text(), nullable=True),
    sa.Column('drawbacks', sa.Text(), nullable=True),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('stat_limits', sa.JSON(), nullable=False),
    sa.Column('stat_modifiers', sa.JSON(), nullable=False),
    sa.Column('tag_ids', sa.JSON(), nullable=False),
    sa.Column('forum_thread_id', sa.BigInteger(), nullable=True),
    sa.Column('forum_message_id', sa.BigInteger(), nullable=True),
    sa.Column('review_message_id', sa.BigInteger(), nullable=True),
    sa.Column('pending_changes', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_species_guild_id'), 'species', ['guild_id'], unique=False)
    op.create_index('uq_species_guild_name', 'species', ['guild_id', sa.literal_column('lower(name)')], unique=True)
    op.create_table('occupations',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('max_holders', sa.Integer(), nullable=True),
    sa.Column('min_level', sa.Integer(), nullable=True),
    sa.Column('role_id', sa.BigInteger(), nullable=True),
    sa.Column('staff_only', sa.Boolean(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_occupations_guild_id'), 'occupations', ['guild_id'], unique=False)
    op.create_index('uq_occupation_guild_name', 'occupations', ['guild_id', sa.literal_column('lower(name)')],
                    unique=True)
    op.create_table('tag_requirements',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('forum_channel_id', sa.BigInteger(), nullable=False),
    sa.Column('tag_id', sa.BigInteger(), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('value', sa.BigInteger(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tag_id', 'kind', name='uq_tag_requirement_tag_kind')
    )
    op.create_index(op.f('ix_tag_requirements_guild_id'), 'tag_requirements', ['guild_id'], unique=False)

    op.add_column('characters', sa.Column('species_id', sa.BigInteger(), nullable=True))
    op.add_column('characters', sa.Column('occupation_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key('characters_species_id_fkey', 'characters', 'species', ['species_id'], ['id'],
                          ondelete='SET NULL')
    op.create_foreign_key('characters_occupation_id_fkey', 'characters', 'occupations', ['occupation_id'], ['id'],
                          ondelete='SET NULL')
    op.add_column('drafts', sa.Column('species_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key('drafts_species_id_fkey', 'drafts', 'species', ['species_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    op.drop_constraint('drafts_species_id_fkey', 'drafts', type_='foreignkey')
    op.drop_column('drafts', 'species_id')
    op.drop_constraint('characters_occupation_id_fkey', 'characters', type_='foreignkey')
    op.drop_constraint('characters_species_id_fkey', 'characters', type_='foreignkey')
    op.drop_column('characters', 'occupation_id')
    op.drop_column('characters', 'species_id')
    op.drop_index(op.f('ix_tag_requirements_guild_id'), table_name='tag_requirements')
    op.drop_table('tag_requirements')
    op.drop_index('uq_occupation_guild_name', table_name='occupations')
    op.drop_index(op.f('ix_occupations_guild_id'), table_name='occupations')
    op.drop_table('occupations')
    op.drop_index('uq_species_guild_name', table_name='species')
    op.drop_index(op.f('ix_species_guild_id'), table_name='species')
    op.drop_table('species')
