from sqlalchemy import Select, func, update

from database.database import ProxyMessages
from database.transactions.DatabaseTransactions import DatabaseTransactions


class ProxyTransactions(DatabaseTransactions) :
	"""The log of messages posted as characters."""

	# ============================================================
	def log(self, message_ids: list[int], character_id: int, uid: int, guild_id: int, channel_id: int, length: int,
	        counted: bool, xp: int, currency: int) -> None :
		"""Logs one post. The first message carries the length and the rewards; the others only point at it."""
		first = message_ids[0]
		with self.createsession() as session :
			for message_id in message_ids :
				is_first = message_id == first
				session.add(ProxyMessages(message_id=message_id, first_message_id=first, character_id=character_id,
				                          uid=uid, guild_id=guild_id, channel_id=channel_id,
				                          length=length if is_first else 0, counted=counted and is_first,
				                          xp_awarded=xp if is_first else 0,
				                          currency_awarded=currency if is_first else 0, deleted=False))
			self.commit(session)

	# ============================================================
	def get(self, message_id: int) -> ProxyMessages | None :
		with self.createsession() as session :
			return session.scalar(Select(ProxyMessages).where(ProxyMessages.message_id == message_id))

	# ============================================================
	def get_post(self, message_id: int) -> list[ProxyMessages] :
		"""Every message of the post the given message belongs to, in the order they were sent."""
		entry = self.get(message_id)
		if entry is None :
			return []
		with self.createsession() as session :
			return list(session.scalars(Select(ProxyMessages)
			                            .where(ProxyMessages.first_message_id == entry.first_message_id)
			                            .order_by(ProxyMessages.message_id)).all())

	# ============================================================
	def mark_deleted(self, message_ids: list[int]) -> int :
		"""Marks logged messages as deleted. Returns how many of them were in the log."""
		if not message_ids :
			return 0
		with self.createsession() as session :
			result = session.execute(update(ProxyMessages).where(ProxyMessages.message_id.in_(message_ids))
			                         .values(deleted=True))
			self.commit(session)
			return result.rowcount

	# ============================================================
	def adjust_length(self, first_message_id: int, change: int) -> None :
		"""Changes a post's stored length after one of its messages was edited."""
		with self.createsession() as session :
			session.execute(update(ProxyMessages).where(ProxyMessages.message_id == first_message_id)
			                .values(length=func.greatest(ProxyMessages.length + change, 0)))
			self.commit(session)

	# ============================================================
	def counted_lengths(self, character_id: int) -> list[int] :
		"""The length of every post by the character that earned XP and was not deleted."""
		with self.createsession() as session :
			return list(session.scalars(
				Select(ProxyMessages.length).where(ProxyMessages.character_id == character_id,
				                                   ProxyMessages.counted.is_(True),
				                                   ProxyMessages.deleted.is_(False))).all())

	# ============================================================
	def counted_lengths_by_user(self, guild_id: int) -> dict[int, list[int]] :
		"""{uid: [length of each post that earned XP and was not deleted]} for a guild, for recounting user XP."""
		with self.createsession() as session :
			rows = session.execute(
				Select(ProxyMessages.uid, ProxyMessages.length).where(ProxyMessages.guild_id == guild_id,
				                                                      ProxyMessages.counted.is_(True),
				                                                      ProxyMessages.deleted.is_(False))).all()
		lengths = {}
		for uid, length in rows :
			lengths.setdefault(uid, []).append(length)
		return lengths

	# ============================================================
	def count(self, character_id: int) -> int :
		with self.createsession() as session :
			return session.scalar(Select(func.count(ProxyMessages.message_id)).where(
				ProxyMessages.character_id == character_id,
			                                                 ProxyMessages.first_message_id == ProxyMessages.message_id,
			                                                 ProxyMessages.deleted.is_(False))) or 0
