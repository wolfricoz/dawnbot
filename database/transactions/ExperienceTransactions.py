from sqlalchemy import update

from database.database import Experience
from database.transactions.DatabaseTransactions import DatabaseTransactions
from database.transactions.UserTransactions import UserTransactions


# Every write registers the user first, so members who joined after start-up are never silently skipped.
class ExperienceTransactions(DatabaseTransactions) :
	"""XP and message counts, per user per guild."""

	# ============================================================
	def get(self, uid: int, guild_id: int) -> Experience :
		return UserTransactions().get(uid, guild_id)

	# ============================================================
	def _update(self, uid: int, guild_id: int, **values) -> Experience :
		UserTransactions().get(uid, guild_id)
		with self.createsession() as session :
			session.execute(
				update(Experience).where(Experience.uid == uid, Experience.guildid == guild_id).values(**values))
			self.commit(session)
		return self.get(uid, guild_id)

	# == XP ==

	# ============================================================
	def add_xp(self, uid: int, guild_id: int, amount: int, count_message: bool = True) -> Experience :
		"""Adds XP; counts a message too unless count_message is False (manual grants)."""
		values = {"xp" : Experience.xp + amount}
		if count_message :
			values["messages"] = Experience.messages + 1
		return self._update(uid, guild_id, **values)

	# ============================================================
	def remove_xp(self, uid: int, guild_id: int, amount: int) -> Experience :
		return self._update(uid, guild_id, xp=Experience.xp - amount)

	# ============================================================
	def set_xp(self, uid: int, guild_id: int, amount: int) -> Experience :
		return self._update(uid, guild_id, xp=amount)
