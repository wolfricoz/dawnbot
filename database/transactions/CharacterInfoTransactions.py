from sqlalchemy import Select

from database.database import CharacterInfo
from database.transactions.DatabaseTransactions import DatabaseTransactions


class CharacterInfoTransactions(DatabaseTransactions) :
	"""Free-form fields on a character sheet. Keys are unique per character; positions start at 1."""

	# ============================================================
	def get_all(self, character_id: int) -> list[CharacterInfo] :
		"""All fields of the character, in display order."""
		with self.createsession() as session :
			return list(session.scalars(Select(CharacterInfo).where(CharacterInfo.character_id == character_id)
			                            .order_by(CharacterInfo.position, CharacterInfo.id)).all())

	# ============================================================
	def add(self, character_id: int, key: str, value: str) -> CharacterInfo | None :
		"""Adds a field at the end; returns None when the key already exists."""
		existing = self.get_all(character_id)
		if any(info.key.lower() == key.lower() for info in existing) :
			return None
		with self.createsession() as session :
			info = CharacterInfo(character_id=character_id, key=key, value=value, position=len(existing) + 1)
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
	def remove(self, character_id: int, key: str) -> bool :
		with self.createsession() as session :
			info = self._find(session, character_id, key)
			if info is None :
				return False
			session.delete(info)
			self.commit(session)
		self._renumber(character_id, [info.key for info in self.get_all(character_id)])
		return True

	# ============================================================
	def move(self, character_id: int, key: str, position: int) -> bool :
		"""Moves a field to a position (clamped to the valid range); the other fields shift around it."""
		keys = [info.key for info in self.get_all(character_id)]
		match = next((k for k in keys if k.lower() == key.lower()), None)
		if match is None :
			return False
		keys.remove(match)
		position = max(1, min(position, len(keys) + 1))
		keys.insert(position - 1, match)
		self._renumber(character_id, keys)
		return True

	# ============================================================
	def _renumber(self, character_id: int, ordered_keys: list[str]) :
		with self.createsession() as session :
			for info in session.scalars(Select(CharacterInfo).where(CharacterInfo.character_id == character_id)) :
				info.position = ordered_keys.index(info.key) + 1
			self.commit(session)

	# ============================================================
	@staticmethod
	def _find(session, character_id: int, key: str) -> CharacterInfo | None :
		for info in session.scalars(Select(CharacterInfo).where(CharacterInfo.character_id == character_id)) :
			if info.key.lower() == key.lower() :
				return info
		return None
