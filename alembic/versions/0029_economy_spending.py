"""economy phase 6: starter kits, weapon training and lifestyle

Phase 6 of design/economy.md: occupations.kit and occupations.trains, characters.lifestyle and lifestyle_paid_until,
and the trainings table. Healers need no new data (injuries stay on the sheet). Comes after the legacy drop (0026_drop_legacy_combat).

Revision ID: 0029_economy_spending
Revises: 0028_economy_magic
Create Date: 2026-11-17 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0029_economy_spending'
down_revision: Union[str, None] = '0028_economy_magic'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('occupations', sa.Column('kit', sa.JSON(), nullable=True))
    op.add_column('occupations', sa.Column('trains', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('characters', sa.Column('lifestyle', sa.String(length=16), nullable=True))
    op.add_column('characters', sa.Column('lifestyle_paid_until', sa.DateTime(timezone=True), nullable=True))
    op.create_table('trainings',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('character_id', sa.BigInteger(), nullable=False),
    sa.Column('entry_id', sa.BigInteger(), nullable=False),
    sa.Column('target', sa.String(length=16), nullable=False),
    sa.Column('days_done', sa.Integer(), nullable=False),
    sa.Column('days_needed', sa.Integer(), nullable=False),
    sa.Column('paid', sa.BigInteger(), nullable=False),
    sa.Column('trainer', sa.String(length=100), nullable=True),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['entry_id'], ['character_gear.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trainings_character_id'), 'trainings', ['character_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_trainings_character_id'), table_name='trainings')
    op.drop_table('trainings')
    op.drop_column('characters', 'lifestyle_paid_until')
    op.drop_column('characters', 'lifestyle')
    op.drop_column('occupations', 'trains')
    op.drop_column('occupations', 'kit')
