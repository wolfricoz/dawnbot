from sqlalchemy import Select, delete

from database.database import TagRequirements
from database.transactions.DatabaseTransactions import DatabaseTransactions


class TagRuleTransactions(DatabaseTransactions) :
	"""What tags on forum posts ask of members. A tag has at most one rule of each kind."""

	# ============================================================
	def get_all(self, guild_id: int) -> list[TagRequirements] :
		with self.createsession() as session :
			return list(session.scalars(Select(TagRequirements).where(TagRequirements.guild_id == guild_id)
			                            .order_by(TagRequirements.forum_channel_id, TagRequirements.id)).all())

	# ============================================================
	def for_tags(self, tag_ids: list[int]) -> list[TagRequirements] :
		"""The rules of the given tags."""
		if not tag_ids :
			return []
		with self.createsession() as session :
			return list(session.scalars(Select(TagRequirements).where(TagRequirements.tag_id.in_(tag_ids))).all())

	# ============================================================
	def set(self, guild_id: int, forum_channel_id: int, tag_id: int, kind: str, value: int | None) -> TagRequirements :
		"""Adds a rule to a tag, or changes the value of its rule of that kind."""
		with self.createsession() as session :
			rule = session.scalar(Select(TagRequirements).where(TagRequirements.tag_id == tag_id,
			                                                    TagRequirements.kind == kind))
			if rule is None :
				rule = TagRequirements(guild_id=guild_id, forum_channel_id=forum_channel_id, tag_id=tag_id, kind=kind)
				session.add(rule)
			rule.value = value
			self.commit(session)
			return rule

	# ============================================================
	def remove(self, tag_id: int, kind: str | None = None) -> int :
		"""Removes a tag's rule of one kind, or all its rules. Returns how many were removed."""
		with self.createsession() as session :
			query = delete(TagRequirements).where(TagRequirements.tag_id == tag_id)
			if kind is not None :
				query = query.where(TagRequirements.kind == kind)
			result = session.execute(query)
			self.commit(session)
			return result.rowcount
