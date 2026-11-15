from sqlalchemy import Select, func

from database.database import Abilities, CharacterAbilities, MagicSchools
from database.transactions.DatabaseTransactions import DatabaseTransactions

PENDING = "pending"
APPROVED = "approved"
DENIED = "denied"

ABILITY_FIELDS = ["name", "description", "flavor", "kind", "school_id", "stat", "tier", "effect", "damage_type",
                  "condition", "area", "secondary", "state", "review_message_id", "forum_thread_id",
                  "forum_message_id", "tag_ids", "creator_uid"]
SCHOOL_FIELDS = ["name", "description", "casting_stat", "state", "standard", "review_message_id", "creator_uid"]


class AbilityTransactions(DatabaseTransactions) :
	"""Abilities, the abilities characters know, and magic schools."""

	# == abilities ==

	# ============================================================
	def get_all(self, guild_id: int, states: list[str] | None = None) -> list[Abilities] :
		with self.createsession() as session :
			query = Select(Abilities).where(Abilities.guild_id == guild_id)
			if states :
				query = query.where(Abilities.state.in_(states))
			return list(session.scalars(query.order_by(func.lower(Abilities.name))).all())

	# ============================================================
	def get(self, ability_id: int | None) -> Abilities | None :
		if ability_id is None :
			return None
		with self.createsession() as session :
			return session.scalar(Select(Abilities).where(Abilities.id == ability_id))

	# ============================================================
	def find(self, guild_id: int, name: str) -> Abilities | None :
		with self.createsession() as session :
			return session.scalar(Select(Abilities).where(Abilities.guild_id == guild_id,
			                                              func.lower(Abilities.name) == (name or "").lower()))

	# ============================================================
	def get_by_review_message(self, message_id: int) -> Abilities | None :
		with self.createsession() as session :
			return session.scalar(Select(Abilities).where(Abilities.review_message_id == message_id))

	# ============================================================
	def get_by_thread(self, thread_id: int) -> Abilities | None :
		with self.createsession() as session :
			return session.scalar(Select(Abilities).where(Abilities.forum_thread_id == thread_id))

	# ============================================================
	def add(self, guild_id: int, name: str, **fields) -> Abilities | None :
		if self.find(guild_id, name) is not None :
			return None
		with self.createsession() as session :
			record = Abilities(guild_id=guild_id, name=name,
			                   **{key : value for key, value in fields.items() if key in ABILITY_FIELDS and key != "name"})
			record.tag_ids = record.tag_ids or []
			session.add(record)
			self.commit(session)
			return record if record.id is not None else None

	# ============================================================
	def update(self, ability_id: int, **fields) -> Abilities | None :
		with self.createsession() as session :
			record = session.scalar(Select(Abilities).where(Abilities.id == ability_id))
			if record is None :
				return None
			for key, value in fields.items() :
				if key in ABILITY_FIELDS :
					setattr(record, key, value)
			self.commit(session)
			return record

	# ============================================================
	def delete(self, ability_id: int) -> bool :
		with self.createsession() as session :
			record = session.scalar(Select(Abilities).where(Abilities.id == ability_id))
			if record is None :
				return False
			session.delete(record)
			self.commit(session)
			return True

	# == what characters know ==

	# ============================================================
	def known(self, character_id: int) -> list[tuple[CharacterAbilities, Abilities]] :
		"""The character's abilities with their definitions, in the order they were learned."""
		with self.createsession() as session :
			rows = session.execute(Select(CharacterAbilities, Abilities)
			                       .join(Abilities, Abilities.id == CharacterAbilities.ability_id)
			                       .where(CharacterAbilities.character_id == character_id)
			                       .order_by(CharacterAbilities.id)).all()
			return [(row[0], row[1]) for row in rows]

	# ============================================================
	def learn(self, character_id: int, ability_id: int, event: bool = False,
	          granted_by: int | None = None) -> CharacterAbilities | None :
		with self.createsession() as session :
			existing = session.scalar(Select(CharacterAbilities).where(CharacterAbilities.character_id == character_id,
			                                                           CharacterAbilities.ability_id == ability_id))
			if existing is not None :
				return None
			record = CharacterAbilities(character_id=character_id, ability_id=ability_id, event=event,
			                            granted_by=granted_by)
			session.add(record)
			self.commit(session)
			return record if record.id is not None else None

	# ============================================================
	def forget(self, character_id: int, ability_id: int) -> bool :
		with self.createsession() as session :
			record = session.scalar(Select(CharacterAbilities).where(CharacterAbilities.character_id == character_id,
			                                                         CharacterAbilities.ability_id == ability_id))
			if record is None :
				return False
			session.delete(record)
			self.commit(session)
			return True

	# == magic schools ==

	# ============================================================
	def schools(self, guild_id: int, states: list[str] | None = None) -> list[MagicSchools] :
		with self.createsession() as session :
			query = Select(MagicSchools).where(MagicSchools.guild_id == guild_id)
			if states :
				query = query.where(MagicSchools.state.in_(states))
			return list(session.scalars(query.order_by(MagicSchools.standard.desc(),
			                                           func.lower(MagicSchools.name))).all())

	# ============================================================
	def school(self, school_id: int | None) -> MagicSchools | None :
		if school_id is None :
			return None
		with self.createsession() as session :
			return session.scalar(Select(MagicSchools).where(MagicSchools.id == school_id))

	# ============================================================
	def find_school(self, guild_id: int, name: str) -> MagicSchools | None :
		with self.createsession() as session :
			return session.scalar(Select(MagicSchools).where(MagicSchools.guild_id == guild_id,
			                                                 func.lower(MagicSchools.name) == (name or "").lower()))

	# ============================================================
	def school_by_review_message(self, message_id: int) -> MagicSchools | None :
		with self.createsession() as session :
			return session.scalar(Select(MagicSchools).where(MagicSchools.review_message_id == message_id))

	# ============================================================
	def add_school(self, guild_id: int, name: str, **fields) -> MagicSchools | None :
		if self.find_school(guild_id, name) is not None :
			return None
		with self.createsession() as session :
			record = MagicSchools(guild_id=guild_id, name=name,
			                      **{key : value for key, value in fields.items() if key in SCHOOL_FIELDS and key != "name"})
			session.add(record)
			self.commit(session)
			return record if record.id is not None else None

	# ============================================================
	def update_school(self, school_id: int, **fields) -> MagicSchools | None :
		with self.createsession() as session :
			record = session.scalar(Select(MagicSchools).where(MagicSchools.id == school_id))
			if record is None :
				return None
			for key, value in fields.items() :
				if key in SCHOOL_FIELDS :
					setattr(record, key, value)
			self.commit(session)
			return record

	# ============================================================
	def delete_school(self, school_id: int) -> bool :
		with self.createsession() as session :
			record = session.scalar(Select(MagicSchools).where(MagicSchools.id == school_id))
			if record is None :
				return False
			session.delete(record)
			self.commit(session)
			return True
