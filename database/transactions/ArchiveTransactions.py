from sqlalchemy import Select, delete

from database.database import ArchivedChannels
from database.transactions.DatabaseTransactions import DatabaseTransactions


class ArchiveTransactions(DatabaseTransactions) :
	"""Records where archived channels came from, so they can be restored."""

	# ============================================================
	def add(self, guild_id: int, channel_id: int, channel_name: str, category_name: str | None,
	        everyone_view: bool | None) -> ArchivedChannels :
		"""Records an archived channel; a channel archived again keeps its first (true) origin."""
		with self.createsession() as session :
			existing = session.scalar(Select(ArchivedChannels).where(ArchivedChannels.channel_id == channel_id))
			if existing is not None :
				return existing
			record = ArchivedChannels(guild_id=guild_id, channel_id=channel_id, channel_name=channel_name,
			                          category_name=category_name, everyone_view=everyone_view)
			session.add(record)
			self.commit(session)
			return record

	# ============================================================
	def get(self, channel_id: int) -> ArchivedChannels | None :
		with self.createsession() as session :
			return session.scalar(Select(ArchivedChannels).where(ArchivedChannels.channel_id == channel_id))

	# ============================================================
	def get_all(self, guild_id: int) -> list[ArchivedChannels] :
		with self.createsession() as session :
			return list(session.scalars(Select(ArchivedChannels).where(ArchivedChannels.guild_id == guild_id)).all())

	# ============================================================
	def remove(self, channel_id: int) -> bool :
		with self.createsession() as session :
			result = session.execute(delete(ArchivedChannels).where(ArchivedChannels.channel_id == channel_id))
			self.commit(session)
			return result.rowcount > 0
