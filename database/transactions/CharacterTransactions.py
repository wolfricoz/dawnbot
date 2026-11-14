from typing import List

from sqlalchemy import Select

from database.database import Characters
from database.transactions.DatabaseTransactions import DatabaseTransactions
from database.transactions.UserTransactions import UserTransactions

# Columns add() and update() accept as keyword arguments.
STAT_FIELDS = ["strength", "perception", "endurance", "charisma", "intelligence", "agility", "prestige", "luck",
               "prefix"]


class CharacterTransactions(DatabaseTransactions) :
	"""Player characters. A user's character names are unique (uq_character_uid_name) and stored lowercase."""

	# ============================================================
	def get_all(self, user_id: int, guild_id: int) -> List[Characters] :
		with self.createsession() as session :
			return list(session.scalars(
				Select(Characters).where(Characters.uid == user_id, Characters.guild_id == guild_id)).unique().all())

	# ============================================================
	def get_every_character(self) -> List[Characters] :
		with self.createsession() as session :
			return list(session.scalars(Select(Characters)).unique().all())

	# ============================================================
	def get(self, user_id: int, name: str) -> Characters | None :
		with self.createsession() as session :
			return session.scalars(
				Select(Characters).where(Characters.uid == user_id, Characters.name == name.lower())).unique().first()

	# ============================================================
	def get_by_id(self, character_id: int) -> Characters | None :
		with self.createsession() as session :
			return session.scalars(Select(Characters).where(Characters.id == character_id)).unique().first()

	# ============================================================
	def add(self, user_id: int, guild_id: int, name: str, armor_id: int, **stats) -> Characters | None :
		"""Creates a character; stats are any of STAT_FIELDS. Returns None if the user already has that name."""
		# Characters reference users.uid, so make sure the user is registered.
		UserTransactions().get(user_id, guild_id)
		with self.createsession() as session :
			if self.get(user_id, name) is not None :
				return None
			character = Characters(uid=user_id, guild_id=guild_id, name=name.lower(), armor=armor_id,
			                       **{key : value for key, value in stats.items() if key in STAT_FIELDS})
			session.add(character)
			self.commit(session)
			return character

	# ============================================================
	def update(self, user_id: int, name: str, armor_id: int = None, **stats) -> Characters | None :
		"""Updates the given fields; None leaves a field unchanged."""
		with self.createsession() as session :
			character = session.scalars(
				Select(Characters).where(Characters.uid == user_id, Characters.name == name.lower())).unique().first()
			if character is None :
				return None
			if armor_id is not None :
				character.armor = armor_id
			for key, value in stats.items() :
				if key in STAT_FIELDS and value is not None :
					setattr(character, key, value)
			self.commit(session)
			return character

	# ============================================================
	def delete(self, user_id: int, name: str) -> bool :
		with self.createsession() as session :
			character = session.scalars(
				Select(Characters).where(Characters.uid == user_id, Characters.name == name.lower())).unique().first()
			if character is None :
				return False
			session.delete(character)
			self.commit(session)
			return True
