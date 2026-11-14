from sqlalchemy import Select, delete

from database.database import SheetFields
from database.transactions.DatabaseTransactions import DatabaseTransactions

# Columns add() and update() accept as keyword arguments.
FIELDS = ["section", "label", "help", "type", "required", "max_length", "min_value", "max_value", "choices"]


class SheetFieldTransactions(DatabaseTransactions) :
	"""The questions on a server's character sheet. Labels are unique per server; positions start at 1."""

	# ============================================================
	def get_all(self, guild_id: int) -> list[SheetFields] :
		"""The server's questions in the order they are asked."""
		with self.createsession() as session :
			return list(session.scalars(Select(SheetFields).where(SheetFields.guild_id == guild_id)
			                            .order_by(SheetFields.position, SheetFields.id)).all())

	# ============================================================
	def get(self, field_id: int) -> SheetFields | None :
		with self.createsession() as session :
			return session.scalar(Select(SheetFields).where(SheetFields.id == field_id))

	# ============================================================
	def find(self, guild_id: int, label: str) -> SheetFields | None :
		return next((field for field in self.get_all(guild_id) if field.label.lower() == label.lower()), None)

	# ============================================================
	def add(self, guild_id: int, label: str, position: int | None = None, **fields) -> SheetFields | None :
		"""Adds a question, at the end unless a position is given; returns None when the label is already used."""
		existing = self.get_all(guild_id)
		if any(field.label.lower() == label.lower() for field in existing) :
			return None
		with self.createsession() as session :
			field = SheetFields(guild_id=guild_id, label=label, position=len(existing) + 1,
			                    **{key : value for key, value in fields.items() if key in FIELDS})
			session.add(field)
			self.commit(session)
		if position is not None :
			self.move(guild_id, label, position)
			return self.get(field.id)
		return field

	# ============================================================
	def add_many(self, guild_id: int, fields: list[dict]) -> int :
		"""Adds several questions at the end, in one session. Returns how many were added."""
		start = len(self.get_all(guild_id))
		with self.createsession() as session :
			for offset, field in enumerate(fields, start=1) :
				session.add(SheetFields(guild_id=guild_id, position=start + offset,
				                        **{key : value for key, value in field.items() if key in FIELDS}))
			self.commit(session)
		return len(fields)

	# ============================================================
	def update(self, field_id: int, **fields) -> SheetFields | None :
		"""Sets the given fields. Unlike None, a missing keyword leaves a field unchanged."""
		with self.createsession() as session :
			field = session.scalar(Select(SheetFields).where(SheetFields.id == field_id))
			if field is None :
				return None
			for key, value in fields.items() :
				if key in FIELDS :
					setattr(field, key, value)
			self.commit(session)
			return field

	# ============================================================
	def remove(self, guild_id: int, label: str) -> bool :
		"""Removes a question. Answers characters already gave stay on their sheets as extra fields."""
		field = self.find(guild_id, label)
		if field is None :
			return False
		with self.createsession() as session :
			session.execute(delete(SheetFields).where(SheetFields.id == field.id))
			self.commit(session)
		self._renumber(guild_id, [f.id for f in self.get_all(guild_id)])
		return True

	# ============================================================
	def move(self, guild_id: int, label: str, position: int) -> bool :
		"""Moves a question to a position (clamped to the valid range); the other questions shift around it."""
		ids = [field.id for field in self.get_all(guild_id)]
		field = self.find(guild_id, label)
		if field is None :
			return False
		ids.remove(field.id)
		position = max(1, min(position, len(ids) + 1))
		ids.insert(position - 1, field.id)
		self._renumber(guild_id, ids)
		return True

	# ============================================================
	def clear(self, guild_id: int) -> None :
		with self.createsession() as session :
			session.execute(delete(SheetFields).where(SheetFields.guild_id == guild_id))
			self.commit(session)

	# ============================================================
	def _renumber(self, guild_id: int, ordered_ids: list[int]) :
		with self.createsession() as session :
			for field in session.scalars(Select(SheetFields).where(SheetFields.guild_id == guild_id)) :
				field.position = ordered_ids.index(field.id) + 1
			self.commit(session)
