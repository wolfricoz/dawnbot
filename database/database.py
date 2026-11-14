"""Database connection and every table the bot uses.

The connection is built from the DB_* environment variables (see .env.example). When TEST is "true" every process
gets its own throwaway database named dawnbot_<8 hex>_test, so parallel test runs never share tables; the test
runner drops it again when it finishes.
"""
import logging
import os
import uuid
from datetime import datetime
from typing import List

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, \
	Text, URL, UniqueConstraint, create_engine, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.pool import NullPool
from sqlalchemy_utils import create_database, database_exists

from data.env.loader import env, load_environment

load_environment()

TEST_MODE = str(env('TEST', '')).lower() == "true"
database_name = env('DB_NAME', 'dawnbot')
if TEST_MODE :
	# Every test run gets its own database, so parallel runs never collide.
	os.environ.setdefault('TEST_DB_NAME', f"dawnbot_{uuid.uuid4().hex[:8]}_test")
	database_name = os.environ['TEST_DB_NAME']

# URL.create escapes special characters in the password, which an f-string URL would not.
db_url = URL.create(
	drivername=env('DB_TYPE', 'postgresql+psycopg2'),
	username=env('DB_USER'),
	password=env('DB_PASSWORD'),
	host=env('DB_HOST', '127.0.0.1'),
	port=int(env('DB_PORT', 5432)),
	database=database_name,
)

if TEST_MODE :
	# Opening a fresh connection per session is the slowest part of a test; a small pool keeps the suite fast.
	engine = create_engine(db_url, pool_size=5, max_overflow=5, pool_pre_ping=True)
else :
	engine = create_engine(db_url, poolclass=NullPool, pool_pre_ping=True)

if not database_exists(engine.url) :
	create_database(engine.url)


class Base(DeclarativeBase) :
	pass


class Timestamps :
	"""Adds the created_at and updated_at columns to the session."""
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
	updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
	status: Mapped[int] = mapped_column(Integer, default=1)


# ============================================================
# Shared tables (same shape as the other bots)
# ============================================================

class Servers(Base) :
	__tablename__ = "servers"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
	owner: Mapped[str] = mapped_column(String(1024))
	name: Mapped[str] = mapped_column(String(1024))
	member_count: Mapped[int] = mapped_column(BigInteger)
	hidden: Mapped[bool] = mapped_column(Boolean, default=False)
	invite: Mapped[str] = mapped_column(String(256), default="")
	updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
	deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=None, nullable=True)
	active: Mapped[bool] = mapped_column(Boolean, default=True)
	premium: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
	owner_id: Mapped[int] = mapped_column(BigInteger, nullable=True)

	def __int__(self) :
		return self.id


class Config(Base) :
	__tablename__ = "config"
	id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
	guild: Mapped[int] = mapped_column(BigInteger, ForeignKey("servers.id", ondelete="CASCADE"))
	key: Mapped[str] = mapped_column(String(512))
	value: Mapped[str] = mapped_column(String(1980))


class Staff(Base) :
	__tablename__ = "staff"
	id: Mapped[int] = mapped_column(primary_key=True)
	uid: Mapped[int] = mapped_column(BigInteger)
	role: Mapped[str] = mapped_column(String(128))

	def __int__(self) :
		return self.id


# ============================================================
# Progression
# ============================================================

class Users(Timestamps, Base) :
	__tablename__ = "users"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

	# Core unique reference point. A user only ever has ONE row here globally.
	uid: Mapped[int] = mapped_column(BigInteger, unique=True)


class Experience(Timestamps, Base) :
	__tablename__ = "experience"

	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

	# Linked to the global users table
	uid: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.uid', ondelete="CASCADE"))

	messages: Mapped[int] = mapped_column(BigInteger, default=0)
	xp: Mapped[int] = mapped_column(BigInteger, default=0)
	currency: Mapped[int] = mapped_column(BigInteger, default=0)
	guildid: Mapped[int] = mapped_column(BigInteger)

	# Allows the same UID to exist across multiple guilds, but only once per guild.
	__table_args__ = (
		UniqueConstraint('uid', 'guildid', name='uq_experience_uid_guildid'),
	)


class Levels(Timestamps, Base) :
	__tablename__ = "levels"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guildid: Mapped[int] = mapped_column(BigInteger)
	role_id: Mapped[int] = mapped_column(BigInteger)
	xp_required: Mapped[int] = mapped_column(BigInteger)


class Channels(Timestamps, Base) :
	"""Unused; kept so the live table is not dropped by a future autogenerate. Channel lists live in config."""
	__tablename__ = "channels"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guildid: Mapped[int] = mapped_column(BigInteger)
	channelid: Mapped[int] = mapped_column(BigInteger)


# ============================================================
# Characters and combat
# ============================================================

class StoredImages(Base) :
	"""An image kept as a message in the storage channel (STORAGE_CHANNEL), such as a character's avatar.

	Discord's attachment links expire, so the message is what is stored; url and expires_at only cache the last link.
	"""
	__tablename__ = "stored_images"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	storage_channel_id: Mapped[int] = mapped_column(BigInteger)
	storage_message_id: Mapped[int] = mapped_column(BigInteger)
	url: Mapped[str] = mapped_column(Text)
	expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Characters(Timestamps, Base) :
	"""A player's character on one server.

	state is the review state (pending, approved, denied, retired); the status column from Timestamps is unrelated.
	Changes to an approved character that need a new review wait in pending_changes until staff approve them.
	"""
	__tablename__ = "characters"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

	# Linked to the global users table
	uid: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.uid', ondelete="CASCADE"))

	guild_id: Mapped[int] = mapped_column(BigInteger)
	# Kept as the player wrote it; names are compared without case.
	name: Mapped[str] = mapped_column(String(255))
	state: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
	prefix: Mapped[str | None] = mapped_column(String(255), nullable=True)
	suffix: Mapped[str | None] = mapped_column(String(255), nullable=True)
	avatar_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("stored_images.id", ondelete="SET NULL"),
	                                              nullable=True)

	strength: Mapped[int] = mapped_column(BigInteger, default=0)
	perception: Mapped[int] = mapped_column(BigInteger, default=0)
	endurance: Mapped[int] = mapped_column(BigInteger, default=0)
	charisma: Mapped[int] = mapped_column(BigInteger, default=0)
	intelligence: Mapped[int] = mapped_column(BigInteger, default=0)
	agility: Mapped[int] = mapped_column(BigInteger, default=0)
	luck: Mapped[int] = mapped_column(BigInteger, default=0)
	# point_buy or rolled, shown to reviewers together with the number of rerolls.
	stat_method: Mapped[str | None] = mapped_column(String(16), nullable=True)
	rerolls: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
	unspent_points: Mapped[int] = mapped_column(BigInteger, default=0)

	xp: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
	level: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
	currency: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")

	# The character's post: the forum thread (when CHARACTER is a forum) and the ids of the messages in it.
	forum_thread_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	forum_message_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
	review_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	pending_changes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
	approved_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

	__table_args__ = (
		Index('uq_character_uid_guild_name', 'uid', 'guild_id', text('lower(name)'), unique=True),
	)


class SheetFields(Timestamps, Base) :
	"""One question on a server's character sheet, asked in the order of position.

	type is short, long, number, choice or info. An info field asks nothing: its help text is shown as a note.
	"""
	__tablename__ = "sheet_fields"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	position: Mapped[int] = mapped_column(Integer, default=1)
	section: Mapped[str | None] = mapped_column(String(100), nullable=True)
	label: Mapped[str] = mapped_column(String(100))
	help: Mapped[str | None] = mapped_column(Text, nullable=True)
	type: Mapped[str] = mapped_column(String(16), default="short")
	required: Mapped[bool] = mapped_column(Boolean, default=False)
	max_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
	min_value: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	max_value: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	choices: Mapped[list | None] = mapped_column(JSON, nullable=True)


class CharacterInfo(Timestamps, Base) :
	"""A field on a character sheet, shown in the order of position.

	sheet_field_id links an answer to the server's sheet question; it is empty for fields the player added.
	"""
	__tablename__ = "character_info"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	character_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"))
	sheet_field_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sheet_fields.id", ondelete="SET NULL"),
	                                                   nullable=True)
	key: Mapped[str] = mapped_column(String(255))
	value: Mapped[str] = mapped_column(Text)
	position: Mapped[int] = mapped_column(Integer, default=1)

	__table_args__ = (
		UniqueConstraint('character_id', 'key', name='uq_character_info_character_key'),
	)


class Drafts(Base) :
	"""The saved state of a DM interview, so it survives restarts. A user has at most one."""
	__tablename__ = "drafts"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	uid: Mapped[int] = mapped_column(BigInteger, unique=True)
	guild_id: Mapped[int] = mapped_column(BigInteger)
	# create, edit or respec
	kind: Mapped[str] = mapped_column(String(16))
	# The character being edited; empty while creating.
	target_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"),
	                                              nullable=True)
	step: Mapped[str] = mapped_column(String(64))
	answers: Mapped[dict] = mapped_column(JSON, default=dict)
	rolled_values: Mapped[list | None] = mapped_column(JSON, nullable=True)
	rerolls: Mapped[int] = mapped_column(Integer, default=0)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
	updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
	                                             onupdate=func.now())


class Armors(Timestamps, Base) :
	__tablename__ = "armors"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	name: Mapped[str] = mapped_column(String(255))
	hp: Mapped[int] = mapped_column(BigInteger, default=75)
	ap: Mapped[int] = mapped_column(BigInteger, default=25)
	ac: Mapped[int] = mapped_column(BigInteger, default=12)
	hitchance: Mapped[int] = mapped_column(BigInteger, default=0)
	modifier: Mapped[str] = mapped_column(String(255), nullable=True)


class Weapons(Timestamps, Base) :
	__tablename__ = "weapons"
	name: Mapped[str] = mapped_column(String(255), primary_key=True)
	dice: Mapped[str] = mapped_column(String(255))
	modifier: Mapped[str] = mapped_column(String(255))
	hitmodifier = mapped_column(BigInteger, default=0)


class EntityStats :
	hp: Mapped[int] = mapped_column(BigInteger)
	ac: Mapped[int] = mapped_column(BigInteger)
	attack: Mapped[str] = mapped_column(String(1024), default="1d20")
	damage: Mapped[str] = mapped_column(String(1024), default="1d12")


class Npcs(EntityStats, Timestamps, Base) :
	__tablename__ = "npcs"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	name: Mapped[str] = mapped_column(String(255))


class Monsters(EntityStats, Timestamps, Base) :
	__tablename__ = "monsters"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	name: Mapped[str] = mapped_column(String(255))


class CombatInstances(Timestamps, Base) :
	__tablename__ = "combat_instances"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guid: Mapped[str] = mapped_column(String(255), server_default=text("gen_random_uuid()"))
	channel_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
	description: Mapped[str] = mapped_column(Text, nullable=True)
	round: Mapped[int] = mapped_column(BigInteger, default=1)
	combat_type: Mapped[str] = mapped_column(String(255), nullable=True, default="encounter")
	active: Mapped[bool] = mapped_column(Boolean, default=True)
	entities: Mapped[List["CombatInstanceEntities"]] = relationship(
		"CombatInstanceEntities",
		back_populates="combat_instance",
		cascade="all, delete-orphan",
		lazy="joined"
	)


class CombatInstanceEntities(Timestamps, Base) :
	__tablename__ = "combat_instance_entities"

	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	instance_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("combat_instances.id", ondelete="CASCADE"),
	                                         nullable=False)

	# Linked to the global users table
	user_uid: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.uid", ondelete="CASCADE"), nullable=True)

	character_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"),
	                                                 nullable=True)
	monster_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("monsters.id", ondelete="CASCADE"),
	                                               nullable=True)
	npc_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("npcs.id", ondelete="CASCADE"), nullable=True)

	current_hp: Mapped[int] = mapped_column(BigInteger, default=0)
	current_ap: Mapped[int] = mapped_column(BigInteger, default=0)
	ac: Mapped[int] = mapped_column(BigInteger, default=0)

	entity_type: Mapped[str] = mapped_column(String(255), nullable=True)
	remaining_attacks: Mapped[int] = mapped_column(BigInteger, default=1)
	alive: Mapped[bool] = mapped_column(Boolean, default=True)
	stunned: Mapped[bool] = mapped_column(Boolean, default=False)

	combat_instance: Mapped["CombatInstances"] = relationship("CombatInstances", back_populates="entities")

	__table_args__ = (
		CheckConstraint(
			"""
			(character_id IS NOT NULL AND monster_id IS NULL AND npc_id IS NULL) OR
			(character_id IS NULL AND monster_id IS NOT NULL AND npc_id IS NULL) OR
			(character_id IS NULL AND monster_id IS NULL AND npc_id IS NOT NULL)
			""",
			name="chk_single_entity_source"
		),
	)


class CombatInstanceLogs(Timestamps, Base) :
	__tablename__ = "combat_instance_log"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	instance_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("combat_instances.id", ondelete="CASCADE"),
	                                         nullable=False)
	attacker_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("combat_instance_entities.id", ondelete="CASCADE"))
	defender_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("combat_instance_entities.id", ondelete="CASCADE"))
	damage: Mapped[int] = mapped_column(BigInteger, default=0)


# ============================================================
# Server setup
# ============================================================

class Templates(Timestamps, Base) :
	"""A snapshot of a server's categories and channels, owned by the user who registered it."""
	__tablename__ = "templates"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	uid: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.uid', ondelete="CASCADE"))
	name: Mapped[str] = mapped_column(String(255))
	# {"categories": [{"name": str, "channels": [{"name": str, "type": int}]}]}
	data: Mapped[dict] = mapped_column(JSON)

	__table_args__ = (
		UniqueConstraint('uid', 'name', name='uq_template_uid_name'),
	)


class ArchivedChannels(Base) :
	"""Where an archived channel came from, so /archive restore can put it back exactly.

	The category is also written at the start of the channel's name, so the origin stays visible (and restorable)
	even without this row.
	"""
	__tablename__ = "archived_channels"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	channel_id: Mapped[int] = mapped_column(BigInteger, unique=True)
	channel_name: Mapped[str] = mapped_column(String(100))
	category_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
	# The channel's own @everyone "View Channel" overwrite before archiving: True, False, or None (inherited).
	everyone_view: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
	archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# Helpers
# ============================================================

class database :
	@staticmethod
	def create() :
		Base.metadata.create_all(engine)
		logging.info("Database built")


def create_bot_database() :
	Base.metadata.create_all(engine)


def _guard_production() :
	if not TEST_MODE or env('TOKEN') is not None :
		raise Exception("Refusing to change the database outside of test mode or while a bot TOKEN is set.")


def drop_bot_database() :
	_guard_production()
	Base.metadata.drop_all(engine)


def clear_bot_database() :
	"""Empties every table; much faster than dropping and recreating them between tests."""
	_guard_production()
	tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
	with engine.begin() as connection :
		connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
