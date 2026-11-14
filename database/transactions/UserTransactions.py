import logging

from sqlalchemy import Select, delete

from database.database import Experience, Users
from database.transactions.DatabaseTransactions import DatabaseTransactions


class UserTransactions(DatabaseTransactions) :
	"""Users are global (one row per Discord user); their progression is stored per guild in Experience."""

	# ============================================================
	def get(self, uid: int, guild_id: int) -> Experience :
		"""Returns the user's progression in the guild, registering the user first if needed."""
		with self.createsession() as session :
			record = session.scalar(Select(Experience).where(Experience.uid == uid, Experience.guildid == guild_id))
			if record is not None :
				return record
		return self.add(uid, guild_id)

	# ============================================================
	def ensure_global(self, uid: int) -> None :
		"""Registers the user in the global users table only, for data that is not tied to a guild."""
		with self.createsession() as session :
			if session.scalar(Select(Users).where(Users.uid == uid)) is None :
				session.add(Users(uid=uid))
				self.commit(session)

	# ============================================================
	def add(self, uid: int, guild_id: int) -> Experience :
		"""Registers the user globally and in the guild; existing rows are left alone."""
		with self.createsession() as session :
			if session.scalar(Select(Users).where(Users.uid == uid)) is None :
				session.add(Users(uid=uid))
				# Push the user row first, experience references it.
				session.flush()
			record = session.scalar(Select(Experience).where(Experience.uid == uid, Experience.guildid == guild_id))
			if record is None :
				record = Experience(uid=uid, guildid=guild_id, xp=0, currency=0, messages=0)
				session.add(record)
			self.commit(session)
			return record

	# ============================================================
	def delete(self, uid: int, guild_id: int) -> bool :
		"""Removes the user's progression in one guild. The global user row is kept."""
		with self.createsession() as session :
			result = session.execute(delete(Experience).where(Experience.uid == uid, Experience.guildid == guild_id))
			self.commit(session)
			return result.rowcount > 0

	# ============================================================
	def sync_guild(self, guild_id: int, uids: list[int]) -> int :
		"""Registers every uid that has no progression in the guild yet, in a single session.

		@return: the number of users that were added.
		"""
		uids = list(dict.fromkeys(uids))
		if not uids :
			return 0
		with self.createsession() as session :
			known_users = set(session.scalars(Select(Users.uid).where(Users.uid.in_(uids))).all())
			known_experience = set(session.scalars(
				Select(Experience.uid).where(Experience.guildid == guild_id, Experience.uid.in_(uids))).all())
			missing_users = [uid for uid in uids if uid not in known_users]
			session.add_all([Users(uid=uid) for uid in missing_users])
			session.flush()
			missing_experience = [uid for uid in uids if uid not in known_experience]
			session.add_all(
				[Experience(uid=uid, guildid=guild_id, xp=0, currency=0, messages=0) for uid in missing_experience])
			self.commit(session)
		if missing_experience :
			logging.info(f"Registered {len(missing_experience)} users in {guild_id}")
		return len(missing_experience)
