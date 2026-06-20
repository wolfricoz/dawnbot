import os
from datetime import datetime
from typing import List

import pymysql
from dotenv import load_dotenv
from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, create_engine, func, \
	text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy_utils import create_database, database_exists

pymysql.install_as_MySQLdb()

load_dotenv('.env')
dblink = os.getenv('DB')
engine = create_engine(dblink, poolclass=NullPool, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
if not database_exists(engine.url) :
	create_database(engine.url)

conn = engine.connect()


class Base(DeclarativeBase) :
	pass


class Timestamps :
	"""Adds the created_at and updated_at columns to the session."""
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
	updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
	status: Mapped[int] = mapped_column(Integer, default=1)


class Users(Timestamps, Base) :
	__tablename__ = "users"
	uid: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
	messages: Mapped[int] = mapped_column(BigInteger, default=0)
	xp: Mapped[int] = mapped_column(BigInteger, default=0)
	currency: Mapped[int] = mapped_column(BigInteger, default=0)
	guildid: Mapped[int] = mapped_column(BigInteger, default=559139888356917259)


class Levels(Timestamps, Base) :
	__tablename__ = "levels"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guildid: Mapped[int] = mapped_column(BigInteger)
	role_id: Mapped[int] = mapped_column(BigInteger)
	xp_required: Mapped[int] = mapped_column(BigInteger)


class Channels(Timestamps, Base) :
	__tablename__ = "channels"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guildid: Mapped[int] = mapped_column(BigInteger)
	channelid: Mapped[int] = mapped_column(BigInteger)


class Characters(Timestamps, Base) :
	__tablename__ = "characters"
	uid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
	guild_id: Mapped[int] = mapped_column(BigInteger)
	name: Mapped[str] = mapped_column(String(255), primary_key=True)
	prestige: Mapped[int] = mapped_column(BigInteger, default=0)
	strength: Mapped[int] = mapped_column(BigInteger, default=0)
	perception: Mapped[int] = mapped_column(BigInteger, default=0)
	endurance: Mapped[int] = mapped_column(BigInteger, default=0)
	charisma: Mapped[int] = mapped_column(BigInteger, default=0)
	intelligence: Mapped[int] = mapped_column(BigInteger, default=0)
	agility: Mapped[int] = mapped_column(BigInteger, default=0)
	armor = mapped_column(BigInteger, ForeignKey('armors.id'))


class Armors(Timestamps, Base) :
	__tablename__ = "armors"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	name: Mapped[str] = mapped_column(String(255))
	hp: Mapped[int] = mapped_column(BigInteger, default=75)
	ap: Mapped[int] = mapped_column(BigInteger, default=0)
	ac: Mapped[int] = mapped_column(BigInteger, default=12)
	hitchance: Mapped[int] = mapped_column(BigInteger, default=0)
	modifier: Mapped[str] = mapped_column(String(255), nullable=True)


class Weapons(Timestamps, Base) :
	__tablename__ = "weapons"
	name: Mapped[str] = mapped_column(String(255), primary_key=True)
	dice: Mapped[str] = mapped_column(String(255))
	modifier: Mapped[str] = mapped_column(String(255))
	hitmodifier = mapped_column(BigInteger, default=0)


class Npcs(Timestamps, Base) :
	__tablename__ = "npcs"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	name: Mapped[str] = mapped_column(String(255))
	hp: Mapped[int] = mapped_column(BigInteger)
	ac: Mapped[int] = mapped_column(BigInteger)
	attack: Mapped[str] = mapped_column(String(1024), default="1d20")
	damage: Mapped[str] = mapped_column(String(1024), default="1d12")

class CombatInstances(Timestamps, Base) :
	__tablename__ = "combat_instances"
	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	guid: Mapped[str] = mapped_column(String(255), server_default=text("gen_random_uuid()")) # this will be shown to the front-end
	channel_id: Mapped[int] = mapped_column(BigInteger, nullable=True) # only one instance can be active per channel; threads act as their own channel.
	entities: Mapped[List["CombatInstanceEntities"]] = relationship(
	        "CombatInstanceEntities",
	        back_populates="combat_instance",
	        cascade="all, delete-orphan", # Automatically wipes out entities if the instance is deleted
					lazy = "joined"
	    )
	round: Mapped[int] = mapped_column(BigInteger, default=1)
	combat_type: Mapped[str] = mapped_column(String(255), nullable=True, default="encounter")
	active: Mapped[bool] = mapped_column(Boolean, default=True)


class CombatInstanceEntities(Timestamps, Base) :
	__tablename__ = "combat_instance_entities"

	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

	# Connects it to the main instance
	instance_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("combat_instances.id", ondelete="CASCADE"),
	                                         nullable=False)

	# Foreign keys to character data
	character_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("characters.id", ondelete="CASCADE"),
	                                                 nullable=True)
	monster_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("monsters.id", ondelete="CASCADE"),
	                                               nullable=True)
	npc_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("npcs.id", ondelete="CASCADE"), nullable=True)

	# Stats
	current_hp: Mapped[int] = mapped_column(BigInteger, default=0)
	armor: Mapped[int] = mapped_column(BigInteger, default=0)

	# System Data
	entity_type: Mapped[str] = mapped_column(String(255), nullable=True)
	remaining_attacks: Mapped[int] = mapped_column(BigInteger, default=1)

	combat_instance: Mapped["CombatInstances"] = relationship(
		"CombatInstances",
		back_populates="entities"
	)

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

	# Connects it to the main instance
	instance_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("combat_instances.id", ondelete="CASCADE"),
	                                         nullable=False)

	attacker_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("combat_instance_entities.id", ondelete="CASCADE"),)
	defender_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("combat_instance_entities.id", ondelete="CASCADE"))
	damage: Mapped[int] = mapped_column(BigInteger, default=0)






class database :
	def create(self) :
		Base.metadata.create_all(engine)
