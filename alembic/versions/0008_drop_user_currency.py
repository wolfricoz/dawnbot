"""drop user currency: currency now belongs to characters

Revision ID: 0008_drop_user_currency
Revises: 0007_gear
Create Date: 2026-11-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0008_drop_user_currency'
down_revision: Union[str, None] = '0007_gear'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('experience', 'currency')


def downgrade() -> None:
    op.add_column('experience', sa.Column('currency', sa.BigInteger(), server_default='0', nullable=False))
