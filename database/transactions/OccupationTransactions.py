from sqlalchemy import Select, func

from database.database import Characters, Occupations
from database.transactions.DatabaseTransactions import DatabaseTransactions

# Columns add() and update() accept as keyword arguments.
FIELDS = ["name", "description", "max_holders", "min_level", "role_id", "staff_only", "pay", "work_stat", "table_id", "flavor", "seer", "faction_id", "faction_tier", "repairs"]
# Characters in these states hold their occupation's place; retired and denied ones free it.
HOLDING_STATES = ["pending", "approved"]


# Names are unique per server, compared without case; positions start at 1.
class OccupationTransactions(DatabaseTransactions) :
	"""The occupations of a server."""

	# ============================================================
	def get_all(self, guild_id: int) -> list[Occupations] :
		with self.createsession() as session :
			return list(session.scalars(Select(Occupations).where(Occupations.guild_id == guild_id)
			                            .order_by(Occupations.position, Occupations.id)).all())

	# ============================================================
	def get(self, occupation_id: int | None) -> Occupations | None :
		if occupation_id is None :
			return None
		with self.createsession() as session :
			return session.scalar(Select(Occupations).where(Occupations.id == occupation_id))

	# ============================================================
	def find(self, guild_id: int, name: str) -> Occupations | None :
		with self.createsession() as session :
			return session.scalar(Select(Occupations).where(Occupations.guild_id == guild_id,
			                                                func.lower(Occupations.name) == name.lower()))

	# ============================================================
	def add(self, guild_id: int, name: str, **fields) -> Occupations | None :
		"""Adds an occupation at the end; returns None when the name is already used."""
		if self.find(guild_id, name) is not None :
			return None
		position = len(self.get_all(guild_id)) + 1
		with self.createsession() as session :
			occupation = Occupations(guild_id=guild_id, name=name, position=position,
			                         **{key : value for key, value in fields.items() if key in FIELDS})
			session.add(occupation)
			self.commit(session)
			return occupation if occupation.id is not None else None

	# ============================================================
	def update(self, occupation_id: int, **fields) -> Occupations | None :
		"""Sets the given fields. Unlike None, a missing keyword leaves a field unchanged."""
		with self.createsession() as session :
			occupation = session.scalar(Select(Occupations).where(Occupations.id == occupation_id))
			if occupation is None :
				return None
			for key, value in fields.items() :
				if key in FIELDS :
					setattr(occupation, key, value)
			self.commit(session)
			return occupation

	# ============================================================
	def move(self, guild_id: int, name: str, position: int) -> bool :
		ids = [occupation.id for occupation in self.get_all(guild_id)]
		occupation = self.find(guild_id, name)
		if occupation is None :
			return False
		ids.remove(occupation.id)
		position = max(1, min(position, len(ids) + 1))
		ids.insert(position - 1, occupation.id)
		with self.createsession() as session :
			for row in session.scalars(Select(Occupations).where(Occupations.guild_id == guild_id)) :
				row.position = ids.index(row.id) + 1
			self.commit(session)
		return True

	# ============================================================
	def delete(self, occupation_id: int) -> bool :
		"""Removes an occupation; characters that held it are left without one."""
		occupation = self.get(occupation_id)
		if occupation is None :
			return False
		with self.createsession() as session :
			session.delete(session.merge(occupation))
			self.commit(session)
		with self.createsession() as session :
			for index, row in enumerate(session.scalars(Select(Occupations)
			                                            .where(Occupations.guild_id == occupation.guild_id)
			                                            .order_by(Occupations.position, Occupations.id)), start=1) :
				row.position = index
			self.commit(session)
		return True

	# ============================================================
	def holders(self, occupation_id: int, exclude_character: int | None = None) -> list[Characters] :
		"""The characters that hold the occupation's places: those that have it while pending or approved, and
		approved ones with a change to it waiting for review."""
		occupation = self.get(occupation_id)
		if occupation is None :
			return []
		with self.createsession() as session :
			characters = list(session.scalars(Select(Characters).where(Characters.guild_id == occupation.guild_id,
			                                                           Characters.state.in_(HOLDING_STATES))))
		holders = []
		for character in characters :
			if character.id == exclude_character :
				continue
			pending = (character.pending_changes or {}).get("occupation_id")
			if character.occupation_id == occupation_id or pending == occupation_id :
				holders.append(character)
		return holders
