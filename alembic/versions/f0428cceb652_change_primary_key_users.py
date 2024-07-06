"""Change_Primary_key_Users

Revision ID: f0428cceb652
Revises: ec05f2e34cee
Create Date: 2024-07-06 18:39:15.173169

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f0428cceb652'
down_revision: Union[str, None] = 'ec05f2e34cee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # op.drop_constraint('users_pk', 'users', type_='primary')
    op.create_primary_key('users_pk', 'users', ['guildid', 'uid'])


def downgrade() -> None:
    op.drop_constraint('users_pk', 'users', type_='primary')
    op.alter_column('users', 'uid', new_column_name='uid', type_=sa.BigInteger, autoincrement=False, nullable=False, primary_key=True)
