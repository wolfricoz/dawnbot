"""Loot from fights (design/economy.md, phase 5).

A bestiary entry can drop loot: currency dice (like 3d10) and items, each with a chance and an amount. When a fight
ends, the GM presses Loot on the GM panel: the bot rolls what every defeated bestiary enemy dropped and posts it in the
thread. Winning players press Claim on the items they want; the GM presses Settle. With LOOT_MODE `gm` (the default)
the GM picks who gets each item claimed by more than one character; with `claim` they roll for it (highest d20). An
item nobody claimed is left behind. The currency is split evenly among the winning characters (ledger `loot`). With
IDENTIFY on, enchanted loot arrives unidentified.
"""
import random

from classes.combat import Rules
from classes.gear import Magic
from classes.gear.Gear import Gear
from classes.kernel import RoleplaySettings
from database.database import FightLoot
from database.transactions.BestiaryTransactions import BestiaryTransactions
from database.transactions.CharacterGearTransactions import CharacterGearTransactions
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.DatabaseTransactions import DatabaseTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from resources.configs.ConfigMapping import ConfigMapping

GM = "gm"
CLAIM = "claim"
OPEN = "open"
SETTLED = "settled"
LOOT_REASON = "loot"
ITEM_LIMIT = 20


class LootTransactions(DatabaseTransactions) :

	# ============================================================
	def add(self, **fields) -> FightLoot :
		with self.createsession() as session :
			loot = FightLoot(state=OPEN, **fields)
			session.add(loot)
			self.commit(session)
			return loot

	# ============================================================
	def get(self, loot_id: int) -> FightLoot | None :
		from sqlalchemy import Select

		with self.createsession() as session :
			return session.scalar(Select(FightLoot).where(FightLoot.id == loot_id))

	# ============================================================
	def of_fight(self, fight_id: int) -> FightLoot | None :
		from sqlalchemy import Select

		with self.createsession() as session :
			return session.scalar(Select(FightLoot).where(FightLoot.fight_id == fight_id))

	# ============================================================
	def update(self, loot_id: int, **fields) -> FightLoot | None :
		from sqlalchemy import Select

		with self.createsession() as session :
			loot = session.scalar(Select(FightLoot).where(FightLoot.id == loot_id).with_for_update())
			if loot is None :
				return None
			for key, value in fields.items() :
				setattr(loot, key, value)
			self.commit(session)
			return loot


# == the loot table ==

# ============================================================
def parse(guild_id: int, text: str | None) -> tuple[list[dict] | None, str | None] :
	"""`Healing Draught 50%, Hedge Knife 10% x2` into items, or None and the problem."""
	found = []
	for part in [piece.strip() for piece in (text or "").split(",") if piece.strip()] :
		words, chance, amount = part, 100, 1
		lower = words.lower()
		for separator in (" x", " ×") :
			if separator in lower and lower.rsplit(separator, 1)[1].strip().isdigit() :
				amount = int(lower.rsplit(separator, 1)[1])
				words = words[:lower.rindex(separator)].strip()
				lower = words.lower()
				break
		if words.endswith("%") and " " in words and words.rsplit(" ", 1)[1][:-1].isdigit() :
			words, percent = words.rsplit(" ", 1)
			chance = int(percent[:-1])
		item = GearItemTransactions().find(guild_id, words.strip())
		if item is None :
			return None, f"The catalog has no item called {words.strip()}."
		if not 1 <= chance <= 100 or not 1 <= amount <= 20 :
			return None, f"{item.name}: a chance is 1% to 100% and an amount 1 to 20."
		found.append({"name" : item.name, "chance" : chance, "amount" : amount})
	return found, None


# ============================================================
def describe(loot: dict | None) -> str :
	loot = loot or {}
	parts = []
	if loot.get("currency") :
		parts.append(f"{loot['currency']} currency")
	parts += [f"{entry['name']} {entry.get('chance', 100)}%" + (f" ×{entry['amount']}" if entry.get("amount", 1) > 1
	                                                            else "") for entry in loot.get("items") or []]
	return ", ".join(parts) or "nothing"


# ============================================================
def roll_currency(dice: str | None, rng: random.Random | None = None) -> int :
	if not dice :
		return 0
	text = str(dice).strip()
	if text.isdigit() :
		return int(text)
	try :
		total, _ = Rules.roll_dice(text, rng=rng)
	except ValueError :
		return 0
	return max(0, total)


# ============================================================
def roll(fight, rng: random.Random | None = None) -> tuple[int, list[dict]] :
	"""What the defeated bestiary enemies dropped: (currency, [{"item_id", "name", "amount"}])."""
	rng = rng or random
	currency, items = 0, []
	for combatant in fight.combatants :
		if combatant.side_id == fight.winner_side_id or not combatant.bestiary_id :
			continue
		entry = BestiaryTransactions().get(combatant.bestiary_id)
		loot = (getattr(entry, "loot", None) or {}) if entry is not None else {}
		currency += roll_currency(loot.get("currency"), rng)
		for drop in loot.get("items") or [] :
			if rng.randint(1, 100) > int(drop.get("chance", 100)) :
				continue
			item = GearItemTransactions().find(fight.guild_id, drop["name"])
			if item is not None :
				items.append({"item_id" : item.id, "name" : item.name, "amount" : int(drop.get("amount", 1)),
				              "claims" : [], "winner" : None})
	return currency, items[:ITEM_LIMIT]


# == sharing ==

# ============================================================
def winners(fight) -> list[int] :
	"""The winning characters (not the ones that fled)."""
	return [combatant.character_id for combatant in fight.combatants
	        if combatant.side_id == fight.winner_side_id and combatant.character_id and combatant.state != "fled"]


# ============================================================
def claim(loot: FightLoot, index: int, character_id: int) -> FightLoot | None :
	"""Adds (or takes back) a character's claim on an item."""
	items = [dict(entry) for entry in loot.items]
	if not 0 <= index < len(items) :
		return None
	claims = list(items[index].get("claims") or [])
	if character_id in claims :
		claims.remove(character_id)
	else :
		claims.append(character_id)
	items[index]["claims"] = claims
	return LootTransactions().update(loot.id, items=items)


# ============================================================
def roll_off(claims: list[int], rng: random.Random | None = None) -> int :
	"""The claimant with the highest d20; ties roll again."""
	rng = rng or random
	contenders = list(claims)
	while len(contenders) > 1 :
		rolls = {character_id : rng.randint(1, 20) for character_id in contenders}
		best = max(rolls.values())
		contenders = [character_id for character_id, value in rolls.items() if value == best]
	return contenders[0]


# ============================================================
def settle(loot: FightLoot, fight, picks: dict[int, int] | None = None, actor_uid: int | None = None,
           rng: random.Random | None = None) -> list[str] :
	"""Hands out the loot: each claimed item to its only claimant, the GM's pick (gm mode) or the roll-off winner, and
	the currency split evenly among the winners. Returns lines to post."""
	picks = picks or {}
	lines, items = [], [dict(entry) for entry in loot.items]
	identify = Magic.identify_on(loot.guild_id)
	for index, entry in enumerate(items) :
		claims = entry.get("claims") or []
		if not claims :
			lines.append(f"• {entry['name']}: left behind.")
			continue
		winner = claims[0] if len(claims) == 1 else picks.get(index) if loot.mode == GM and picks.get(index) in claims \
			else roll_off(claims, rng)
		entry["winner"] = winner
		character = CharacterTransactions().get_by_id(winner)
		item = GearItemTransactions().get(entry["item_id"])
		if character is None or item is None :
			continue
		for _ in range(max(1, int(entry.get("amount", 1)))) :
			given = Gear.grant(character, item, actor_uid)
			if given is not None and identify and Magic.enchanted(item) :
				CharacterGearTransactions().update(given.id, identified=False)
		shown = item.unidentified_name if identify and Magic.enchanted(item) and item.unidentified_name else item.name
		amount = f" ×{entry['amount']}" if entry.get("amount", 1) > 1 else ""
		lines.append(f"• {shown}{amount} → **{character.name}**")
	if loot.currency :
		share_ids = winners(fight)
		if share_ids :
			share = loot.currency // len(share_ids)
			for character_id in share_ids :
				character = CharacterTransactions().get_by_id(character_id)
				if character is not None and share :
					Gear.change_currency(character, share, LOOT_REASON, actor_uid, note=f"Fight: {fight.title}")
			lines.append(f"• {loot.currency} currency: {share} each.")
	LootTransactions().update(loot.id, items=items, state=SETTLED)
	return lines


# ============================================================
def mode(guild_id: int) -> str :
	value = RoleplaySettings.text(guild_id, ConfigMapping.LOOT_MODE).lower()
	return value if value in (GM, CLAIM) else GM
