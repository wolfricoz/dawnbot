"""drop the legacy armors, weapons, npcs and monsters tables

THIS DELETES THE OLD ARMOR SETS, WEAPONS, NPCS AND MONSTERS. Nothing reads them any more: weapons and armor live in the
gear catalog (gear_items) and NPCs and monsters in the bestiary. Copy anything worth keeping into those first
with /armory import legacy and /bestiary import legacy. A downgrade brings the tables back empty.

Revision ID: 0027_drop_legacy_combat
Revises: 0026_economy_merchants
Create Date: 2026-11-15 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0027_drop_legacy_combat'
down_revision: Union[str, None] = '0026_economy_merchants'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The old combat_instance_entities pointed at npcs and monsters; 0011 dropped it, so nothing references these.
    op.drop_table('armors')
    op.drop_table('weapons')
    op.drop_table('npcs')
    op.drop_table('monsters')


def downgrade() -> None:
    op.create_table('armors',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('hp', sa.BigInteger(), nullable=False),
    sa.Column('ap', sa.BigInteger(), nullable=False),
    sa.Column('ac', sa.BigInteger(), nullable=False),
    sa.Column('hitchance', sa.BigInteger(), nullable=False),
    sa.Column('modifier', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('weapons',
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('dice', sa.String(length=255), nullable=False),
    sa.Column('modifier', sa.String(length=255), nullable=False),
    sa.Column('hitmodifier', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('name')
    )
    for table in ('npcs', 'monsters') :
        op.create_table(table,
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('hp', sa.BigInteger(), nullable=False),
        sa.Column('ac', sa.BigInteger(), nullable=False),
        sa.Column('attack', sa.String(length=1024), nullable=False),
        sa.Column('damage', sa.String(length=1024), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id')
        )
