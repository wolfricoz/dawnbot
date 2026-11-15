from datetime import datetime

from sqlalchemy import Select, func

from database.database import CharacterLanguages, Languages, Letters, ProxyLanguages
from database.transactions.DatabaseTransactions import DatabaseTransactions


class LanguageTransactions(DatabaseTransactions) :
	"""Languages, who knows them, the originals of posts made in them, and letters."""

	# == languages ==

	# ============================================================
	def get_all(self, guild_id: int) -> list[Languages] :
		with self.createsession() as session :
			return list(session.scalars(Select(Languages).where(Languages.guild_id == guild_id)
			                            .order_by(Languages.common.desc(), func.lower(Languages.name))).all())

	# ============================================================
	def get(self, language_id: int | None) -> Languages | None :
		if language_id is None :
			return None
		with self.createsession() as session :
			return session.scalar(Select(Languages).where(Languages.id == language_id))

	# ============================================================
	def find(self, guild_id: int, name: str) -> Languages | None :
		with self.createsession() as session :
			return session.scalar(Select(Languages).where(Languages.guild_id == guild_id,
			                                              func.lower(Languages.name) == (name or "").strip().lower()))

	# ============================================================
	def common(self, guild_id: int) -> Languages | None :
		with self.createsession() as session :
			return session.scalar(Select(Languages).where(Languages.guild_id == guild_id, Languages.common.is_(True)))

	# ============================================================
	def add(self, guild_id: int, name: str, **fields) -> Languages | None :
		if self.find(guild_id, name) is not None :
			return None
		with self.createsession() as session :
			record = Languages(guild_id=guild_id, name=name,
			                   **{key : value for key, value in fields.items() if hasattr(Languages, key)})
			session.add(record)
			self.commit(session)
			return record if record.id is not None else None

	# ============================================================
	def update(self, language_id: int, **fields) -> Languages | None :
		with self.createsession() as session :
			record = session.scalar(Select(Languages).where(Languages.id == language_id))
			if record is None :
				return None
			for key, value in fields.items() :
				if hasattr(Languages, key) and key != "id" :
					setattr(record, key, value)
			self.commit(session)
			return record

	# ============================================================
	def delete(self, language_id: int) -> bool :
		with self.createsession() as session :
			record = session.scalar(Select(Languages).where(Languages.id == language_id))
			if record is None :
				return False
			session.delete(record)
			self.commit(session)
			return True

	# == who knows what ==

	# ============================================================
	def known(self, character_id: int) -> list[CharacterLanguages] :
		with self.createsession() as session :
			return list(session.scalars(Select(CharacterLanguages)
			                            .where(CharacterLanguages.character_id == character_id)).all())

	# ============================================================
	def teach(self, character_id: int, language_id: int, fluency: str, source: str) -> CharacterLanguages | None :
		"""Adds a language to a character, or changes how well it knows it."""
		with self.createsession() as session :
			record = session.scalar(Select(CharacterLanguages).where(CharacterLanguages.character_id == character_id,
			                                                         CharacterLanguages.language_id == language_id))
			if record is None :
				record = CharacterLanguages(character_id=character_id, language_id=language_id, fluency=fluency,
				                            source=source)
				session.add(record)
			else :
				record.fluency = fluency
			self.commit(session)
			return record

	# ============================================================
	def forget(self, character_id: int, language_id: int) -> bool :
		with self.createsession() as session :
			record = session.scalar(Select(CharacterLanguages).where(CharacterLanguages.character_id == character_id,
			                                                         CharacterLanguages.language_id == language_id))
			if record is None :
				return False
			session.delete(record)
			self.commit(session)
			return True

	# == posts ==

	# ============================================================
	def save_post(self, first_message_id: int, character_id: int | None, segments: list[dict]) -> None :
		with self.createsession() as session :
			record = session.scalar(Select(ProxyLanguages).where(ProxyLanguages.first_message_id == first_message_id))
			if record is None :
				session.add(ProxyLanguages(first_message_id=first_message_id, character_id=character_id,
				                           segments=segments))
			else :
				record.segments = segments
			self.commit(session)

	# ============================================================
	def post(self, first_message_id: int) -> ProxyLanguages | None :
		with self.createsession() as session :
			return session.scalar(Select(ProxyLanguages).where(ProxyLanguages.first_message_id == first_message_id))

	# == letters ==

	# ============================================================
	def add_letter(self, guild_id: int, **fields) -> Letters | None :
		with self.createsession() as session :
			record = Letters(guild_id=guild_id, **{key : value for key, value in fields.items() if hasattr(Letters, key)})
			session.add(record)
			self.commit(session)
			return record if record.id is not None else None

	# ============================================================
	def letter(self, letter_id: int | None) -> Letters | None :
		if letter_id is None :
			return None
		with self.createsession() as session :
			return session.scalar(Select(Letters).where(Letters.id == letter_id))

	# ============================================================
	def update_letter(self, letter_id: int, **fields) -> Letters | None :
		with self.createsession() as session :
			record = session.scalar(Select(Letters).where(Letters.id == letter_id))
			if record is None :
				return None
			for key, value in fields.items() :
				if hasattr(Letters, key) and key != "id" :
					setattr(record, key, value)
			self.commit(session)
			return record

	# ============================================================
	def due_letters(self, now: datetime) -> list[Letters] :
		with self.createsession() as session :
			return list(session.scalars(Select(Letters).where(Letters.state == "in_transit", Letters.deliver_at <= now)
			                            .order_by(Letters.deliver_at)).all())

	# ============================================================
	def inbox(self, character_id: int, limit: int = 15) -> list[Letters] :
		with self.createsession() as session :
			return list(session.scalars(Select(Letters).where(Letters.to_character_id == character_id,
			                                                  Letters.state == "delivered")
			                            .order_by(Letters.id.desc()).limit(limit)).all())

	# ============================================================
	def in_transit(self, guild_id: int) -> list[Letters] :
		with self.createsession() as session :
			return list(session.scalars(Select(Letters).where(Letters.guild_id == guild_id,
			                                                  Letters.state.in_(("in_transit", "held")))
			                            .order_by(Letters.deliver_at)).all())
