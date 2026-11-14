"""characters can be made global, so their sheet shows on their player's small servers

Revision ID: 0010_global_characters
Revises: 0009_character_import
Create Date: 2026-11-15 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0010_global_characters'
down_revision: Union[str, None] = '0009_character_import'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('characters', sa.Column('is_global', sa.Boolean(), server_default=sa.text('false'), nullable=False))


def downgrade() -> None:
    op.drop_column('characters', 'is_global')
