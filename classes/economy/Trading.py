"""The rules for trades and payments between characters (design/economy.md, phase 3).

Two characters of different players trade items and currency in a trade window: each side adds what it offers, both
accept, and the bot swaps everything at once. Any change clears both accepts. A player's own characters never trade
or pay each other (that would let a member move wealth between characters). Equipped items have to be put away first,
so worn cursed armor can't be traded; a cursed weapon can, and the trade window shows the curse. In free mode only
items change hands. TRADING turns trades and payments off.
"""
from classes.gear import Carry, Condition
from classes.gear.Gear import Gear
from classes.kernel import RoleplaySettings
from database.database import CharacterGear, Characters, Trades
from database.transactions.CharacterGearTransactions import CharacterGearTransactions
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from database.transactions.TradeTransactions import Move, Payment, Transfer
from resources.configs.ConfigMapping import ConfigMapping

LEFT = "left"
RIGHT = "right"
SIDES = (LEFT, RIGHT)
TRADE_IN = "trade_in"
TRADE_OUT = "trade_out"
PAY = "pay"
EXPIRE_MINUTES = 10


# ============================================================
def trading_on(guild_id: int) -> bool :
	return RoleplaySettings.toggle(guild_id, ConfigMapping.TRADING)


# ============================================================
def pair_problem(mine: Characters | None, theirs: Characters | None) -> str | None :
	"""Why these two characters can't trade or pay each other, or None."""
	if mine is None or theirs is None :
		return "Pick an approved character on each side."
	if mine.state != APPROVED or theirs.state != APPROVED :
		return "Both characters need to be approved."
	if mine.guild_id != theirs.guild_id :
		return "Both characters have to be on this server."
	if mine.uid == theirs.uid :
		return "Your own characters can't trade with or pay each other."
	return None


# ============================================================
def tradable(entry: CharacterGear) -> str | None :
	"""Why an item can't be offered, or None."""
	if entry.status != "owned" :
		return f"{entry.name} is {entry.status}."
	if entry.equipped :
		return f"{entry.name} is equipped; put it away first with /gear unequip."
	return None


# ============================================================
def side_of(trade: Trades, uid: int) -> str | None :
	if uid == trade.left_uid :
		return LEFT
	if uid == trade.right_uid :
		return RIGHT
	return None


# ============================================================
def other(side: str) -> str :
	return RIGHT if side == LEFT else LEFT


# ============================================================
def character_of(trade: Trades, side: str) -> int :
	return trade.left_character_id if side == LEFT else trade.right_character_id


# ============================================================
def offer(trade: Trades, side: str) -> dict :
	offers = trade.offers or {}
	current = offers.get(side) or {}
	return {"items" : list(current.get("items") or []), "currency" : int(current.get("currency") or 0)}


# ============================================================
def with_offer(trade: Trades, side: str, items: list[int] | None = None, currency: int | None = None) -> dict :
	"""The trade's offers with one side's changed."""
	offers = {key : offer(trade, key) for key in SIDES}
	if items is not None :
		offers[side]["items"] = list(dict.fromkeys(items))
	if currency is not None :
		offers[side]["currency"] = max(0, int(currency))
	return offers


# ============================================================
def empty(trade: Trades) -> bool :
	return not any(offer(trade, side)["items"] or offer(trade, side)["currency"] for side in SIDES)


# ============================================================
def item_line(entry: CharacterGear) -> str :
	"""`Sword` with what a trader should know: masterwork, cursed, its condition, a stack's size."""
	notes = []
	if getattr(entry, "quality", None) :
		notes.append(entry.quality)
	if Condition.of(entry) != Condition.GOOD :
		notes.append(Condition.label(Condition.of(entry)).lower())
	if (entry.quantity or 1) > 1 :
		notes.append(f"×{entry.quantity}")
	return entry.name + (f" ({', '.join(notes)})" if notes else "")


# ============================================================
def build_transfer(trade: Trades, actor_uid: int | None = None) -> Transfer :
	"""Every item offered goes to the other character; currency is paid across, each way in the ledger."""
	transfer = Transfer()
	names = {side : CharacterTransactions().get_by_id(character_of(trade, side)) for side in SIDES}
	for side in SIDES :
		giver, receiver = character_of(trade, side), character_of(trade, other(side))
		current = offer(trade, side)
		for entry_id in current["items"] :
			transfer.moves.append(Move(entry_id, giver, receiver))
		if current["currency"] :
			note_out = f"Trade with {names[other(side)].name}" if names[other(side)] else "Trade"
			note_in = f"Trade with {names[side].name}" if names[side] else "Trade"
			transfer.payments.append(Payment(giver, -current["currency"], TRADE_OUT, note_out, actor_uid))
			transfer.payments.append(Payment(receiver, current["currency"], TRADE_IN, note_in, actor_uid))
	return transfer


# ============================================================
def weight_problem(trade: Trades) -> str | None :
	"""Why a character couldn't carry what it would get (past 150% of its carry limit), or None."""
	for side in SIDES :
		receiver = CharacterTransactions().get_by_id(character_of(trade, side))
		if receiver is None or Carry.unit(receiver.guild_id) == Carry.OFF :
			continue
		incoming = [CharacterGearTransactions().get(entry_id) for entry_id in offer(trade, other(side))["items"]]
		outgoing = [CharacterGearTransactions().get(entry_id) for entry_id in offer(trade, side)["items"]]
		weigh = lambda entries : Carry.load_kg([(entry, GearItemTransactions().get(entry.gear_item_id))
		                                        for entry in entries if entry is not None])
		carried, capacity = Carry.load_of(receiver)
		if carried - weigh(outgoing) + weigh(incoming) > capacity * Carry.HARD_LIMIT :
			return f"{receiver.name} couldn't carry all of that."
	return None


# ============================================================
def check(trade: Trades) -> str | None :
	"""Everything that has to hold when the trade goes through, or why it can't."""
	if not trading_on(trade.guild_id) :
		return "Trading is off on this server."
	left = CharacterTransactions().get_by_id(trade.left_character_id)
	right = CharacterTransactions().get_by_id(trade.right_character_id)
	problem = pair_problem(left, right)
	if problem :
		return problem
	if empty(trade) :
		return "Nothing is offered yet."
	if not Gear.economy(trade.guild_id) and any(offer(trade, side)["currency"] for side in SIDES) :
		return "There is no currency to trade in free mode."
	for side in SIDES :
		for entry_id in offer(trade, side)["items"] :
			entry = CharacterGearTransactions().get(entry_id)
			if entry is None or entry.character_id != character_of(trade, side) :
				return "An offered item is no longer there."
			problem = tradable(entry)
			if problem :
				return problem
	return weight_problem(trade)


# ============================================================
def pay(payer: Characters, payee: Characters, amount: int, actor_uid: int, note: str | None = None) -> str | None :
	"""Sends currency to another player's character; returns why it was refused, or None."""
	from database.transactions.TradeTransactions import TradeTransactions

	if not trading_on(payer.guild_id) :
		return "Trading is off on this server."
	if not Gear.economy(payer.guild_id) :
		return "There is no currency to pay in free mode."
	problem = pair_problem(payer, payee)
	if problem :
		return problem
	if amount <= 0 :
		return "Pay at least 1."
	text = f": {note}" if note else ""
	transfer = Transfer(payments=[Payment(payer.id, -amount, PAY, f"Paid {payee.name}{text}", actor_uid),
	                              Payment(payee.id, amount, PAY, f"From {payer.name}{text}", actor_uid)])
	return TradeTransactions().transfer(transfer, payer.guild_id)

