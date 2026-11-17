"""Database connection and every table the bot uses.

The connection is built from the DB_* environment variables (see .env.example). When TEST is "true" every process
gets its own throwaway database named dawnbot_<8 hex>_test, so parallel test runs never share tables; the test
runner drops it again when it finishes.
"""
import logging
import os
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, \
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
	# /scene away: no scene nudges or skips for them until then.
	away_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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
	# Languages every character of the species speaks fluently.
	language_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)

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
	# Downtime work: what a day pays (empty is WORK_PAY), the stat it rolls, a roll table for a great day, and flavor
	# lines per outcome. seer occupations can read omens for others.
	pay: Mapped[int | None] = mapped_column(Integer, nullable=True)
	work_stat: Mapped[str | None] = mapped_column(String(16), nullable=True)
	table_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	flavor: Mapped[dict | None] = mapped_column(JSON, nullable=True)
	seer: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
	# A faction standing (a tier, see classes/economy/FactionFlow.py) a character needs to take the occupation.
	faction_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	faction_tier: Mapped[str | None] = mapped_column(String(16), nullable=True)
	# The kinds of gear its characters can repair: weapon, clothing, light, medium, heavy, accessory.
	repairs: Mapped[list | None] = mapped_column(JSON, nullable=True)

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
	# {"month", "day"} on the in-world calendar.
	birthday: Mapped[dict | None] = mapped_column(JSON, nullable=True)
	# /language speak: the language its posts are in unless they say otherwise (empty is the common language).
	speaking_language_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	# The last omen drawn: {"card", "deck", "effect" (boon, bane or none), "used", "drawn_at"}.
	omen: Mapped[dict | None] = mapped_column(JSON, nullable=True)

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
	"""A weapon, armor set, consumable or material in a server's catalog."""
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
	# A faction's item: its standing changes the price, and faction_tier (a standing tier) is needed to buy it.
	faction_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	faction_tier: Mapped[str | None] = mapped_column(String(16), nullable=True)
	# What salvaging it gives: {material name: amount}.
	salvage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
	# common, uncommon, rare, very_rare or legendary; empty takes it from the price (classes/gear/Rarity.py).
	rarity: Mapped[str | None] = mapped_column(String(16), nullable=True)
	# In kilograms; empty weighs nothing (classes/gear/Carry.py).
	weight: Mapped[float | None] = mapped_column(Float, nullable=True)
	# Where an accessory is worn: head, neck, back, hands, feet or ring (classes/gear/Slots.py).
	slot: Mapped[str | None] = mapped_column(String(16), nullable=True)
	# A magic item's enchantment (classes/gear/Magic.py): {"activation", "effects": [{"key"}], "charges", "recharge",
	# "bonus", "item_bonus", "damage_type"}; empty for a plain item.
	enchantments: Mapped[dict | None] = mapped_column(JSON, nullable=True)
	# What an unidentified copy is called ("a humming silver ring").
	unidentified_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
	# Only made by crafting (a player's approved enchanted design): never sold by a shop or merchant.
	crafted_only: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

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
	# owned, lost, sold or used (broken is a condition)
	status: Mapped[str] = mapped_column(String(16), default="owned")
	# creation, shop or granted
	source: Mapped[str] = mapped_column(String(16))
	price_paid: Mapped[int] = mapped_column(BigInteger, default=0)
	changed_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	# excellent, good, average, poor or awful; empty counts as awful (weapons only).
	proficiency: Mapped[str | None] = mapped_column(String(16), nullable=True)
	# How many: materials stack in one entry.
	quantity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
	# masterwork or cursed (crafted), or empty.
	quality: Mapped[str | None] = mapped_column(String(16), nullable=True)
	# Where it is equipped (main_hand, off_hand, readied, body, head, neck, back, hands, feet, ring_1, ring_2).
	slot: Mapped[str | None] = mapped_column(String(16), nullable=True)
	# good, worn, damaged or broken (classes/gear/Condition.py).
	condition: Mapped[str] = mapped_column(String(16), default="good", server_default="good")
	# A ranged weapon's ammunition die (d12 to d4, or empty when it ran out); unset is full.
	ammo_die: Mapped[str | None] = mapped_column(String(8), nullable=True)
	# The location whose stash holds it, while status is "stashed" (classes/economy/Merchants.py).
	stash_location_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	# Magic items (classes/gear/Magic.py): attuned items work; charges left today (for daily charges) and the day they
	# were counted; extra charges from a crafting crit; identified is False for loot that dropped unidentified.
	attuned: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
	charges_left: Mapped[int | None] = mapped_column(Integer, nullable=True)
	charges_day: Mapped[str | None] = mapped_column(String(10), nullable=True)
	extra_charges: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
	identified: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
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
	# What it drops (classes/economy/Loot.py): {"currency": "3d10", "items": [{"name", "chance", "amount"}]}.
	loot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
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


# kind is spell or ability; tier cantrip, weak, normal or strong. effects lists the catalog effects it is built from,
# [{"key": "pyrokinesis"}, ...] (passives can add "target" and "limit"; see classes/combat/Abilities.py). damage_type is
# the type for effects that take the ability's own. state is draft (made from an old free-text sheet answer, no effects
# yet), pending, approved or denied.
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
	effects: Mapped[list | None] = mapped_column(JSON, nullable=True)
	damage_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
	# active (used on a turn) or passive (always on, built from passive effects).
	activation: Mapped[str] = mapped_column(String(16), default="active", server_default="active")
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
# Checks and roll tables
# ============================================================

# kind is individual, group, opposed or passive; visibility public, hidden_dc or secret; state open or closed.
# allowed is {"role": id, "member": id} (empty means anyone). opposed holds the two sides of an opposed check between
# characters, {"1": {"uid", "character_id", "stat"}, "2": {...}}, or the NPC's roll, {"npc", "bonus", "natural",
# "total"}. helps lists {"helper_uid", "helper_character_id", "helper_name", "target_uid", "used"}.
class Checks(Base) :
	"""A check a member called; players press Roll on its card."""
	__tablename__ = "checks"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	channel_id: Mapped[int] = mapped_column(BigInteger)
	message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	caller_uid: Mapped[int] = mapped_column(BigInteger)
	title: Mapped[str | None] = mapped_column(String(200), nullable=True)
	stat: Mapped[str] = mapped_column(String(16))
	dc: Mapped[int | None] = mapped_column(Integer, nullable=True)
	kind: Mapped[str] = mapped_column(String(16), default="individual")
	visibility: Mapped[str] = mapped_column(String(16), default="public")
	modifier: Mapped[int] = mapped_column(Integer, default=0)
	allowed: Mapped[dict] = mapped_column(JSON, default=dict)
	opposed: Mapped[dict | None] = mapped_column(JSON, nullable=True)
	helps: Mapped[list] = mapped_column(JSON, default=list)
	state: Mapped[str] = mapped_column(String(16), default="open")
	expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# name is copied from the character, so the line survives the character being deleted. side is 1 or 2 in an opposed
# check between characters, otherwise 0.
class CheckRolls(Base) :
	"""One character's roll on a check."""
	__tablename__ = "check_rolls"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	check_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("checks.id", ondelete="CASCADE"), index=True)
	character_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="SET NULL"),
	                                                 nullable=True)
	uid: Mapped[int] = mapped_column(BigInteger)
	name: Mapped[str] = mapped_column(String(255))
	side: Mapped[int] = mapped_column(Integer, default=0)
	stat: Mapped[str] = mapped_column(String(16))
	natural: Mapped[int] = mapped_column(Integer)
	total: Mapped[int] = mapped_column(Integer)
	outcome: Mapped[str] = mapped_column(String(16))
	helped_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
	details: Mapped[dict] = mapped_column(JSON, default=dict)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

	__table_args__ = (
		UniqueConstraint('check_id', 'character_id', name='uq_check_roll_character'),
	)


# dice is "1dN" for a table rolled over ranges, or "weights" for one rolled by weight. kind is table or deck (omen
# decks, later); visibility everyone or staff.
class RollTables(Base) :
	"""A server's roll table: loot, encounters, names, plot hooks."""
	__tablename__ = "roll_tables"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	name: Mapped[str] = mapped_column(String(100))
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	dice: Mapped[str] = mapped_column(String(16), default="weights")
	luck: Mapped[bool] = mapped_column(Boolean, default=False)
	kind: Mapped[str] = mapped_column(String(16), default="table")
	visibility: Mapped[str] = mapped_column(String(16), default="everyone")
	pack: Mapped[str | None] = mapped_column(String(50), nullable=True)
	creator_uid: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

	__table_args__ = (
		Index('uq_roll_table_guild_name', 'guild_id', text('lower(name)'), unique=True),
	)


# low and high are the range of a table rolled over ranges; weight is used by tables rolled by weight. actions lists
# what the entry gives: {"kind": "item", "name"}, {"kind": "currency" or "xp", "amount": "2d6"} or
# {"kind": "npc", "name", "count": "1d4"}.
class RollTableEntries(Base) :
	"""One line of a roll table."""
	__tablename__ = "roll_table_entries"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	table_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("roll_tables.id", ondelete="CASCADE"), index=True)
	low: Mapped[int | None] = mapped_column(Integer, nullable=True)
	high: Mapped[int | None] = mapped_column(Integer, nullable=True)
	weight: Mapped[int] = mapped_column(Integer, default=1)
	text: Mapped[str] = mapped_column(Text)
	actions: Mapped[list] = mapped_column(JSON, default=list)
	position: Mapped[int] = mapped_column(Integer, default=0)


# actions are the entry's actions with their dice rolled ({"kind": "currency", "amount": 7}). granted_to lists the
# character ids a GM gave the rewards to.
class TableRolls(Base) :
	"""A roll on a table, kept so its Grant and Start fight buttons work later."""
	__tablename__ = "table_rolls"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	table_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("roll_tables.id", ondelete="SET NULL"),
	                                             nullable=True)
	table_name: Mapped[str] = mapped_column(String(100))
	uid: Mapped[int] = mapped_column(BigInteger)
	character_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="SET NULL"),
	                                                 nullable=True)
	channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	natural: Mapped[int] = mapped_column(Integer)
	rolled: Mapped[int] = mapped_column(Integer)
	text: Mapped[str] = mapped_column(Text)
	actions: Mapped[list] = mapped_column(JSON, default=list)
	granted_to: Mapped[list] = mapped_column(JSON, default=list)
	fight_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	secret: Mapped[bool] = mapped_column(Boolean, default=False)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# The world: calendar, weather, locations and travel
# ============================================================

# months is [{"name", "days", "season"}], weekdays a list of names. month and day count from 1; part is the time of day
# (0 dawn to 5 night). flow is manual or a ratio such as 2:1 (in-world days per real day), copied from TIME_FLOW when
# time moves; last_tick is when flowing time was last moved.
class Calendars(Base) :
	"""A server's in-world calendar and the current in-world date."""
	__tablename__ = "calendars"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, unique=True)
	preset: Mapped[str] = mapped_column(String(32), default="gregorian")
	months: Mapped[list] = mapped_column(JSON, default=list)
	weekdays: Mapped[list] = mapped_column(JSON, default=list)
	era: Mapped[str | None] = mapped_column(String(32), nullable=True)
	year: Mapped[int] = mapped_column(Integer, default=1)
	month: Mapped[int] = mapped_column(Integer, default=1)
	day: Mapped[int] = mapped_column(Integer, default=1)
	part: Mapped[int] = mapped_column(Integer, default=1)
	moon_cycle: Mapped[int | None] = mapped_column(Integer, nullable=True)
	last_tick: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# year empty means every year. last_year is the in-world year it was last announced, so it is announced once.
class CalendarEvents(Base) :
	"""A holiday or event on the in-world calendar, announced on its day."""
	__tablename__ = "calendar_events"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	name: Mapped[str] = mapped_column(String(100))
	month: Mapped[int] = mapped_column(Integer)
	day: Mapped[int] = mapped_column(Integer)
	year: Mapped[int | None] = mapped_column(Integer, nullable=True)
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	last_year: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Regions(Base) :
	"""A group of locations (a city, a forest) that shares a climate and its weather."""
	__tablename__ = "regions"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	name: Mapped[str] = mapped_column(String(100))
	climate: Mapped[str] = mapped_column(String(16), default="temperate")
	description: Mapped[str | None] = mapped_column(Text, nullable=True)

	__table_args__ = (
		Index('uq_region_guild_name', 'guild_id', text('lower(name)'), unique=True),
	)


# climate empty means the region's. table_id is the roll table for encounters on the way here.
class Locations(Base) :
	"""A place in the world, bound to one channel or thread."""
	__tablename__ = "locations"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	channel_id: Mapped[int] = mapped_column(BigInteger, unique=True)
	name: Mapped[str] = mapped_column(String(100))
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	image_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("stored_images.id", ondelete="SET NULL"),
	                                             nullable=True)
	region_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("regions.id", ondelete="SET NULL"),
	                                              nullable=True)
	climate: Mapped[str | None] = mapped_column(String(16), nullable=True)
	indoor: Mapped[bool] = mapped_column(Boolean, default=False)
	danger: Mapped[int] = mapped_column(Integer, default=0)
	hazards: Mapped[str | None] = mapped_column(Text, nullable=True)
	table_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("roll_tables.id", ondelete="SET NULL"),
	                                             nullable=True)
	tags: Mapped[list] = mapped_column(JSON, default=list)
	# The faction that holds the place: carousing here gains a little standing with it.
	faction_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


# hours is the in-world travel time.
class Routes(Base) :
	"""A road between two locations, with its travel time and danger."""
	__tablename__ = "routes"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	from_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("locations.id", ondelete="CASCADE"))
	to_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("locations.id", ondelete="CASCADE"))
	hours: Mapped[int] = mapped_column(Integer, default=0)
	danger: Mapped[int] = mapped_column(Integer, default=0)
	table_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("roll_tables.id", ondelete="SET NULL"),
	                                             nullable=True)
	two_way: Mapped[bool] = mapped_column(Boolean, default=True)


# region_id empty is the server's weather outside any region. world_day is the in-world day (an ordinal) it was rolled
# for, so flowing time rolls it once a day.
class WeatherStates(Base) :
	"""The current weather of a region."""
	__tablename__ = "weather_states"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	region_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("regions.id", ondelete="CASCADE"),
	                                              nullable=True)
	climate: Mapped[str] = mapped_column(String(16))
	weather: Mapped[str] = mapped_column(String(32))
	forced: Mapped[bool] = mapped_column(Boolean, default=False)
	world_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
	since: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# state is travelling or arrived.
class Travels(Base) :
	"""A character on the road, until it arrives."""
	__tablename__ = "travels"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	character_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"))
	from_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("locations.id", ondelete="SET NULL"),
	                                            nullable=True)
	to_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("locations.id", ondelete="CASCADE"))
	arrive_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
	state: Mapped[str] = mapped_column(String(16), default="travelling")
	encounter: Mapped[dict | None] = mapped_column(JSON, nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# Scenes and the chronicle
# ============================================================

# channel_id is where the scene runs: a channel, or a thread. mode is order or free; state open, paused or ended.
# paused_by_fight is the fight that paused it (it resumes when that fight ends). turn_index points into the active
# participants in position order. world_start and world_end are in-world dates ({"year", "month", "day", "part",
# "text"}).
class Scenes(Base) :
	"""A tracked roleplay in one channel or thread, with a post order."""
	__tablename__ = "scenes"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	channel_id: Mapped[int] = mapped_column(BigInteger, index=True)
	title: Mapped[str] = mapped_column(String(200))
	host_uid: Mapped[int] = mapped_column(BigInteger)
	mode: Mapped[str] = mapped_column(String(16), default="order")
	state: Mapped[str] = mapped_column(String(16), default="open")
	paused_by_fight: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	location_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("locations.id", ondelete="SET NULL"),
	                                                nullable=True)
	turn_index: Mapped[int] = mapped_column(Integer, default=0)
	turn_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	card_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	last_post_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	idle_warned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	world_start: Mapped[dict | None] = mapped_column(JSON, nullable=True)
	world_end: Mapped[dict | None] = mapped_column(JSON, nullable=True)
	summary: Mapped[str | None] = mapped_column(Text, nullable=True)
	chronicle_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
	ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# state is active, left or removed.
class SceneParticipants(Base) :
	"""A character taking part in a scene."""
	__tablename__ = "scene_participants"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	scene_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("scenes.id", ondelete="CASCADE"), index=True)
	character_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"))
	uid: Mapped[int] = mapped_column(BigInteger)
	position: Mapped[int] = mapped_column(Integer, default=0)
	state: Mapped[str] = mapped_column(String(16), default="active")
	posts: Mapped[int] = mapped_column(Integer, default=0)
	words: Mapped[int] = mapped_column(Integer, default=0)
	skips: Mapped[int] = mapped_column(Integer, default=0)
	last_post_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	last_nudged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# thread_id is the chronicle's forum thread (or the thread on its message in a text channel); message_id its first
# message. channel_id, first_message_id and last_message_id are the roleplay it covers.
class Chronicles(Base) :
	"""A finished scene (or a stretch of older roleplay) written up as a transcript."""
	__tablename__ = "chronicles"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	scene_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("scenes.id", ondelete="SET NULL"),
	                                             nullable=True)
	title: Mapped[str] = mapped_column(String(200))
	channel_id: Mapped[int] = mapped_column(BigInteger)
	first_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	last_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	thread_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	summary: Mapped[str | None] = mapped_column(Text, nullable=True)
	created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChronicleCharacters(Base) :
	"""A character in a chronicle, with how much it wrote there."""
	__tablename__ = "chronicle_characters"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	chronicle_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chronicles.id", ondelete="CASCADE"), index=True)
	character_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"), index=True)
	posts: Mapped[int] = mapped_column(Integer, default=0)
	words: Mapped[int] = mapped_column(Integer, default=0)


# ============================================================
# Languages and letters
# ============================================================

# sound is a preset (flowing, harsh, clipped, sibilant, runes, glyphs) or custom, with syllables then the custom list.
# The common language is the one every character speaks.
class Languages(Base) :
	"""A language characters can speak; readers who don't know it see it scrambled."""
	__tablename__ = "languages"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	name: Mapped[str] = mapped_column(String(50))
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	sound: Mapped[str] = mapped_column(String(16), default="flowing")
	syllables: Mapped[list | None] = mapped_column(JSON, nullable=True)
	common: Mapped[bool] = mapped_column(Boolean, default=False)
	pack: Mapped[str | None] = mapped_column(String(50), nullable=True)

	__table_args__ = (
		Index('uq_language_guild_name', 'guild_id', text('lower(name)'), unique=True),
	)


# fluency is fluent or partial; source start, species, study or granted.
class CharacterLanguages(Base) :
	"""A language a character knows."""
	__tablename__ = "character_languages"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	character_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"), index=True)
	language_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("languages.id", ondelete="CASCADE"))
	fluency: Mapped[str] = mapped_column(String(16), default="fluent")
	source: Mapped[str] = mapped_column(String(16), default="start")

	__table_args__ = (
		UniqueConstraint('character_id', 'language_id', name='uq_character_language'),
	)


# segments is the post as written: [{"language": id or null, "text"}], null being the common language.
class ProxyLanguages(Base) :
	"""The original text of a post made in a language, by its first message."""
	__tablename__ = "proxy_languages"
	first_message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
	character_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="SET NULL"),
	                                                 nullable=True)
	segments: Mapped[list] = mapped_column(JSON, default=list)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# state is in_transit, held, delivered, returned or destroyed. world_date is the in-world date it was written on.
class Letters(Base) :
	"""An in-character letter from one character to another."""
	__tablename__ = "letters"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	from_character_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="SET NULL"),
	                                                      nullable=True)
	to_character_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="SET NULL"),
	                                                    nullable=True)
	from_uid: Mapped[int] = mapped_column(BigInteger)
	from_name: Mapped[str] = mapped_column(String(255))
	to_name: Mapped[str] = mapped_column(String(255))
	subject: Mapped[str] = mapped_column(String(200))
	body: Mapped[str] = mapped_column(Text)
	language_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("languages.id", ondelete="SET NULL"),
	                                                nullable=True)
	sealed: Mapped[bool] = mapped_column(Boolean, default=False)
	seal_broken: Mapped[bool] = mapped_column(Boolean, default=False)
	express: Mapped[bool] = mapped_column(Boolean, default=False)
	world_date: Mapped[dict | None] = mapped_column(JSON, nullable=True)
	deliver_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
	state: Mapped[str] = mapped_column(String(16), default="in_transit")
	read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	reply_to_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	intercepted_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# The economy round: factions, jobs, downtime and crafting
# ============================================================

# rivals lists faction ids: gaining standing here costs half as much there.
class Factions(Base) :
	"""A faction characters gain and lose standing with."""
	__tablename__ = "factions"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	name: Mapped[str] = mapped_column(String(100))
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	colour: Mapped[int | None] = mapped_column(Integer, nullable=True)
	emoji: Mapped[str | None] = mapped_column(String(64), nullable=True)
	hidden: Mapped[bool] = mapped_column(Boolean, default=False)
	rivals: Mapped[list] = mapped_column(JSON, default=list)

	__table_args__ = (
		Index('uq_faction_guild_name', 'guild_id', text('lower(name)'), unique=True),
	)


class CharacterReputation(Base) :
	"""A character's standing with a faction, from -100 to 100."""
	__tablename__ = "character_reputation"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	character_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"), index=True)
	faction_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("factions.id", ondelete="CASCADE"))
	value: Mapped[int] = mapped_column(Integer, default=0)

	__table_args__ = (
		UniqueConstraint('character_id', 'faction_id', name='uq_character_reputation'),
	)


class ReputationLog(Base) :
	"""Every change to a character's standing, for disputes and audits."""
	__tablename__ = "reputation_log"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	character_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"), index=True)
	faction_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("factions.id", ondelete="CASCADE"))
	amount: Mapped[int] = mapped_column(Integer)
	reason: Mapped[str] = mapped_column(String(32))
	actor_uid: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# reward is {"currency", "xp", "items": [names]}. state is open, taken, done, failed or cancelled. poster_character_id
# is set for a player's job, whose currency reward is held in escrow until it ends.
class Jobs(Base) :
	"""A job on the job board."""
	__tablename__ = "jobs"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	thread_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	poster_uid: Mapped[int] = mapped_column(BigInteger)
	poster_character_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("characters.id",
	                                                                              ondelete="SET NULL"), nullable=True)
	title: Mapped[str] = mapped_column(String(100))
	description: Mapped[str] = mapped_column(Text)
	reward: Mapped[dict] = mapped_column(JSON, default=dict)
	slots: Mapped[int] = mapped_column(Integer, default=1)
	min_level: Mapped[int] = mapped_column(Integer, default=1)
	faction_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("factions.id", ondelete="SET NULL"),
	                                               nullable=True)
	rep_success: Mapped[int] = mapped_column(Integer, default=0)
	rep_failure: Mapped[int] = mapped_column(Integer, default=0)
	location_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("locations.id", ondelete="SET NULL"),
	                                                nullable=True)
	deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	state: Mapped[str] = mapped_column(String(16), default="open")
	escrow: Mapped[int] = mapped_column(BigInteger, default=0)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# state is claimed, waiting, withdrawn or done; outcome success, partial or failure.
class JobClaims(Base) :
	"""A character on a job (or on its waiting list)."""
	__tablename__ = "job_claims"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	job_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
	character_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"))
	uid: Mapped[int] = mapped_column(BigInteger)
	state: Mapped[str] = mapped_column(String(16), default="claimed")
	outcome: Mapped[str | None] = mapped_column(String(16), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# day is the downtime day (DOWNTIME_RESET decides when it starts); one activity per character per day.
class Downtime(Base) :
	"""A character's downtime activity on one day."""
	__tablename__ = "downtime"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	character_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"), index=True)
	day: Mapped[str] = mapped_column(String(10))
	activity: Mapped[str] = mapped_column(String(16))
	outcome: Mapped[str] = mapped_column(String(16))
	details: Mapped[dict] = mapped_column(JSON, default=dict)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

	__table_args__ = (
		UniqueConstraint('character_id', 'day', name='uq_downtime_character_day'),
	)


class StudyProgress(Base) :
	"""How far a character is in studying a language."""
	__tablename__ = "study_progress"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	character_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"), index=True)
	language_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("languages.id", ondelete="CASCADE"))
	points: Mapped[int] = mapped_column(Integer, default=0)

	__table_args__ = (
		UniqueConstraint('character_id', 'language_id', name='uq_study_progress'),
	)


# ingredients is [{"item_id", "amount"}]. days 0 is made right away; more is a project worked on in downtime.
class Recipes(Base) :
	"""A crafting recipe: ingredients and a roll make an item."""
	__tablename__ = "recipes"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	name: Mapped[str] = mapped_column(String(100))
	result_item_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("gear_items.id", ondelete="CASCADE"),
	                                                   nullable=True)
	result_amount: Mapped[int] = mapped_column(Integer, default=1)
	ingredients: Mapped[list] = mapped_column(JSON, default=list)
	tool_item_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("gear_items.id", ondelete="SET NULL"),
	                                                 nullable=True)
	stat: Mapped[str] = mapped_column(String(16), default="intelligence")
	dc: Mapped[int] = mapped_column(Integer, default=12)
	occupation_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("occupations.id", ondelete="SET NULL"),
	                                                  nullable=True)
	occupation_required: Mapped[bool] = mapped_column(Boolean, default=False)
	min_level: Mapped[int] = mapped_column(Integer, default=1)
	faction_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("factions.id", ondelete="SET NULL"),
	                                               nullable=True)
	days: Mapped[int] = mapped_column(Integer, default=0)
	mishap_table_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("roll_tables.id", ondelete="SET NULL"),
	                                                    nullable=True)
	pack: Mapped[str | None] = mapped_column(String(50), nullable=True)
	# An enchanting recipe: only spellcasters, or characters with the recipe's occupation, can make it.
	enchanting: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

	__table_args__ = (
		Index('uq_recipe_guild_name', 'guild_id', text('lower(name)'), unique=True),
	)


# reserved is the ingredients set aside ([{"item_id", "amount"}]); state working, done or abandoned.
class CraftProjects(Base) :
	"""A recipe that takes days, worked on in downtime."""
	__tablename__ = "craft_projects"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	character_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"), index=True)
	recipe_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("recipes.id", ondelete="SET NULL"),
	                                              nullable=True)
	days_done: Mapped[int] = mapped_column(Integer, default=0)
	masterwork: Mapped[bool] = mapped_column(Boolean, default=False)
	# A bad failure on the way leaves a flaw: a flawed weapon or armor comes out cursed (unless also masterwork).
	flawed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
	state: Mapped[str] = mapped_column(String(16), default="working")
	reserved: Mapped[list] = mapped_column(JSON, default=list)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# Flavor: rumors and omens
# ============================================================

# truth is unknown, true, false or partial (GMs mark it; hidden from players). secret rumors are never posted, only
# overheard. heard counts how often characters overheard it; in whisper mode it spreads (is posted) at 3.
class Rumors(Base) :
	"""A rumor going round: posted anonymously, or planted by a GM."""
	__tablename__ = "rumors"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	author_uid: Mapped[int] = mapped_column(BigInteger)
	character_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="SET NULL"),
	                                                 nullable=True)
	text: Mapped[str] = mapped_column(Text)
	location_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("locations.id", ondelete="SET NULL"),
	                                                nullable=True)
	region_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("regions.id", ondelete="SET NULL"),
	                                              nullable=True)
	truth: Mapped[str] = mapped_column(String(16), default="unknown")
	secret: Mapped[bool] = mapped_column(Boolean, default=False)
	planted: Mapped[bool] = mapped_column(Boolean, default=False)
	heard: Mapped[int] = mapped_column(Integer, default=0)
	spread_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	pinned: Mapped[bool] = mapped_column(Boolean, default=False)
	expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RumorHeard(Base) :
	"""A character overheard a rumor."""
	__tablename__ = "rumor_heard"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	rumor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("rumors.id", ondelete="CASCADE"), index=True)
	character_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"), index=True)
	heard_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# kind is listen (once a real day per character) or block (a member who may not post rumors; character_id empty).
class RumorMarks(Base) :
	"""When a character last listened for rumors, and members blocked from posting them."""
	__tablename__ = "rumor_marks"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	kind: Mapped[str] = mapped_column(String(16))
	uid: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	character_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"),
	                                                 nullable=True)
	day: Mapped[str | None] = mapped_column(String(10), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# deck is a built-in deck's key (tarot, bones) or "table:<id>" for a server deck. cycle goes up each time the
# character's deck is reshuffled, so cards are drawn without replacement within a cycle.
class OmenDraws(Base) :
	"""A card a character drew."""
	__tablename__ = "omen_draws"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	character_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"), index=True)
	deck: Mapped[str] = mapped_column(String(32))
	card: Mapped[str] = mapped_column(String(100))
	cycle: Mapped[int] = mapped_column(Integer, default=1)
	reader_uid: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	drawn_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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


# offers is {"left": {"items": [character_gear ids], "currency": n}, "right": {...}}; accepted lists the sides that
# pressed Accept ("left", "right"). state is open, done, cancelled or expired (design/economy.md, phase 3).
class Trades(Base) :
	"""A trade between two characters of different players."""
	__tablename__ = "trades"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	left_character_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"))
	right_character_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"))
	left_uid: Mapped[int] = mapped_column(BigInteger)
	right_uid: Mapped[int] = mapped_column(BigInteger)
	offers: Mapped[dict] = mapped_column(JSON, default=dict)
	accepted: Mapped[list] = mapped_column(JSON, default=list)
	state: Mapped[str] = mapped_column(String(16), default="open")
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
	finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# state is open, sold, withdrawn or expired. While open, the item (character_gear) has the status "listed".
class MarketListings(Base) :
	"""An item a character offers on the market forum at a fixed price."""
	__tablename__ = "market_listings"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	entry_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("character_gear.id", ondelete="SET NULL"),
	                                             nullable=True)
	seller_character_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("characters.id",
	                                                                               ondelete="SET NULL"), nullable=True)
	seller_uid: Mapped[int] = mapped_column(BigInteger)
	name: Mapped[str] = mapped_column(String(100))
	price: Mapped[int] = mapped_column(BigInteger)
	fee: Mapped[int] = mapped_column(BigInteger, default=0)
	thread_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	state: Mapped[str] = mapped_column(String(16), default="open")
	buyer_character_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	buyer_uid: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
	expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# location_ids: where it trades (locations.id). buys: the gear kinds it buys (empty buys nothing). services: repair,
# lodging (later also healing, training, enchanting). restock is daily, weekly or manual; cycle counts restocks, so
# haggles last until the next one (design/economy.md, phase 4).
class Merchants(Base) :
	"""An NPC shop at one or more locations."""
	__tablename__ = "merchants"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	name: Mapped[str] = mapped_column(String(100))
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
	location_ids: Mapped[list] = mapped_column(JSON, default=list)
	faction_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	markup: Mapped[float] = mapped_column(Float, default=1.0)
	buys: Mapped[list] = mapped_column(JSON, default=list)
	pays: Mapped[float] = mapped_column(Float, default=1.0)
	services: Mapped[list] = mapped_column(JSON, default=list)
	lodging_price: Mapped[int] = mapped_column(Integer, default=0)
	haggle_dc: Mapped[int | None] = mapped_column(Integer, nullable=True)
	restock: Mapped[str] = mapped_column(String(16), default="weekly")
	last_restock: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	cycle: Mapped[int] = mapped_column(Integer, default=0)

	__table_args__ = (
		Index('uq_merchant_guild_name', 'guild_id', text('lower(name)'), unique=True),
	)


# quantity: how many a restock brings (empty is unlimited). chance: the percent chance it is there after a restock
# (100 always). in_stock: how many are left now (empty is unlimited); available: whether it is there this cycle.
class MerchantStock(Base) :
	"""An item a merchant sells."""
	__tablename__ = "merchant_stock"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	merchant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("merchants.id", ondelete="CASCADE"), index=True)
	gear_item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("gear_items.id", ondelete="CASCADE"))
	quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
	chance: Mapped[int] = mapped_column(Integer, default=100)
	price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	in_stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
	available: Mapped[bool] = mapped_column(Boolean, default=True)


# One per character, merchant, item and restock cycle: the discount won (percent), or refused (a bad failure: the
# merchant won't deal with the character until the next restock; gear_item_id is then empty).
class MerchantHaggles(Base) :
	"""A character's haggle with a merchant."""
	__tablename__ = "merchant_haggles"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	merchant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("merchants.id", ondelete="CASCADE"), index=True)
	character_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"))
	gear_item_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	cycle: Mapped[int] = mapped_column(Integer)
	discount: Mapped[int] = mapped_column(Integer, default=0)
	refused: Mapped[bool] = mapped_column(Boolean, default=False)


class Lodgings(Base) :
	"""A room a character rents at a location: it opens the stash there."""
	__tablename__ = "lodgings"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	character_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"), index=True)
	location_id: Mapped[int] = mapped_column(BigInteger)
	merchant_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	paid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# enchantments as on gear_items. state is pending, approved or denied; approval makes result_item_id (a crafted-only
# catalog item) and recipe_id (its enchanting recipe).
class EnchantDesigns(Base) :
	"""A player's design for an enchanted item, waiting for staff review."""
	__tablename__ = "enchant_designs"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	creator_uid: Mapped[int] = mapped_column(BigInteger)
	character_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="SET NULL"),
	                                                 nullable=True)
	base_item_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("gear_items.id", ondelete="SET NULL"),
	                                                 nullable=True)
	name: Mapped[str] = mapped_column(String(100))
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	rarity: Mapped[str] = mapped_column(String(16))
	enchantments: Mapped[dict] = mapped_column(JSON, default=dict)
	state: Mapped[str] = mapped_column(String(16), default="pending")
	review_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	result_item_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	recipe_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# items: [{"item_id", "name", "amount", "claims": [character ids], "winner": character id}]. state is open or settled.
class FightLoot(Base) :
	"""What the defeated enemies of a fight dropped, waiting to be shared."""
	__tablename__ = "fight_loot"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
	fight_id: Mapped[int] = mapped_column(BigInteger)
	channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
	currency: Mapped[int] = mapped_column(Integer, default=0)
	items: Mapped[list] = mapped_column(JSON, default=list)
	mode: Mapped[str] = mapped_column(String(16), default="gm")
	state: Mapped[str] = mapped_column(String(16), default="open")
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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
