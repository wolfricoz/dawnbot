"""Add_Guild_To_Users

Revision ID: ec05f2e34cee
Revises: ddbeb8325a18
Create Date: 2024-07-06 18:09:30.078376

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ec05f2e34cee'
down_revision: Union[str, None] = 'ddbeb8325a18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('guildid', sa.BigInteger, default=559139888356917259, nullable=False, server_default='559139888356917259', primary_key=True))


def downgrade() -> None:
    op.drop_column('users', 'guildid')
