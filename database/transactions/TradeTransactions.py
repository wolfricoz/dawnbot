from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import Select

from database.database import CharacterGear, Characters, CurrencyTransactions as CurrencyRows, MarketListings, Trades
from database.transactions.DatabaseTransactions import DatabaseTransactions

OWNED = "owned"
LISTED = "listed"
TRADES_FIELDS = ["channel_id", "message_id", "offers", "accepted", "state", "finished_at"]
LISTING_FIELDS = ["thread_id", "message_id", "state", "buyer_character_id", "buyer_uid", "fee", "finished_at",
                  "expires_at"]


@dataclass
class Move :
	"""An item changing hands: it has to belong to giver and be in one of the statuses."""
	entry_id: int
	giver_id: int
	receiver_id: int
	statuses: tuple[str, ...] = (OWNED,)
	source: str = "traded"


@dataclass
class Payment :
	"""A currency change written to the ledger: a negative amount may not leave the character below 0."""
	character_id: int
	amount: int
	reason: str
	note: str | None = None
	actor_uid: int | None = None


@dataclass
class Transfer :
	moves: list[Move] = field(default_factory=list)
	payments: list[Payment] = field(default_factory=list)


class TradeTransactions(DatabaseTransactions) :
	"""Trades, market listings and the transfer that moves items and currency between characters at once."""

	# == transfers ==

	# ============================================================
	def transfer(self, transfer: Transfer, guild_id: int) -> str | None :
		"""Moves the items and makes the payments in one database transaction: all of it happens, or (with the reason
		returned) none of it. Items lose their slot and proficiency when they change hands."""
		with self.createsession() as session :
			problem = self._apply(session, transfer, guild_id)
			if problem :
				session.rollback()
				return problem
			self.commit(session)
			return None

	# ============================================================
	def buy_listing(self, listing_id: int, transfer: Transfer, buyer: Characters, fee: int) -> str | None :
		"""Sells an open listing: the transfer and the listing's end happen together, or not at all."""
		with self.createsession() as session :
			listing = session.scalar(Select(MarketListings).where(MarketListings.id == listing_id).with_for_update())
			if listing is None or listing.state != "open" :
				session.rollback()
				return "This listing isn't open any more."
			problem = self._apply(session, transfer, listing.guild_id)
			if problem :
				session.rollback()
				return problem
			listing.state = "sold"
			listing.buyer_character_id = buyer.id
			listing.buyer_uid = buyer.uid
			listing.fee = fee
			listing.finished_at = datetime.now(timezone.utc)
			self.commit(session)
			return None

	# ============================================================
	@staticmethod
	def _apply(session, transfer: Transfer, guild_id: int) -> str | None :
		character_ids = sorted({payment.character_id for payment in transfer.payments})
		characters = {character.id : character for character in session.scalars(
			Select(Characters).where(Characters.id.in_(character_ids)).order_by(Characters.id).with_for_update())}
		entry_ids = sorted({move.entry_id for move in transfer.moves})
		entries = {entry.id : entry for entry in session.scalars(
			Select(CharacterGear).where(CharacterGear.id.in_(entry_ids)).order_by(CharacterGear.id).with_for_update())}
		for move in transfer.moves :
			entry = entries.get(move.entry_id)
			if entry is None or entry.character_id != move.giver_id or entry.status not in move.statuses :
				return f"{entry.name if entry else 'An item'} is no longer available."
			if entry.equipped :
				return f"{entry.name} is equipped; it has to be put away first."
		balances = {character_id : character.currency for character_id, character in characters.items()}
		for payment in transfer.payments :
			if payment.character_id not in characters :
				return "A character in this deal no longer exists."
			balances[payment.character_id] += payment.amount
		short = [characters[character_id].name for character_id, balance in balances.items() if balance < 0]
		if short :
			return f"{short[0]} doesn't have enough currency any more."
		for move in transfer.moves :
			entry = entries[move.entry_id]
			entry.character_id = move.receiver_id
			entry.status = OWNED
			entry.equipped = False
			entry.slot = None
			entry.proficiency = None
			entry.source = move.source
		for character_id, balance in balances.items() :
			characters[character_id].currency = balance
		for payment in transfer.payments :
			if payment.amount :
				session.add(CurrencyRows(character_id=payment.character_id, guild_id=guild_id, amount=payment.amount,
				                         reason=payment.reason, actor_uid=payment.actor_uid, note=payment.note))
		return None

	# == trades ==

	# ============================================================
	def add_trade(self, guild_id: int, left: Characters, right: Characters) -> Trades | None :
		with self.createsession() as session :
			trade = Trades(guild_id=guild_id, left_character_id=left.id, right_character_id=right.id,
			               left_uid=left.uid, right_uid=right.uid,
			               offers={"left" : {"items" : [], "currency" : 0}, "right" : {"items" : [], "currency" : 0}},
			               accepted=[], state="open")
			session.add(trade)
			self.commit(session)
			return trade

	# ============================================================
	def trade(self, trade_id: int | None) -> Trades | None :
		if trade_id is None :
			return None
		with self.createsession() as session :
			return session.scalar(Select(Trades).where(Trades.id == trade_id))

	# ============================================================
	def update_trade(self, trade_id: int, **fields) -> Trades | None :
		with self.createsession() as session :
			trade = session.scalar(Select(Trades).where(Trades.id == trade_id))
			if trade is None :
				return None
			for key, value in fields.items() :
				if key in TRADES_FIELDS :
					setattr(trade, key, value)
			self.commit(session)
			return trade

	# ============================================================
	def open_trades(self, character_id: int) -> list[Trades] :
		with self.createsession() as session :
			return list(session.scalars(Select(Trades).where(
				Trades.state == "open",
				(Trades.left_character_id == character_id) | (Trades.right_character_id == character_id))).all())

	# == market ==

	# ============================================================
	def add_listing(self, guild_id: int, entry: CharacterGear, seller: Characters, price: int,
	                expires_at: datetime | None) -> MarketListings | None :
		"""Lists the item: it gets the status "listed" (out of the inventory and fights) in the same transaction."""
		with self.createsession() as session :
			locked = session.scalar(Select(CharacterGear).where(CharacterGear.id == entry.id).with_for_update())
			if locked is None or locked.character_id != seller.id or locked.status != OWNED or locked.equipped :
				session.rollback()
				return None
			locked.status = LISTED
			listing = MarketListings(guild_id=guild_id, entry_id=entry.id, seller_character_id=seller.id,
			                         seller_uid=seller.uid, name=entry.name, price=price, fee=0, state="open",
			                         expires_at=expires_at)
			session.add(listing)
			self.commit(session)
			return listing

	# ============================================================
	def listing(self, listing_id: int | None) -> MarketListings | None :
		if listing_id is None :
			return None
		with self.createsession() as session :
			return session.scalar(Select(MarketListings).where(MarketListings.id == listing_id))

	# ============================================================
	def update_listing(self, listing_id: int, **fields) -> MarketListings | None :
		with self.createsession() as session :
			listing = session.scalar(Select(MarketListings).where(MarketListings.id == listing_id))
			if listing is None :
				return None
			for key, value in fields.items() :
				if key in LISTING_FIELDS :
					setattr(listing, key, value)
			self.commit(session)
			return listing

	# ============================================================
	def listings(self, guild_id: int, states: tuple[str, ...] = ("open",)) -> list[MarketListings] :
		with self.createsession() as session :
			return list(session.scalars(Select(MarketListings).where(MarketListings.guild_id == guild_id,
			                                                         MarketListings.state.in_(states))
			                            .order_by(MarketListings.id)).all())

	# ============================================================
	def expired_listings(self, now: datetime | None = None) -> list[MarketListings] :
		now = now or datetime.now(timezone.utc)
		with self.createsession() as session :
			return list(session.scalars(Select(MarketListings).where(MarketListings.state == "open",
			                                                         MarketListings.expires_at.is_not(None),
			                                                         MarketListings.expires_at <= now)).all())

	# ============================================================
	def close_listing(self, listing_id: int, state: str) -> MarketListings | None :
		"""Ends an open listing without a sale (withdrawn or expired): the item goes back to the seller. Returns None
		when the listing was no longer open."""
		with self.createsession() as session :
			listing = session.scalar(Select(MarketListings).where(MarketListings.id == listing_id).with_for_update())
			if listing is None or listing.state != "open" :
				session.rollback()
				return None
			entry = session.scalar(Select(CharacterGear).where(CharacterGear.id == listing.entry_id).with_for_update()) \
				if listing.entry_id else None
			if entry is not None and entry.status == LISTED :
				entry.status = OWNED
			listing.state = state
			listing.finished_at = datetime.now(timezone.utc)
			self.commit(session)
			return listing
