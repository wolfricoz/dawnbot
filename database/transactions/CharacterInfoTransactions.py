from sqlalchemy import Select, delete

from database.database import CharacterInfo, SheetFields
from database.transactions.DatabaseTransactions import DatabaseTransactions


# Sheet answers belong to one of the server's sheet questions (sheet_field_id) and are shown in the order of the sheet.
# Extra fields are added by the player, have no sheet_field_id, and are shown after the answers in the order of their
# position, starting at 1. Keys are unique per character.
class CharacterInfoTransactions(DatabaseTransactions) :
	"""The fields on a character sheet: sheet answers and the player's extra fields."""

	# ============================================================
	def get_all(self, character_id: int) -> list[CharacterInfo] :
		"""All fields of the character in display order: sheet answers in sheet order, then extra fields."""
		with self.createsession() as session :
			rows = session.execute(
				Select(CharacterInfo, SheetFields.position)
				.outerjoin(SheetFields, SheetFields.id == CharacterInfo.sheet_field_id)
				.where(CharacterInfo.character_id == character_id)).all()
		answers = sorted((row for row in rows if row[0].sheet_field_id is not None),
		                 key=lambda row : (row[1] or 0, row[0].id))
		extras = sorted((row for row in rows if row[0].sheet_field_id is None),
		                key=lambda row : (row[0].position, row[0].id))
		return [row[0] for row in answers + extras]

	# ============================================================
	def get_extras(self, character_id: int) -> list[CharacterInfo] :
		"""The fields the player added, in display order."""
		return [info for info in self.get_all(character_id) if info.sheet_field_id is None]

	# ============================================================
	def get_answers(self, character_id: int) -> dict[int, str] :
		"""The character's sheet answers as {sheet field id: value}."""
		return {info.sheet_field_id : info.value for info in self.get_all(character_id)
		        if info.sheet_field_id is not None}

	# == sheet answers ==

	# ============================================================
	def set_answer(self, character_id: int, field_id: int, label: str, value: str | None) -> None :
		"""Stores the answer to a sheet question; None or an empty value removes it.

		An extra field with the same name as the question becomes the answer, so the key stays unique.
		"""
		with self.createsession() as session :
			rows = list(session.scalars(Select(CharacterInfo).where(CharacterInfo.character_id == character_id)))
			info = next((row for row in rows if row.sheet_field_id == field_id), None)
			if info is None :
				info = next((row for row in rows if row.key.lower() == label.lower()), None)
			if value is None or value == "" :
				if info is not None :
					session.delete(info)
				self.commit(session)
				return
			if info is None :
				info = CharacterInfo(character_id=character_id, key=label, value=value, position=0)
				session.add(info)
			info.sheet_field_id = field_id
			info.key = label
			info.value = value
			info.position = 0
			self.commit(session)
		self._renumber(character_id, [extra.key for extra in self.get_extras(character_id)])

	# == extra fields ==

	# ============================================================
	def add(self, character_id: int, key: str, value: str) -> CharacterInfo | None :
		"""Adds an extra field at the end; returns None when the character already has a field with that key."""
		existing = self.get_all(character_id)
		if any(info.key.lower() == key.lower() for info in existing) :
			return None
		extras = [info for info in existing if info.sheet_field_id is None]
		with self.createsession() as session :
			info = CharacterInfo(character_id=character_id, key=key, value=value, position=len(extras) + 1)
			session.add(info)
			self.commit(session)
			return info

	# ============================================================
	def edit(self, character_id: int, key: str, value: str) -> CharacterInfo | None :
		with self.createsession() as session :
			info = self._find(session, character_id, key)
			if info is None :
				return None
			info.value = value
			self.commit(session)
			return info

	# ============================================================
	def rename(self, character_id: int, key: str, new_key: str) -> CharacterInfo | None :
		"""Renames an extra field; a name another field already has gets a number added (`Magics (old) 2`)."""
		with self.createsession() as session :
			info = self._find(session, character_id, key)
			if info is None :
				return None
			taken = {row.key.lower() for row in session.scalars(
				Select(CharacterInfo).where(CharacterInfo.character_id == character_id)) if row.id != info.id}
			candidate, number = new_key, 2
			while candidate.lower() in taken :
				candidate, number = f"{new_key} {number}", number + 1
			info.key = candidate
			self.commit(session)
			return info

	# ============================================================
	def remove(self, character_id: int, key: str) -> bool :
		with self.createsession() as session :
			info = self._find(session, character_id, key)
			if info is None :
				return False
			session.delete(info)
			self.commit(session)
		self._renumber(character_id, [info.key for info in self.get_extras(character_id)])
		return True

	# ============================================================
	def move(self, character_id: int, key: str, position: int) -> bool :
		"""Moves an extra field to a position (clamped to the valid range); the other extra fields shift around it."""
		keys = [info.key for info in self.get_extras(character_id)]
		match = next((k for k in keys if k.lower() == key.lower()), None)
		if match is None :
			return False
		keys.remove(match)
		position = max(1, min(position, len(keys) + 1))
		keys.insert(position - 1, match)
		self._renumber(character_id, keys)
		return True

	# ============================================================
	def replace_extras(self, character_id: int, extras: list[dict]) -> None :
		"""Replaces every extra field with the given [{"key", "value"}] list, in that order."""
		with self.createsession() as session :
			session.execute(delete(CharacterInfo).where(CharacterInfo.character_id == character_id,
			                                            CharacterInfo.sheet_field_id.is_(None)))
			for position, extra in enumerate(extras, start=1) :
				session.add(CharacterInfo(character_id=character_id, key=extra["key"], value=extra["value"],
				                          position=position))
			self.commit(session)

	# ============================================================
	def _renumber(self, character_id: int, ordered_keys: list[str]) :
		with self.createsession() as session :
			for info in session.scalars(Select(CharacterInfo).where(CharacterInfo.character_id == character_id,
			                                                        CharacterInfo.sheet_field_id.is_(None))) :
				info.position = ordered_keys.index(info.key) + 1
			self.commit(session)

	# ============================================================
	@staticmethod
	def _find(session, character_id: int, key: str) -> CharacterInfo | None :
		"""An extra field by its key; sheet answers are changed through /character edit."""
		for info in session.scalars(Select(CharacterInfo).where(CharacterInfo.character_id == character_id,
		                                                        CharacterInfo.sheet_field_id.is_(None))) :
			if info.key.lower() == key.lower() :
				return info
		return None
