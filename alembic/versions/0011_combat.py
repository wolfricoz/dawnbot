"""combat: instanced fights, the bestiary, damage types, abilities and magic schools, legendary characters and
weapon/armor proficiency

Replaces the old combat tables (combat_instances, combat_instance_entities, combat_instance_log); fights in progress
under the old system are lost. The old armors, weapons, npcs and monsters tables are dropped separately by
0022_drop_legacy_combat.

Revision ID: 0011_combat
Revises: 0010_global_characters
Create Date: 2026-11-15 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0011_combat'
down_revision: Union[str, None] = '0010_global_characters'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('combat_instance_log')
    op.drop_table('combat_instance_entities')
    op.drop_table('combat_instances')

    op.create_table('combat_instances',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('guid', sa.String(length=64), nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('channel_id', sa.BigInteger(), nullable=True),
    sa.Column('thread_id', sa.BigInteger(), nullable=True),
    sa.Column('board_message_id', sa.BigInteger(), nullable=True),
    sa.Column('gm_uid', sa.BigInteger(), nullable=False),
    sa.Column('co_gms', sa.JSON(), nullable=False),
    sa.Column('kind', sa.String(length=8), nullable=False),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('pacing', sa.String(length=8), nullable=False),
    sa.Column('lethal', sa.Boolean(), nullable=False),
    sa.Column('round', sa.Integer(), nullable=False),
    sa.Column('order', sa.JSON(), nullable=False),
    sa.Column('turn_index', sa.Integer(), nullable=False),
    sa.Column('deadline', sa.DateTime(timezone=True), nullable=True),
    sa.Column('paused_seconds', sa.Integer(), nullable=True),
    sa.Column('title', sa.String(length=100), nullable=False),
    sa.Column('winner_side_id', sa.BigInteger(), nullable=True),
    sa.Column('late_join', sa.Boolean(), nullable=False),
    sa.Column('invites', sa.JSON(), nullable=False),
    sa.Column('pending', sa.JSON(), nullable=False),
    sa.Column('challenge', sa.JSON(), nullable=True),
    sa.Column('idle_pinged', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_combat_instances_guild_id'), 'combat_instances', ['guild_id'], unique=False)
    op.create_index(op.f('ix_combat_instances_thread_id'), 'combat_instances', ['thread_id'], unique=False)

    op.create_table('combat_sides',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('instance_id', sa.BigInteger(), nullable=False),
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['instance_id'], ['combat_instances.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_combat_sides_instance_id'), 'combat_sides', ['instance_id'], unique=False)

    op.create_table('bestiary',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('avatar_url', sa.Text(), nullable=True),
    sa.Column('preset', sa.String(length=16), nullable=False),
    sa.Column('hp', sa.Integer(), nullable=False),
    sa.Column('ac', sa.Integer(), nullable=False),
    sa.Column('dt', sa.Integer(), nullable=False),
    sa.Column('to_hit', sa.Integer(), nullable=False),
    sa.Column('damage', sa.String(length=16), nullable=False),
    sa.Column('damage_type', sa.String(length=50), nullable=True),
    sa.Column('attack_name', sa.String(length=50), nullable=False),
    sa.Column('ap', sa.Integer(), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('behavior', sa.String(length=16), nullable=False),
    sa.Column('ability_ids', sa.JSON(), nullable=False),
    sa.Column('reward_xp', sa.Integer(), nullable=False),
    sa.Column('reward_currency', sa.Integer(), nullable=False),
    sa.Column('creator_uid', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bestiary_guild_id'), 'bestiary', ['guild_id'], unique=False)
    op.create_index('uq_bestiary_guild_name', 'bestiary', ['guild_id', sa.literal_column('lower(name)')], unique=True)

    op.create_table('combat_entities',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('instance_id', sa.BigInteger(), nullable=False),
    sa.Column('side_id', sa.BigInteger(), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('character_id', sa.BigInteger(), nullable=True),
    sa.Column('uid', sa.BigInteger(), nullable=True),
    sa.Column('bestiary_id', sa.BigInteger(), nullable=True),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('controller', sa.String(length=8), nullable=False),
    sa.Column('behavior', sa.String(length=16), nullable=False),
    sa.Column('stats', sa.JSON(), nullable=False),
    sa.Column('hp', sa.Integer(), nullable=False),
    sa.Column('hp_max', sa.Integer(), nullable=False),
    sa.Column('ap', sa.Integer(), nullable=False),
    sa.Column('ap_max', sa.Integer(), nullable=False),
    sa.Column('ac', sa.Integer(), nullable=False),
    sa.Column('dt', sa.Integer(), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('conditions', sa.JSON(), nullable=False),
    sa.Column('ability_uses', sa.JSON(), nullable=False),
    sa.Column('acted', sa.Boolean(), nullable=False),
    sa.Column('idle_turns', sa.Integer(), nullable=False),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('death_successes', sa.Integer(), nullable=False),
    sa.Column('death_failures', sa.Integer(), nullable=False),
    sa.Column('last_attacker_id', sa.BigInteger(), nullable=True),
    sa.Column('weapon_key', sa.String(length=32), nullable=True),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('lethal_ok', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['bestiary_id'], ['bestiary.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['instance_id'], ['combat_instances.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['side_id'], ['combat_sides.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_combat_entities_character_id'), 'combat_entities', ['character_id'], unique=False)
    op.create_index(op.f('ix_combat_entities_instance_id'), 'combat_entities', ['instance_id'], unique=False)

    op.create_table('combat_log',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('instance_id', sa.BigInteger(), nullable=False),
    sa.Column('round', sa.Integer(), nullable=False),
    sa.Column('actor_id', sa.BigInteger(), nullable=True),
    sa.Column('target_id', sa.BigInteger(), nullable=True),
    sa.Column('action', sa.String(length=32), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('details', sa.JSON(), nullable=False),
    sa.Column('snapshot', sa.JSON(none_as_null=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['instance_id'], ['combat_instances.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_combat_log_instance_id'), 'combat_log', ['instance_id'], unique=False)

    op.create_table('damage_types',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.Column('trigger', sa.String(length=16), nullable=False),
    sa.Column('effect', sa.JSON(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('pack', sa.String(length=50), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_damage_types_guild_id'), 'damage_types', ['guild_id'], unique=False)
    op.create_index('uq_damage_type_guild_name', 'damage_types', ['guild_id', sa.literal_column('lower(name)')],
                    unique=True)

    op.create_table('magic_schools',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('casting_stat', sa.String(length=16), nullable=False),
    sa.Column('creator_uid', sa.BigInteger(), nullable=True),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('standard', sa.Boolean(), nullable=False),
    sa.Column('review_message_id', sa.BigInteger(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_magic_schools_guild_id'), 'magic_schools', ['guild_id'], unique=False)
    op.create_index('uq_magic_school_guild_name', 'magic_schools', ['guild_id', sa.literal_column('lower(name)')],
                    unique=True)

    op.create_table('abilities',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('creator_uid', sa.BigInteger(), nullable=True),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('flavor', sa.Text(), nullable=True),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('school_id', sa.BigInteger(), nullable=True),
    sa.Column('stat', sa.String(length=16), nullable=False),
    sa.Column('tier', sa.String(length=16), nullable=False),
    sa.Column('effect', sa.String(length=16), nullable=False),
    sa.Column('damage_type', sa.String(length=50), nullable=True),
    sa.Column('condition', sa.String(length=16), nullable=True),
    sa.Column('area', sa.Boolean(), nullable=False),
    sa.Column('secondary', sa.String(length=16), nullable=True),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('review_message_id', sa.BigInteger(), nullable=True),
    sa.Column('forum_thread_id', sa.BigInteger(), nullable=True),
    sa.Column('forum_message_id', sa.BigInteger(), nullable=True),
    sa.Column('tag_ids', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['school_id'], ['magic_schools.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_abilities_guild_id'), 'abilities', ['guild_id'], unique=False)
    op.create_index('uq_ability_guild_name', 'abilities', ['guild_id', sa.literal_column('lower(name)')], unique=True)

    op.create_table('character_abilities',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('character_id', sa.BigInteger(), nullable=False),
    sa.Column('ability_id', sa.BigInteger(), nullable=False),
    sa.Column('event', sa.Boolean(), nullable=False),
    sa.Column('granted_by', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['ability_id'], ['abilities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('character_id', 'ability_id', name='uq_character_ability')
    )
    op.create_index(op.f('ix_character_abilities_character_id'), 'character_abilities', ['character_id'],
                    unique=False)

    op.add_column('characters', sa.Column('legendary', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('characters', sa.Column('legendary_points', sa.Integer(), server_default='0', nullable=False))
    op.add_column('characters', sa.Column('legendary_by', sa.BigInteger(), nullable=True))
    op.add_column('characters', sa.Column('legendary_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('characters', sa.Column('armor_proficiency', sa.String(length=16), nullable=True))
    op.add_column('character_gear', sa.Column('proficiency', sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column('character_gear', 'proficiency')
    op.drop_column('characters', 'armor_proficiency')
    op.drop_column('characters', 'legendary_at')
    op.drop_column('characters', 'legendary_by')
    op.drop_column('characters', 'legendary_points')
    op.drop_column('characters', 'legendary')

    op.drop_index(op.f('ix_character_abilities_character_id'), table_name='character_abilities')
    op.drop_table('character_abilities')
    op.drop_index('uq_ability_guild_name', table_name='abilities')
    op.drop_index(op.f('ix_abilities_guild_id'), table_name='abilities')
    op.drop_table('abilities')
    op.drop_index('uq_magic_school_guild_name', table_name='magic_schools')
    op.drop_index(op.f('ix_magic_schools_guild_id'), table_name='magic_schools')
    op.drop_table('magic_schools')
    op.drop_index('uq_damage_type_guild_name', table_name='damage_types')
    op.drop_index(op.f('ix_damage_types_guild_id'), table_name='damage_types')
    op.drop_table('damage_types')
    op.drop_index(op.f('ix_combat_log_instance_id'), table_name='combat_log')
    op.drop_table('combat_log')
    op.drop_index(op.f('ix_combat_entities_instance_id'), table_name='combat_entities')
    op.drop_index(op.f('ix_combat_entities_character_id'), table_name='combat_entities')
    op.drop_table('combat_entities')
    op.drop_index('uq_bestiary_guild_name', table_name='bestiary')
    op.drop_index(op.f('ix_bestiary_guild_id'), table_name='bestiary')
    op.drop_table('bestiary')
    op.drop_index(op.f('ix_combat_sides_instance_id'), table_name='combat_sides')
    op.drop_table('combat_sides')
    op.drop_index(op.f('ix_combat_instances_thread_id'), table_name='combat_instances')
    op.drop_index(op.f('ix_combat_instances_guild_id'), table_name='combat_instances')
    op.drop_table('combat_instances')

    # The old combat tables come back empty.
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
    sa.CheckConstraint('(character_id IS NOT NULL AND monster_id IS NULL AND npc_id IS NULL) OR '
                       '(character_id IS NULL AND monster_id IS NOT NULL AND npc_id IS NULL) OR '
                       '(character_id IS NULL AND monster_id IS NULL AND npc_id IS NOT NULL)',
                       name='chk_single_entity_source'),
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
