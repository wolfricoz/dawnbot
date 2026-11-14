"""add the shared servers, config and staff tables

Revision ID: 0002_config_staff_servers
Revises: 0001_baseline
Create Date: 2026-11-14 10:02:35.550505

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002_config_staff_servers'
down_revision: Union[str, None] = '0001_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('servers',
    sa.Column('id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('owner', sa.String(length=1024), nullable=False),
    sa.Column('name', sa.String(length=1024), nullable=False),
    sa.Column('member_count', sa.BigInteger(), nullable=False),
    sa.Column('hidden', sa.Boolean(), nullable=False),
    sa.Column('invite', sa.String(length=256), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('premium', sa.DateTime(timezone=True), nullable=True),
    sa.Column('owner_id', sa.BigInteger(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('staff',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('uid', sa.BigInteger(), nullable=False),
    sa.Column('role', sa.String(length=128), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('config',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('guild', sa.BigInteger(), nullable=False),
    sa.Column('key', sa.String(length=512), nullable=False),
    sa.Column('value', sa.String(length=1980), nullable=False),
    sa.ForeignKeyConstraint(['guild'], ['servers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('config')
    op.drop_table('staff')
    op.drop_table('servers')
