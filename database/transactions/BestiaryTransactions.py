from sqlalchemy import Select, func

from database.database import Bestiary
from database.transactions.DatabaseTransactions import DatabaseTransactions

FIELDS = ["name", "description", "avatar_url", "preset", "hp", "ac", "dt", "to_hit", "damage", "damage_type",
          "attack_name", "ap", "sequence", "behavior", "ability_ids", "reward_xp", "reward_currency", "creator_uid",
          "special", "level", "weapon_ids", "armor_id"]


class BestiaryTransactions(DatabaseTransactions) :
	"""A server's bestiary. Names are unique per server, compared without case."""

	# ============================================================
	def get_all(self, guild_id: int) -> list[Bestiary] :
		with self.createsession() as session :
			return list(session.scalars(Select(Bestiary).where(Bestiary.guild_id == guild_id)
			                            .order_by(func.lower(Bestiary.name))).all())

	# ============================================================
	def get(self, entry_id: int | None) -> Bestiary | None :
		if entry_id is None :
			return None
		with self.createsession() as session :
			return session.scalar(Select(Bestiary).where(Bestiary.id == entry_id))

	# ============================================================
	def find(self, guild_id: int, name: str) -> Bestiary | None :
		with self.createsession() as session :
			return session.scalar(Select(Bestiary).where(Bestiary.guild_id == guild_id,
			                                             func.lower(Bestiary.name) == (name or "").lower()))

	# ============================================================
	def add(self, guild_id: int, name: str, **fields) -> Bestiary | None :
		if self.find(guild_id, name) is not None :
			return None
		with self.createsession() as session :
			record = Bestiary(guild_id=guild_id, name=name,
			                  **{key : value for key, value in fields.items() if key in FIELDS and key != "name"})
			record.ability_ids = record.ability_ids or []
			session.add(record)
			self.commit(session)
			return record if record.id is not None else None

	# ============================================================
	def update(self, entry_id: int, **fields) -> Bestiary | None :
		with self.createsession() as session :
			record = session.scalar(Select(Bestiary).where(Bestiary.id == entry_id))
			if record is None :
				return None
			for key, value in fields.items() :
				if key in FIELDS :
					setattr(record, key, value)
			self.commit(session)
			return record

	# ============================================================
	def delete(self, entry_id: int) -> bool :
		with self.createsession() as session :
			record = session.scalar(Select(Bestiary).where(Bestiary.id == entry_id))
			if record is None :
				return False
			session.delete(record)
			self.commit(session)
			return True
