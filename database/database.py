"""Database connection and every table the bot uses.

The connection is built from the DB_* environment variables (see .env.example). When TEST is "true" every process
gets its own throwaway database named dawnbot_<8 hex>_test, so parallel test runs never share tables; the test
runner drops it again when it finishes.
"""
import logging
import os
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, \
	Text, URL, UniqueConstraint, create_engine, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
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


# Channel lists live in config.
class Channels(Timestamps, Base) :
	"""Unused; kept so a future autogenerate does not drop the live table."""
	__tablename__ = "channels"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guildid: Mapped[int] = mapped_column(BigInteger)
	channelid: Mapped[int] = mapped_column(BigInteger)


# ============================================================
# Characters and combat
# ============================================================

# Discord's attachment links expire, so the message is what is stored; url and expires_at only cache the last link.
class StoredImages(Base) :
	"""An image kept as a message in the storage channel (STORAGE_CHANNEL), such as an avatar."""
	__tablename__ = "stored_images"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	storage_channel_id: Mapped[int] = mapped_column(BigInteger)
	storage_message_id: Mapped[int] = mapped_column(BigInteger)
	url: Mapped[str] = mapped_column(Text)
	expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# stat_limits holds {stat: [min, max]} for the stats it changes; stats it leaves out follow the server's limits.
# stat_modifiers holds {stat: change to the starting value}. tag_ids are the tags on its post in the species forum, kept
# in step by the ProxyListener, and decide who may pick it (see tag_requirements). Edits to an approved species wait in
# pending_changes until staff approve them.
class Species(Timestamps, Base) :
	"""A species characters can be: made by a player and reviewed by staff, or the default Human."""
	__tablename__ = "species"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	creator_uid: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	name: Mapped[str] = mapped_column(String(100))
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	benefits: Mapped[str | None] = mapped_column(Text, nullable=True)
	drawbacks: Mapped[str | None] = mapped_column(Text, nullable=True)
	state: Mapped[str] = mapped_column(String(16), default="pending")
	stat_limits: Mapped[dict] = mapped_column(JSON, default=dict)
	stat_modifiers: Mapped[dict] = mapped_column(JSON, default=dict)
	tag_ids: Mapped[list] = mapped_column(JSON, default=list)
	forum_thread_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	forum_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	review_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	pending_changes: Mapped[dict | None] = mapped_column(JSON, nullable=True)

	__table_args__ = (
		Index('uq_species_guild_name', 'guild_id', text('lower(name)'), unique=True),
	)


# max_holders is how many characters can hold it at once (empty means no limit). min_level is a server level (the number
# of level roles a member has reached), role_id a role the member needs; staff_only ones are only given out by staff.
class Occupations(Base) :
	"""A role or occupation characters can hold, set by staff."""
	__tablename__ = "occupations"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	name: Mapped[str] = mapped_column(String(100))
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	max_holders: Mapped[int | None] = mapped_column(Integer, nullable=True)
	min_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
	role_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	staff_only: Mapped[bool] = mapped_column(Boolean, default=False)
	position: Mapped[int] = mapped_column(Integer, default=1)

	__table_args__ = (
		Index('uq_occupation_guild_name', 'guild_id', text('lower(name)'), unique=True),
	)


# kind is role (value: role id), level (value: server level), staff_only (only staff may give it out) or event (hidden;
# only given out by staff).
class TagRequirements(Base) :
	"""What a tag on a forum post asks of a member before they may pick what the post is about."""
	__tablename__ = "tag_requirements"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	forum_channel_id: Mapped[int] = mapped_column(BigInteger)
	tag_id: Mapped[int] = mapped_column(BigInteger)
	kind: Mapped[str] = mapped_column(String(16))
	value: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

	__table_args__ = (
		UniqueConstraint('tag_id', 'kind', name='uq_tag_requirement_tag_kind'),
	)


# state is the review state (pending, approved, denied, retired); the status column from Timestamps is unrelated.
# Changes to an approved character that need a new review wait in pending_changes until staff approve them.
class Characters(Timestamps, Base) :
	"""A player's character on one server."""
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
	species_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("species.id", ondelete="SET NULL"),
	                                               nullable=True)
	occupation_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("occupations.id", ondelete="SET NULL"),
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
	# The character this one was copied from on another server; a plain id, since the original can be deleted.
	imported_from: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	# A global character's sheet can also be viewed on the small servers (fewer than 10 members) its player is in.
	is_global: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
	# Legendary characters have doubled stat limits; legendary_points is what the status gave, taken back on removal.
	# Failed rolls in a row; at 3 the next failed roll is made again (see classes/combat/Fortune.py).
	bad_streak: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
	legendary: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
	legendary_points: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
	legendary_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	legendary_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	# clothing, light, medium or heavy; empty means it is read from the sheet (see Loadout).
	armor_proficiency: Mapped[str | None] = mapped_column(String(16), nullable=True)

	__table_args__ = (
		Index('uq_character_uid_guild_name', 'uid', 'guild_id', text('lower(name)'), unique=True),
	)


# type is short, long, number, choice or info. An info field asks nothing: its help text is shown as a note.
class SheetFields(Timestamps, Base) :
	"""One question on a server's character sheet, asked in the order of position."""
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


# sheet_field_id links an answer to the server's sheet question; it is empty for fields the player added.
class CharacterInfo(Timestamps, Base) :
	"""A field on a character sheet, shown in the order of position."""
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


# length, counted, xp_awarded and currency_awarded are only set on a post's first message. counted means the post was
# made in a roleplay channel, so it earns XP; recalculating XP uses the length of every counted post that was not
# deleted.
class ProxyMessages(Base) :
	"""A message the bot posted as a character. A long post's messages share first_message_id."""
	__tablename__ = "proxy_messages"
	message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
	first_message_id: Mapped[int] = mapped_column(BigInteger, index=True)
	character_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="SET NULL"),
	                                                 nullable=True, index=True)
	uid: Mapped[int] = mapped_column(BigInteger, index=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	# Where the message is: the thread when it was posted in one, otherwise the channel.
	channel_id: Mapped[int] = mapped_column(BigInteger)
	length: Mapped[int] = mapped_column(Integer, default=0)
	counted: Mapped[bool] = mapped_column(Boolean, default=False)
	xp_awarded: Mapped[int] = mapped_column(BigInteger, default=0)
	currency_awarded: Mapped[int] = mapped_column(BigInteger, default=0)
	deleted: Mapped[bool] = mapped_column(Boolean, default=False)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Autoproxy(Base) :
	"""A channel (or thread) where everything a member types is posted as one of their characters."""
	__tablename__ = "autoproxy"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	uid: Mapped[int] = mapped_column(BigInteger)
	guild_id: Mapped[int] = mapped_column(BigInteger)
	channel_id: Mapped[int] = mapped_column(BigInteger)
	character_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"))

	__table_args__ = (
		UniqueConstraint('uid', 'channel_id', name='uq_autoproxy_uid_channel'),
	)


# requirements holds {stat: lowest value} a character needs to use it well. effect_met and effect_unmet describe what
# happens when a character does or does not meet them, effect what the item always does. combat holds the numbers combat
# will use (weapons: dice, modifier, hitmodifier; armor: hp, ap, ac, hitchance). tag_ids are the tags on its post in the
# gear forum, kept in step from thread updates; they decide who may buy it.
class GearItems(Timestamps, Base) :
	"""A weapon or armor set in a server's catalog."""
	__tablename__ = "gear_items"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	# weapon or armor
	kind: Mapped[str] = mapped_column(String(16))
	name: Mapped[str] = mapped_column(String(100))
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	price: Mapped[int] = mapped_column(BigInteger, default=0)
	requirements: Mapped[dict] = mapped_column(JSON, default=dict)
	effect_met: Mapped[str | None] = mapped_column(Text, nullable=True)
	effect_unmet: Mapped[str | None] = mapped_column(Text, nullable=True)
	effect: Mapped[str | None] = mapped_column(Text, nullable=True)
	combat: Mapped[dict] = mapped_column(JSON, default=dict)
	tag_ids: Mapped[list] = mapped_column(JSON, default=list)
	forum_thread_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	forum_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	# The genre pack the item was imported from, if any.
	pack: Mapped[str | None] = mapped_column(String(50), nullable=True)

	__table_args__ = (
		Index('uq_gear_item_guild_name', 'guild_id', text('lower(name)'), unique=True),
	)


# name and kind are copied from the catalog, so the item keeps its name if the catalog entry is removed.
class CharacterGear(Base) :
	"""A piece of gear a character owns, or owned: lost, broken and sold items stay as history."""
	__tablename__ = "character_gear"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	character_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"), index=True)
	gear_item_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("gear_items.id", ondelete="SET NULL"),
	                                                 nullable=True)
	name: Mapped[str] = mapped_column(String(100))
	kind: Mapped[str] = mapped_column(String(16))
	equipped: Mapped[bool] = mapped_column(Boolean, default=False)
	# owned, lost, broken or sold
	status: Mapped[str] = mapped_column(String(16), default="owned")
	# creation, shop or granted
	source: Mapped[str] = mapped_column(String(16))
	price_paid: Mapped[int] = mapped_column(BigInteger, default=0)
	changed_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	# excellent, good, average, poor or awful; empty counts as awful (weapons only).
	proficiency: Mapped[str | None] = mapped_column(String(16), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
	updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
	                                             onupdate=func.now())


class CurrencyTransactions(Base) :
	"""Every change to a character's currency, for disputes and audits."""
	__tablename__ = "currency_transactions"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	character_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"), index=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	amount: Mapped[int] = mapped_column(BigInteger)
	# start, roleplay, buy, sell, gm_give or gm_take
	reason: Mapped[str] = mapped_column(String(16))
	actor_uid: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	note: Mapped[str | None] = mapped_column(Text, nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Drafts(Base) :
	"""The saved state of a DM interview, so it survives restarts. A user has at most one."""
	__tablename__ = "drafts"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	uid: Mapped[int] = mapped_column(BigInteger, unique=True)
	guild_id: Mapped[int] = mapped_column(BigInteger)
	# create, edit or respec for characters; species or species_edit for species
	kind: Mapped[str] = mapped_column(String(16))
	# The character being edited; empty while creating.
	target_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"),
	                                              nullable=True)
	# The species being edited.
	species_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("species.id", ondelete="CASCADE"),
	                                               nullable=True)
	step: Mapped[str] = mapped_column(String(64))
	answers: Mapped[dict] = mapped_column(JSON, default=dict)
	rolled_values: Mapped[list | None] = mapped_column(JSON, nullable=True)
	rerolls: Mapped[int] = mapped_column(Integer, default=0)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
	updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
	                                             onupdate=func.now())


# ============================================================
# Combat
# ============================================================

# state is pending (a PvP challenge nobody accepted yet), setup, active, paused or ended. order holds the side ids (async
# pacing) or combatant ids (live pacing) in the order they act this round, and turn_index points into it. deadline is
# when the current phase or turn runs out; while paused, paused_seconds holds the time that was left. invites holds
# {side id: [user ids]} for PvP sides, pending the "Other" actions waiting for the GM, challenge the PvP challenge.
class CombatInstances(Base) :
	"""One fight, bound to the thread it runs in."""
	__tablename__ = "combat_instances"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guid: Mapped[str] = mapped_column(String(64), default=lambda : uuid.uuid4().hex)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	thread_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
	board_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	gm_uid: Mapped[int] = mapped_column(BigInteger)
	co_gms: Mapped[list] = mapped_column(JSON, default=list)
	kind: Mapped[str] = mapped_column(String(8), default="pve")
	state: Mapped[str] = mapped_column(String(16), default="setup")
	pacing: Mapped[str] = mapped_column(String(8), default="async")
	lethal: Mapped[bool] = mapped_column(Boolean, default=False)
	round: Mapped[int] = mapped_column(Integer, default=0)
	order: Mapped[list] = mapped_column(JSON, default=list)
	turn_index: Mapped[int] = mapped_column(Integer, default=0)
	deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	paused_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
	title: Mapped[str] = mapped_column(String(100), default="Combat")
	winner_side_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	late_join: Mapped[bool] = mapped_column(Boolean, default=False)
	invites: Mapped[dict] = mapped_column(JSON, default=dict)
	pending: Mapped[list] = mapped_column(JSON, default=list)
	challenge: Mapped[dict | None] = mapped_column(JSON, nullable=True)
	idle_pinged: Mapped[list] = mapped_column(JSON, default=list)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
	updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
	                                             onupdate=func.now())
	ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CombatSides(Base) :
	"""A side in a fight, such as the party or the enemies."""
	__tablename__ = "combat_sides"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	instance_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("combat_instances.id", ondelete="CASCADE"),
	                                         index=True)
	name: Mapped[str] = mapped_column(String(50))
	position: Mapped[int] = mapped_column(Integer, default=1)


# stats is the snapshot taken when the combatant joined: SPECIAL, level, weapons, armor and abilities (see Loadout).
# controller is player, gm or auto; behavior is the NPC behavior or the player's autopilot. state is active, downed,
# stable, dying, fled, dead or removed. weapon_key is the weapon it holds, so switching can cost AP.
class CombatEntities(Base) :
	"""A character or NPC taking part in a fight."""
	__tablename__ = "combat_entities"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	instance_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("combat_instances.id", ondelete="CASCADE"),
	                                         index=True)
	side_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("combat_sides.id", ondelete="CASCADE"))
	kind: Mapped[str] = mapped_column(String(16))
	character_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="SET NULL"),
	                                                 nullable=True, index=True)
	uid: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	bestiary_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("bestiary.id", ondelete="SET NULL"),
	                                                nullable=True)
	name: Mapped[str] = mapped_column(String(100))
	controller: Mapped[str] = mapped_column(String(8), default="player")
	behavior: Mapped[str] = mapped_column(String(16), default="weakest")
	stats: Mapped[dict] = mapped_column(JSON, default=dict)
	hp: Mapped[int] = mapped_column(Integer, default=0)
	hp_max: Mapped[int] = mapped_column(Integer, default=0)
	ap: Mapped[int] = mapped_column(Integer, default=0)
	ap_max: Mapped[int] = mapped_column(Integer, default=0)
	ac: Mapped[int] = mapped_column(Integer, default=10)
	dt: Mapped[int] = mapped_column(Integer, default=0)
	sequence: Mapped[int] = mapped_column(Integer, default=0)
	conditions: Mapped[list] = mapped_column(JSON, default=list)
	ability_uses: Mapped[dict] = mapped_column(JSON, default=dict)
	acted: Mapped[bool] = mapped_column(Boolean, default=False)
	idle_turns: Mapped[int] = mapped_column(Integer, default=0)
	state: Mapped[str] = mapped_column(String(16), default="active")
	death_successes: Mapped[int] = mapped_column(Integer, default=0)
	death_failures: Mapped[int] = mapped_column(Integer, default=0)
	last_attacker_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	weapon_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
	position: Mapped[int] = mapped_column(Integer, default=0)
	lethal_ok: Mapped[bool] = mapped_column(Boolean, default=False)


# snapshot holds the fight as it was before the action, so the GM can undo it.
class CombatLog(Base) :
	"""One thing that happened in a fight."""
	__tablename__ = "combat_log"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	instance_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("combat_instances.id", ondelete="CASCADE"),
	                                         index=True)
	round: Mapped[int] = mapped_column(Integer, default=0)
	actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	target_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	action: Mapped[str] = mapped_column(String(32))
	text: Mapped[str] = mapped_column(Text, default="")
	details: Mapped[dict] = mapped_column(JSON, default=dict)
	snapshot: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# preset is minion, standard, elite, boss or custom. damage is the dice of its attack, damage_type a damage type's name.
class Bestiary(Base) :
	"""An NPC or monster a server's GMs can add to fights."""
	__tablename__ = "bestiary"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	name: Mapped[str] = mapped_column(String(100))
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
	preset: Mapped[str] = mapped_column(String(16), default="standard")
	hp: Mapped[int] = mapped_column(Integer, default=20)
	ac: Mapped[int] = mapped_column(Integer, default=12)
	dt: Mapped[int] = mapped_column(Integer, default=1)
	to_hit: Mapped[int] = mapped_column(Integer, default=2)
	damage: Mapped[str] = mapped_column(String(16), default="2d6")
	damage_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
	attack_name: Mapped[str] = mapped_column(String(50), default="Attack")
	ap: Mapped[int] = mapped_column(Integer, default=7)
	sequence: Mapped[int] = mapped_column(Integer, default=10)
	behavior: Mapped[str] = mapped_column(String(16), default="aggressive")
	ability_ids: Mapped[list] = mapped_column(JSON, default=list)
	reward_xp: Mapped[int] = mapped_column(Integer, default=0)
	reward_currency: Mapped[int] = mapped_column(Integer, default=0)
	# When special is set ({stat: value}), HP, AC, AP and Sequence are derived like a character's, at this level,
	# and it fights with the catalog weapons and armor below instead of its own attack.
	special: Mapped[dict | None] = mapped_column(JSON, nullable=True)
	level: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
	weapon_ids: Mapped[list] = mapped_column(JSON, default=list)
	armor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("gear_items.id", ondelete="SET NULL"),
	                                             nullable=True)
	creator_uid: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

	__table_args__ = (
		Index('uq_bestiary_guild_name', 'guild_id', text('lower(name)'), unique=True),
	)


# trigger is strong_hit or always. effect is {"kind": "condition", "condition": "bleeding", "turns": 2},
# {"kind": "ignore_dt"}, {"kind": "arc"}, {"kind": "cleanse"} or {"kind": "none"}.
class DamageTypes(Base) :
	"""A damage type a server's weapons, spells and abilities can have, with the effect a strong hit adds."""
	__tablename__ = "damage_types"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	name: Mapped[str] = mapped_column(String(50))
	trigger: Mapped[str] = mapped_column(String(16), default="strong_hit")
	effect: Mapped[dict] = mapped_column(JSON, default=dict)
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	pack: Mapped[str | None] = mapped_column(String(50), nullable=True)

	__table_args__ = (
		Index('uq_damage_type_guild_name', 'guild_id', text('lower(name)'), unique=True),
	)


class MagicSchools(Base) :
	"""A school of magic; standard ones come with the server, players can propose their own."""
	__tablename__ = "magic_schools"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	name: Mapped[str] = mapped_column(String(50))
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	casting_stat: Mapped[str] = mapped_column(String(16), default="intelligence")
	creator_uid: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	state: Mapped[str] = mapped_column(String(16), default="pending")
	standard: Mapped[bool] = mapped_column(Boolean, default=False)
	review_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

	__table_args__ = (
		Index('uq_magic_school_guild_name', 'guild_id', text('lower(name)'), unique=True),
	)


# kind is spell or ability; tier cantrip, weak, normal or strong; effect damage, heal, condition, shield or boost.
# condition is the condition a condition or boost ability applies, secondary the one a damage ability adds on a hit.
class Abilities(Base) :
	"""A spell or ability a player built, reviewed by staff."""
	__tablename__ = "abilities"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	creator_uid: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	name: Mapped[str] = mapped_column(String(100))
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	flavor: Mapped[str | None] = mapped_column(Text, nullable=True)
	kind: Mapped[str] = mapped_column(String(16), default="ability")
	school_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("magic_schools.id", ondelete="SET NULL"),
	                                              nullable=True)
	stat: Mapped[str] = mapped_column(String(16), default="intelligence")
	tier: Mapped[str] = mapped_column(String(16), default="weak")
	effect: Mapped[str] = mapped_column(String(16), default="damage")
	damage_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
	condition: Mapped[str | None] = mapped_column(String(16), nullable=True)
	area: Mapped[bool] = mapped_column(Boolean, default=False)
	secondary: Mapped[str | None] = mapped_column(String(16), nullable=True)
	# active (used on a turn) or passive (always on; its parts are in passive, see classes/combat/Passives.py).
	activation: Mapped[str] = mapped_column(String(16), default="active", server_default="active")
	passive: Mapped[dict | None] = mapped_column(JSON, nullable=True)
	state: Mapped[str] = mapped_column(String(16), default="pending")
	review_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	forum_thread_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	forum_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	tag_ids: Mapped[list] = mapped_column(JSON, default=list)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

	__table_args__ = (
		Index('uq_ability_guild_name', 'guild_id', text('lower(name)'), unique=True),
	)


# event abilities were granted by a GM: they skip the slot limits.
class CharacterAbilities(Base) :
	"""An ability a character knows."""
	__tablename__ = "character_abilities"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	character_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"), index=True)
	ability_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("abilities.id", ondelete="CASCADE"))
	event: Mapped[bool] = mapped_column(Boolean, default=False)
	granted_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

	__table_args__ = (
		UniqueConstraint('character_id', 'ability_id', name='uq_character_ability'),
	)


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


# The category is also written at the start of the channel's name, so the origin stays visible (and restorable) even
# without this row.
class ArchivedChannels(Base) :
	"""Where an archived channel came from, so /archive restore can put it back exactly."""
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
