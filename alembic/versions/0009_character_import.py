"""characters remember which character they were imported from

Revision ID: 0009_character_import
Revises: 0008_drop_user_currency
Create Date: 2026-11-15 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0009_character_import'
down_revision: Union[str, None] = '0008_drop_user_currency'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('characters', sa.Column('imported_from', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column('characters', 'imported_from')
