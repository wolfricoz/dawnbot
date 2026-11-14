from sqlalchemy import Select

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
