from sqlalchemy import Select, delete as delete_rows, func

from database.database import RollTableEntries, RollTables, TableRolls
from database.transactions.DatabaseTransactions import DatabaseTransactions

FIELDS = ["name", "description", "dice", "luck", "kind", "visibility", "pack", "creator_uid"]
ENTRY_FIELDS = ["low", "high", "weight", "text", "actions"]
ROLL_FIELDS = ["character_id", "channel_id", "natural", "rolled", "text", "actions", "granted_to", "fight_id",
               "secret"]


class RollTableTransactions(DatabaseTransactions) :
	"""A server's roll tables, their entries and the rolls made on them. Names are unique per server, without case."""

	# ============================================================
	def get_all(self, guild_id: int, kind: str = "table") -> list[RollTables] :
		with self.createsession() as session :
			return list(session.scalars(Select(RollTables).where(RollTables.guild_id == guild_id,
			                                                     RollTables.kind == kind)
			                            .order_by(func.lower(RollTables.name))).all())

	# ============================================================
	def get(self, table_id: int | None) -> RollTables | None :
		if table_id is None :
			return None
		with self.createsession() as session :
			return session.scalar(Select(RollTables).where(RollTables.id == table_id))

	# ============================================================
	def find(self, guild_id: int, name: str) -> RollTables | None :
		with self.createsession() as session :
			return session.scalar(Select(RollTables).where(RollTables.guild_id == guild_id,
			                                               func.lower(RollTables.name) == (name or "").strip().lower()))

	# ============================================================
	def add(self, guild_id: int, name: str, entries: list[dict], **fields) -> RollTables | None :
		"""Adds a table with its entries ({"low", "high", "weight", "text", "actions"}). None when the name is
		taken."""
		if self.find(guild_id, name) is not None :
			return None
		with self.createsession() as session :
			record = RollTables(guild_id=guild_id, name=name,
			                    **{key : value for key, value in fields.items() if key in FIELDS and key != "name"})
			session.add(record)
			session.flush()
			self._add_entries(session, record.id, entries)
			self.commit(session)
			return record if record.id is not None else None

	# ============================================================
	def update(self, table_id: int, entries: list[dict] | None = None, **fields) -> RollTables | None :
		"""Changes a table; entries, when given, replace all of its entries."""
		with self.createsession() as session :
			record = session.scalar(Select(RollTables).where(RollTables.id == table_id))
			if record is None :
				return None
			for key, value in fields.items() :
				if key in FIELDS :
					setattr(record, key, value)
			if entries is not None :
				session.execute(delete_rows(RollTableEntries).where(RollTableEntries.table_id == table_id))
				self._add_entries(session, table_id, entries)
			self.commit(session)
			return record

	# ============================================================
	def delete(self, table_id: int) -> bool :
		with self.createsession() as session :
			record = session.scalar(Select(RollTables).where(RollTables.id == table_id))
			if record is None :
				return False
			session.delete(record)
			self.commit(session)
			return True

	# ============================================================
	def entries(self, table_id: int) -> list[RollTableEntries] :
		with self.createsession() as session :
			return list(session.scalars(Select(RollTableEntries).where(RollTableEntries.table_id == table_id)
			                            .order_by(RollTableEntries.position, RollTableEntries.id)).all())

	# ============================================================
	@staticmethod
	def _add_entries(session, table_id: int, entries: list[dict]) -> None :
		for position, entry in enumerate(entries) :
			record = RollTableEntries(table_id=table_id, position=position,
			                          **{key : value for key, value in entry.items() if key in ENTRY_FIELDS})
			record.actions = record.actions or []
			record.weight = record.weight or 1
			session.add(record)

	# == rolls ==

	# ============================================================
	def add_roll(self, guild_id: int, table: RollTables, uid: int, **fields) -> TableRolls | None :
		with self.createsession() as session :
			record = TableRolls(guild_id=guild_id, table_id=table.id, table_name=table.name, uid=uid,
			                    **{key : value for key, value in fields.items() if key in ROLL_FIELDS})
			record.actions = record.actions or []
			record.granted_to = record.granted_to or []
			record.secret = bool(record.secret)
			session.add(record)
			self.commit(session)
			return record if record.id is not None else None

	# ============================================================
	def get_roll(self, roll_id: int) -> TableRolls | None :
		with self.createsession() as session :
			return session.scalar(Select(TableRolls).where(TableRolls.id == roll_id))

	# ============================================================
	def update_roll(self, roll_id: int, **fields) -> TableRolls | None :
		with self.createsession() as session :
			record = session.scalar(Select(TableRolls).where(TableRolls.id == roll_id))
			if record is None :
				return None
			for key, value in fields.items() :
				if key in ROLL_FIELDS :
					setattr(record, key, value)
			self.commit(session)
			return record
