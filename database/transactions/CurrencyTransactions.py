from datetime import datetime

from sqlalchemy import Select, case, func

from database.database import CurrencyTransactions as CurrencyRows
from database.transactions.DatabaseTransactions import DatabaseTransactions

START = "start"
ROLEPLAY = "roleplay"
BUY = "buy"
SELL = "sell"
GM_GIVE = "gm_give"
GM_TAKE = "gm_take"


class CurrencyTransactions(DatabaseTransactions) :
	"""The ledger of every change to a character's currency."""

	# ============================================================
	def log(self, character_id: int, guild_id: int, amount: int, reason: str, actor_uid: int | None = None,
	        note: str | None = None) -> CurrencyRows | None :
		with self.createsession() as session :
			row = CurrencyRows(character_id=character_id, guild_id=guild_id, amount=amount, reason=reason,
			                   actor_uid=actor_uid, note=note)
			session.add(row)
			self.commit(session)
			return row

	# ============================================================
	def get_all(self, character_id: int, limit: int = 50) -> list[CurrencyRows] :
		"""The character's most recent changes, newest first."""
		with self.createsession() as session :
			return list(session.scalars(Select(CurrencyRows).where(CurrencyRows.character_id == character_id)
			                            .order_by(CurrencyRows.id.desc()).limit(limit)).all())

	# ============================================================
	def totals(self, guild_id: int, since: datetime) -> list[tuple[str, int, int]] :
		"""Every reason's gains and losses on the server since then: (reason, amount gained or lost, changes),
		gains and losses of one reason apart, biggest first."""
		with self.createsession() as session :
			gained = case((CurrencyRows.amount > 0, "in"), else_="out")
			rows = session.execute(Select(CurrencyRows.reason, gained, func.sum(CurrencyRows.amount),
			                              func.count(CurrencyRows.id))
			                       .where(CurrencyRows.guild_id == guild_id, CurrencyRows.created_at >= since,
			                              CurrencyRows.amount != 0)
			                       .group_by(CurrencyRows.reason, gained)).all()
			return sorted(((reason, int(total), int(count)) for reason, _, total, count in rows),
			              key=lambda row : -abs(row[1]))

	# ============================================================
	def earners(self, guild_id: int, since: datetime, limit: int = 5) -> list[tuple[int, int]] :
		"""The characters that gained the most since then (gains only): (character id, amount)."""
		with self.createsession() as session :
			total = func.sum(CurrencyRows.amount)
			rows = session.execute(Select(CurrencyRows.character_id, total)
			                       .where(CurrencyRows.guild_id == guild_id, CurrencyRows.created_at >= since,
			                              CurrencyRows.amount > 0)
			                       .group_by(CurrencyRows.character_id).order_by(total.desc()).limit(limit)).all()
			return [(int(character_id), int(amount)) for character_id, amount in rows]
