from sqlalchemy import Select, delete, func

from database.database import DamageTypes
from database.transactions.DatabaseTransactions import DatabaseTransactions

# Columns add() and update() accept as keyword arguments.
FIELDS = ["name", "trigger", "effect", "description", "pack"]


class DamageTypeTransactions(DatabaseTransactions) :
	"""A server's damage types. Names are unique per server, compared without case."""

	# ============================================================
	def get_all(self, guild_id: int) -> list[DamageTypes] :
		with self.createsession() as session :
			return list(session.scalars(Select(DamageTypes).where(DamageTypes.guild_id == guild_id)
			                            .order_by(DamageTypes.id)).all())

	# ============================================================
	def find(self, guild_id: int, name: str) -> DamageTypes | None :
		with self.createsession() as session :
			return session.scalar(Select(DamageTypes).where(DamageTypes.guild_id == guild_id,
			                                                func.lower(DamageTypes.name) == (name or "").lower()))

	# ============================================================
	def add(self, guild_id: int, name: str, **fields) -> DamageTypes | None :
		if self.find(guild_id, name) is not None :
			return None
		with self.createsession() as session :
			record = DamageTypes(guild_id=guild_id, name=name,
			                     **{key : value for key, value in fields.items() if key in FIELDS and key != "name"})
			record.effect = record.effect or {"kind" : "none"}
			session.add(record)
			self.commit(session)
			return record if record.id is not None else None

	# ============================================================
	def update(self, type_id: int, **fields) -> DamageTypes | None :
		with self.createsession() as session :
			record = session.scalar(Select(DamageTypes).where(DamageTypes.id == type_id))
			if record is None :
				return None
			for key, value in fields.items() :
				if key in FIELDS :
					setattr(record, key, value)
			self.commit(session)
			return record

	# ============================================================
	def delete(self, type_id: int) -> bool :
		with self.createsession() as session :
			record = session.scalar(Select(DamageTypes).where(DamageTypes.id == type_id))
			if record is None :
				return False
			session.delete(record)
			self.commit(session)
			return True

	# ============================================================
	def delete_all(self, guild_id: int) -> None :
		with self.createsession() as session :
			session.execute(delete(DamageTypes).where(DamageTypes.guild_id == guild_id))
			self.commit(session)
