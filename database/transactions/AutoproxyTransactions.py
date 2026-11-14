from sqlalchemy import Select, delete

from database.database import Autoproxy
from database.transactions.DatabaseTransactions import DatabaseTransactions


class AutoproxyTransactions(DatabaseTransactions) :
	"""Channels where a member's messages are posted as a character without a prefix or suffix."""

	# ============================================================
	def get(self, uid: int, channel_ids: list[int]) -> int | None :
		"""The character set for the first of the channels that has one (a thread before its parent channel)."""
		if not channel_ids :
			return None
		with self.createsession() as session :
			rows = {row.channel_id : row.character_id for row in session.scalars(
				Select(Autoproxy).where(Autoproxy.uid == uid, Autoproxy.channel_id.in_(channel_ids)))}
		return next((rows[channel_id] for channel_id in channel_ids if channel_id in rows), None)

	# ============================================================
	def set(self, uid: int, guild_id: int, channel_id: int, character_id: int) -> None :
		with self.createsession() as session :
			row = session.scalar(Select(Autoproxy).where(Autoproxy.uid == uid, Autoproxy.channel_id == channel_id))
			if row is None :
				session.add(Autoproxy(uid=uid, guild_id=guild_id, channel_id=channel_id, character_id=character_id))
			else :
				row.character_id = character_id
			self.commit(session)

	# ============================================================
	def clear(self, uid: int, channel_id: int) -> bool :
		with self.createsession() as session :
			result = session.execute(delete(Autoproxy).where(Autoproxy.uid == uid, Autoproxy.channel_id == channel_id))
			self.commit(session)
			return result.rowcount > 0

	# ============================================================
	def clear_character(self, character_id: int) -> int :
		"""Turns autoproxy off everywhere for a character, for example when it stops being approved."""
		with self.createsession() as session :
			result = session.execute(delete(Autoproxy).where(Autoproxy.character_id == character_id))
			self.commit(session)
			return result.rowcount
