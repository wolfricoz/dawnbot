from sqlalchemy import Select, func

from database.database import GearItems
from database.transactions.DatabaseTransactions import DatabaseTransactions

# Columns add() and update() accept as keyword arguments.
FIELDS = ["kind", "name", "description", "price", "requirements", "effect_met", "effect_unmet", "effect", "combat",
          "tag_ids", "forum_thread_id", "forum_message_id", "pack"]


class GearItemTransactions(DatabaseTransactions) :
	"""A server's gear catalog. Names are unique per server, compared without case."""

	# ============================================================
	def get_all(self, guild_id: int, kind: str | None = None) -> list[GearItems] :
		"""The catalog, weapons before armor, then by price and name."""
		with self.createsession() as session :
			query = Select(GearItems).where(GearItems.guild_id == guild_id)
			if kind is not None :
				query = query.where(GearItems.kind == kind)
			return list(session.scalars(query.order_by(GearItems.kind.desc(), GearItems.price,
			                                           func.lower(GearItems.name))).all())

	# ============================================================
	def get(self, item_id: int | None) -> GearItems | None :
		if item_id is None :
			return None
		with self.createsession() as session :
			return session.scalar(Select(GearItems).where(GearItems.id == item_id))

	# ============================================================
	def find(self, guild_id: int, name: str) -> GearItems | None :
		with self.createsession() as session :
			return session.scalar(Select(GearItems).where(GearItems.guild_id == guild_id,
			                                              func.lower(GearItems.name) == name.lower()))

	# ============================================================
	def get_by_thread(self, thread_id: int) -> GearItems | None :
		with self.createsession() as session :
			return session.scalar(Select(GearItems).where(GearItems.forum_thread_id == thread_id))

	# ============================================================
	def add(self, guild_id: int, kind: str, name: str, **fields) -> GearItems | None :
		"""Returns None when the catalog already has an item with that name, or it could not be saved."""
		if self.find(guild_id, name) is not None :
			return None
		with self.createsession() as session :
			item = GearItems(guild_id=guild_id, kind=kind, name=name,
			                 **{key : value for key, value in fields.items() if key in FIELDS})
			item.requirements = item.requirements or {}
			item.combat = item.combat or {}
			item.tag_ids = item.tag_ids or []
			item.price = item.price or 0
			session.add(item)
			self.commit(session)
			return item if item.id is not None else None

	# ============================================================
	def update(self, item_id: int, **fields) -> GearItems | None :
		"""Sets the given fields. Unlike None, a missing keyword leaves a field unchanged."""
		with self.createsession() as session :
			item = session.scalar(Select(GearItems).where(GearItems.id == item_id))
			if item is None :
				return None
			for key, value in fields.items() :
				if key in FIELDS :
					setattr(item, key, value)
			self.commit(session)
			return item

	# ============================================================
	def delete(self, item_id: int) -> bool :
		"""Removes an item from the catalog. Characters keep the copies they own, by name."""
		with self.createsession() as session :
			item = session.scalar(Select(GearItems).where(GearItems.id == item_id))
			if item is None :
				return False
			session.delete(item)
			self.commit(session)
			return True
