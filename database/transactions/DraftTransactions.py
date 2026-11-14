from sqlalchemy import Select, delete
from sqlalchemy.orm.attributes import flag_modified

from database.database import Drafts
from database.transactions.DatabaseTransactions import DatabaseTransactions


class DraftTransactions(DatabaseTransactions) :
	"""The saved state of DM interviews. A user has at most one draft at a time."""

	# ============================================================
	def get(self, uid: int) -> Drafts | None :
		with self.createsession() as session :
			return session.scalar(Select(Drafts).where(Drafts.uid == uid))

	# ============================================================
	def create(self, uid: int, guild_id: int, kind: str, step: str, target_id: int | None = None,
	           answers: dict | None = None, species_id: int | None = None) -> Drafts | None :
		"""Starts a draft; returns None when the user already has one. target_id is the character being edited,
		species_id the species being edited."""
		if self.get(uid) is not None :
			return None
		with self.createsession() as session :
			draft = Drafts(uid=uid, guild_id=guild_id, kind=kind, step=step, target_id=target_id,
			               species_id=species_id, answers=answers or {}, rerolls=0)
			session.add(draft)
			self.commit(session)
			return draft

	# ============================================================
	def save(self, draft: Drafts) -> Drafts :
		"""Writes the draft's step, answers and rolls back to the database."""
		with self.createsession() as session :
			stored = session.scalar(Select(Drafts).where(Drafts.id == draft.id))
			if stored is None :
				return draft
			stored.step = draft.step
			stored.answers = dict(draft.answers or {})
			stored.rolled_values = list(draft.rolled_values) if draft.rolled_values is not None else None
			stored.rerolls = draft.rerolls
			# JSON columns only notice a new object, not a change inside one.
			flag_modified(stored, "answers")
			flag_modified(stored, "rolled_values")
			self.commit(session)
			return stored

	# ============================================================
	def delete(self, uid: int) -> bool :
		with self.createsession() as session :
			result = session.execute(delete(Drafts).where(Drafts.uid == uid))
			self.commit(session)
			return result.rowcount > 0
