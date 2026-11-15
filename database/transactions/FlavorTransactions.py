from datetime import datetime

from sqlalchemy import Select, func, or_

from database.database import OmenDraws, RumorHeard, RumorMarks, Rumors
from database.transactions.DatabaseTransactions import DatabaseTransactions

LISTEN = "listen"
BLOCK = "block"


class FlavorTransactions(DatabaseTransactions) :
	"""Rumors, who heard them, rumor listens and blocks, and omen draws."""

	# == rumors ==

	# ============================================================
	def add_rumor(self, guild_id: int, author_uid: int, text: str, **fields) -> Rumors | None :
		with self.createsession() as session :
			record = Rumors(guild_id=guild_id, author_uid=author_uid, text=text,
			                **{key : value for key, value in fields.items() if hasattr(Rumors, key)})
			session.add(record)
			self.commit(session)
			return record if record.id is not None else None

	# ============================================================
	def rumor(self, rumor_id: int | None) -> Rumors | None :
		if rumor_id is None :
			return None
		with self.createsession() as session :
			return session.scalar(Select(Rumors).where(Rumors.id == rumor_id))

	# ============================================================
	def update_rumor(self, rumor_id: int, **fields) -> Rumors | None :
		with self.createsession() as session :
			record = session.scalar(Select(Rumors).where(Rumors.id == rumor_id))
			if record is None :
				return None
			for key, value in fields.items() :
				if hasattr(Rumors, key) and key != "id" :
					setattr(record, key, value)
			self.commit(session)
			return record

	# ============================================================
	def live(self, guild_id: int, now: datetime) -> list[Rumors] :
		"""Rumors that haven't faded (pinned ones never do), newest first."""
		with self.createsession() as session :
			return list(session.scalars(Select(Rumors).where(Rumors.guild_id == guild_id, or_(
				Rumors.pinned.is_(True), Rumors.expires_at.is_(None), Rumors.expires_at > now))
			                            .order_by(Rumors.id.desc())).all())

	# ============================================================
	def heard_by(self, character_id: int) -> set[int] :
		with self.createsession() as session :
			return set(session.scalars(Select(RumorHeard.rumor_id).where(RumorHeard.character_id == character_id)).all())

	# ============================================================
	def hear(self, rumor_id: int, character_id: int) -> Rumors | None :
		"""Records that a character heard a rumor; returns the rumor with its new count."""
		with self.createsession() as session :
			session.add(RumorHeard(rumor_id=rumor_id, character_id=character_id))
			record = session.scalar(Select(Rumors).where(Rumors.id == rumor_id))
			if record is not None :
				record.heard = (record.heard or 0) + 1
			self.commit(session)
			return record

	# == listens and blocks ==

	# ============================================================
	def listened(self, character_id: int, day: str) -> bool :
		with self.createsession() as session :
			return session.scalar(Select(func.count(RumorMarks.id)).where(RumorMarks.kind == LISTEN,
			                                                              RumorMarks.character_id == character_id,
			                                                              RumorMarks.day == day)) > 0

	# ============================================================
	def mark_listen(self, guild_id: int, character_id: int, day: str) -> None :
		with self.createsession() as session :
			session.add(RumorMarks(guild_id=guild_id, kind=LISTEN, character_id=character_id, day=day))
			self.commit(session)

	# ============================================================
	def blocked(self, guild_id: int, uid: int) -> bool :
		with self.createsession() as session :
			return session.scalar(Select(func.count(RumorMarks.id)).where(RumorMarks.guild_id == guild_id,
			                                                              RumorMarks.kind == BLOCK,
			                                                              RumorMarks.uid == uid)) > 0

	# ============================================================
	def set_blocked(self, guild_id: int, uid: int, blocked: bool) -> None :
		with self.createsession() as session :
			marks = list(session.scalars(Select(RumorMarks).where(RumorMarks.guild_id == guild_id,
			                                                      RumorMarks.kind == BLOCK,
			                                                      RumorMarks.uid == uid)).all())
			if blocked and not marks :
				session.add(RumorMarks(guild_id=guild_id, kind=BLOCK, uid=uid))
			if not blocked :
				for mark in marks :
					session.delete(mark)
			self.commit(session)

	# == omens ==

	# ============================================================
	def draws(self, character_id: int, deck: str) -> list[OmenDraws] :
		with self.createsession() as session :
			return list(session.scalars(Select(OmenDraws).where(OmenDraws.character_id == character_id,
			                                                    OmenDraws.deck == deck)
			                            .order_by(OmenDraws.id)).all())

	# ============================================================
	def add_draw(self, character_id: int, deck: str, card: str, cycle: int, reader_uid: int | None) -> None :
		with self.createsession() as session :
			session.add(OmenDraws(character_id=character_id, deck=deck, card=card[:100], cycle=cycle,
			                      reader_uid=reader_uid))
			self.commit(session)
