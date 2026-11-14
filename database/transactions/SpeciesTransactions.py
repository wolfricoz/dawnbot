from sqlalchemy import Select, func

from database.database import Characters, Species
from database.transactions.DatabaseTransactions import DatabaseTransactions

PENDING = "pending"
APPROVED = "approved"
DENIED = "denied"

# Columns add() and update() accept as keyword arguments.
FIELDS = ["name", "creator_uid", "description", "benefits", "drawbacks", "state", "stat_limits", "stat_modifiers",
          "tag_ids", "forum_thread_id", "forum_message_id", "review_message_id", "pending_changes"]


class SpeciesTransactions(DatabaseTransactions) :
	"""The species of a server. Names are unique per server, compared without case."""

	# ============================================================
	def get_all(self, guild_id: int, states: list[str] | None = None) -> list[Species] :
		with self.createsession() as session :
			query = Select(Species).where(Species.guild_id == guild_id)
			if states is not None :
				query = query.where(Species.state.in_(states))
			return list(session.scalars(query.order_by(func.lower(Species.name))).all())

	# ============================================================
	def get(self, species_id: int | None) -> Species | None :
		if species_id is None :
			return None
		with self.createsession() as session :
			return session.scalar(Select(Species).where(Species.id == species_id))

	# ============================================================
	def find(self, guild_id: int, name: str) -> Species | None :
		with self.createsession() as session :
			return session.scalar(Select(Species).where(Species.guild_id == guild_id,
			                                            func.lower(Species.name) == name.lower()))

	# ============================================================
	def get_by_review_message(self, message_id: int) -> Species | None :
		with self.createsession() as session :
			return session.scalar(Select(Species).where(Species.review_message_id == message_id))

	# ============================================================
	def get_by_thread(self, thread_id: int) -> Species | None :
		with self.createsession() as session :
			return session.scalar(Select(Species).where(Species.forum_thread_id == thread_id))

	# ============================================================
	def add(self, guild_id: int, name: str, **fields) -> Species | None :
		"""Returns None when the server already has a species with that name, or it could not be saved."""
		if self.find(guild_id, name) is not None :
			return None
		with self.createsession() as session :
			species = Species(guild_id=guild_id, name=name, **{key : value for key, value in fields.items()
			                                                   if key in FIELDS})
			species.stat_limits = species.stat_limits or {}
			species.stat_modifiers = species.stat_modifiers or {}
			species.tag_ids = species.tag_ids or []
			session.add(species)
			self.commit(session)
			return species if species.id is not None else None

	# ============================================================
	def update(self, species_id: int, **fields) -> Species | None :
		"""Sets the given fields. Unlike None, a missing keyword leaves a field unchanged."""
		with self.createsession() as session :
			species = session.scalar(Select(Species).where(Species.id == species_id))
			if species is None :
				return None
			for key, value in fields.items() :
				if key in FIELDS :
					setattr(species, key, value)
			self.commit(session)
			return species

	# ============================================================
	def users(self, species_id: int) -> int :
		"""How many characters are this species."""
		with self.createsession() as session :
			return session.scalar(Select(func.count(Characters.id)).where(Characters.species_id == species_id)) or 0

	# ============================================================
	def delete(self, species_id: int) -> bool :
		with self.createsession() as session :
			species = session.scalar(Select(Species).where(Species.id == species_id))
			if species is None :
				return False
			session.delete(species)
			self.commit(session)
			return True
