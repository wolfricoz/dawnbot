from datetime import datetime, timezone
from typing import List

from sqlalchemy import Select, func

from database.database import Characters
from database.transactions.DatabaseTransactions import DatabaseTransactions
from database.transactions.UserTransactions import UserTransactions

# The review states of a character.
PENDING = "pending"
APPROVED = "approved"
DENIED = "denied"
RETIRED = "retired"

# Columns add() and update() accept as keyword arguments.
FIELDS = ["name", "state", "prefix", "suffix", "avatar_id", "strength", "perception", "endurance", "charisma",
          "intelligence", "agility", "luck", "stat_method", "rerolls", "unspent_points", "xp", "level", "currency",
          "forum_thread_id", "forum_message_ids", "review_message_id", "pending_changes", "approved_by", "approved_at"]


class CharacterTransactions(DatabaseTransactions) :
	"""Player characters. A user's character names are unique per server, compared without case."""

	# ============================================================
	def get_all(self, user_id: int, guild_id: int, states: list[str] | None = None) -> List[Characters] :
		"""The user's characters in the guild, oldest first; states limits them to those review states."""
		with self.createsession() as session :
			query = Select(Characters).where(Characters.uid == user_id, Characters.guild_id == guild_id)
			if states is not None :
				query = query.where(Characters.state.in_(states))
			return list(session.scalars(query.order_by(Characters.id)).all())

	# ============================================================
	def get_in_guild(self, guild_id: int, user_id: int | None = None) -> List[Characters] :
		"""Every character on the server, or only one member's."""
		with self.createsession() as session :
			query = Select(Characters).where(Characters.guild_id == guild_id)
			if user_id is not None :
				query = query.where(Characters.uid == user_id)
			return list(session.scalars(query.order_by(Characters.id)).all())

	# ============================================================
	def get_every_character(self) -> List[Characters] :
		with self.createsession() as session :
			return list(session.scalars(Select(Characters).order_by(Characters.id)).all())

	# ============================================================
	def get(self, user_id: int, guild_id: int, name: str) -> Characters | None :
		with self.createsession() as session :
			return session.scalars(
				Select(Characters).where(Characters.uid == user_id, Characters.guild_id == guild_id,
				                         func.lower(Characters.name) == name.lower())).first()

	# ============================================================
	def get_by_id(self, character_id: int) -> Characters | None :
		with self.createsession() as session :
			return session.scalars(Select(Characters).where(Characters.id == character_id)).first()

	# ============================================================
	def get_by_review_message(self, message_id: int) -> Characters | None :
		"""The character whose review card is the given message."""
		with self.createsession() as session :
			return session.scalars(Select(Characters).where(Characters.review_message_id == message_id)).first()

	# ============================================================
	def count_active(self, user_id: int, guild_id: int) -> int :
		"""How many of the user's characters count toward the server's cap: every one that is not retired."""
		with self.createsession() as session :
			return session.scalar(
				Select(func.count(Characters.id)).where(Characters.uid == user_id, Characters.guild_id == guild_id,
				                                        Characters.state != RETIRED)) or 0

	# ============================================================
	def trigger_taken(self, user_id: int, guild_id: int, prefix: str | None, suffix: str | None,
	                  exclude_id: int | None = None) -> bool :
		"""True when another of the user's characters in the guild already uses this prefix and suffix."""
		wanted = ((prefix or "").lower(), (suffix or "").lower())
		for character in self.get_all(user_id, guild_id) :
			if character.id == exclude_id :
				continue
			if ((character.prefix or "").lower(), (character.suffix or "").lower()) == wanted :
				return True
		return False

	# ============================================================
	def add(self, user_id: int, guild_id: int, name: str, **fields) -> Characters | None :
		"""Creates a character; fields are any of FIELDS. Returns None if the user already has that name there, or
		when it could not be saved."""
		# Characters reference users.uid, so make sure the user is registered.
		UserTransactions().get(user_id, guild_id)
		with self.createsession() as session :
			if self.get(user_id, guild_id, name) is not None :
				return None
			character = Characters(uid=user_id, guild_id=guild_id, name=name,
			                       **{key : value for key, value in fields.items() if key in FIELDS})
			session.add(character)
			self.commit(session)
			# A failed commit is rolled back without raising; the character then never got an id.
			return character if character.id is not None else None

	# ============================================================
	def update(self, character_id: int, **fields) -> Characters | None :
		"""Sets the given fields. Unlike None, a missing keyword leaves a field unchanged."""
		with self.createsession() as session :
			character = session.scalars(Select(Characters).where(Characters.id == character_id)).first()
			if character is None :
				return None
			for key, value in fields.items() :
				if key in FIELDS :
					setattr(character, key, value)
			self.commit(session)
			return character

	# ============================================================
	def progress(self, character_id: int, level_for_xp, points_per_level: int, add_xp: int = 0,
	             set_xp: int | None = None, add_currency: int = 0) -> tuple[Characters | None, int] :
		"""Changes a character's XP and currency and levels it up, holding a lock on its row so posts that arrive at
		the same time cannot overwrite each other.

		level_for_xp turns an amount of XP into a level. A level never goes down.
		@return: the updated character (None when it does not exist) and the number of levels gained.
		"""
		with self.createsession() as session :
			character = session.scalars(
				Select(Characters).where(Characters.id == character_id).with_for_update()).first()
			if character is None :
				return None, 0
			xp = set_xp if set_xp is not None else character.xp + add_xp
			character.xp = max(0, xp)
			character.currency = character.currency + add_currency
			level = max(character.level, level_for_xp(character.xp))
			gained = level - character.level
			character.level = level
			character.unspent_points = character.unspent_points + gained * points_per_level
			self.commit(session)
			return character, gained

	# ============================================================
	def approve(self, character_id: int, reviewer_id: int) -> Characters | None :
		return self.update(character_id, state=APPROVED, approved_by=reviewer_id,
		                   approved_at=datetime.now(timezone.utc), review_message_id=None)

	# ============================================================
	def delete(self, character_id: int) -> bool :
		with self.createsession() as session :
			character = session.scalars(Select(Characters).where(Characters.id == character_id)).first()
			if character is None :
				return False
			session.delete(character)
			self.commit(session)
			return True
