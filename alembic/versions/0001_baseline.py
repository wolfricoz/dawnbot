"""baseline: the schema dawnbot had before the restructure (previously built by create_all)

Revision ID: 0001_baseline
Revises: 
Create Date: 2026-11-14 10:02:35.550505

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_baseline'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
    op.create_table('channels',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('guildid', sa.BigInteger(), nullable=False),
    sa.Column('channelid', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('combat_instances',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('guid', sa.String(length=255), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('channel_id', sa.BigInteger(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('round', sa.BigInteger(), nullable=False),
    sa.Column('combat_type', sa.String(length=255), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('levels',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('guildid', sa.BigInteger(), nullable=False),
    sa.Column('role_id', sa.BigInteger(), nullable=False),
    sa.Column('xp_required', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('monsters',
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
    op.create_table('npcs',
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
    op.create_table('users',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('uid', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('uid')
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
    op.create_table('characters',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('uid', sa.BigInteger(), nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('prestige', sa.BigInteger(), nullable=False),
    sa.Column('strength', sa.BigInteger(), nullable=False),
    sa.Column('perception', sa.BigInteger(), nullable=False),
    sa.Column('endurance', sa.BigInteger(), nullable=False),
    sa.Column('charisma', sa.BigInteger(), nullable=False),
    sa.Column('intelligence', sa.BigInteger(), nullable=False),
    sa.Column('agility', sa.BigInteger(), nullable=False),
    sa.Column('luck', sa.BigInteger(), nullable=False),
    sa.Column('armor', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['armor'], ['armors.id'], ),
    sa.ForeignKeyConstraint(['uid'], ['users.uid'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('uid', 'name', name='uq_character_uid_name')
    )
    op.create_table('experience',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('uid', sa.BigInteger(), nullable=False),
    sa.Column('messages', sa.BigInteger(), nullable=False),
    sa.Column('xp', sa.BigInteger(), nullable=False),
    sa.Column('currency', sa.BigInteger(), nullable=False),
    sa.Column('guildid', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['uid'], ['users.uid'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('uid', 'guildid', name='uq_experience_uid_guildid')
    )
    op.create_table('combat_instance_entities',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('instance_id', sa.BigInteger(), nullable=False),
    sa.Column('user_uid', sa.BigInteger(), nullable=True),
    sa.Column('character_id', sa.BigInteger(), nullable=True),
    sa.Column('monster_id', sa.BigInteger(), nullable=True),
    sa.Column('npc_id', sa.BigInteger(), nullable=True),
    sa.Column('current_hp', sa.BigInteger(), nullable=False),
    sa.Column('current_ap', sa.BigInteger(), nullable=False),
    sa.Column('ac', sa.BigInteger(), nullable=False),
    sa.Column('entity_type', sa.String(length=255), nullable=True),
    sa.Column('remaining_attacks', sa.BigInteger(), nullable=False),
    sa.Column('alive', sa.Boolean(), nullable=False),
    sa.Column('stunned', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.Integer(), nullable=False),
    sa.CheckConstraint('\n\t\t\t(character_id IS NOT NULL AND monster_id IS NULL AND npc_id IS NULL) OR\n\t\t\t(character_id IS NULL AND monster_id IS NOT NULL AND npc_id IS NULL) OR\n\t\t\t(character_id IS NULL AND monster_id IS NULL AND npc_id IS NOT NULL)\n\t\t\t', name='chk_single_entity_source'),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['instance_id'], ['combat_instances.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['monster_id'], ['monsters.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['npc_id'], ['npcs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_uid'], ['users.uid'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('combat_instance_log',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('instance_id', sa.BigInteger(), nullable=False),
    sa.Column('attacker_id', sa.BigInteger(), nullable=False),
    sa.Column('defender_id', sa.BigInteger(), nullable=False),
    sa.Column('damage', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['attacker_id'], ['combat_instance_entities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['defender_id'], ['combat_instance_entities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['instance_id'], ['combat_instances.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('combat_instance_log')
    op.drop_table('combat_instance_entities')
    op.drop_table('experience')
    op.drop_table('characters')
    op.drop_table('weapons')
    op.drop_table('users')
    op.drop_table('npcs')
    op.drop_table('monsters')
    op.drop_table('levels')
    op.drop_table('combat_instances')
    op.drop_table('channels')
    op.drop_table('armors')
