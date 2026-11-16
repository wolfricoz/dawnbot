"""What gear costs a particular character, what it sells for, and a suggested price for new catalog items
(design/economy.md).

Charisma is the bartering stat: each point of modifier (stat − STAT_BASE) takes 3% off buying, at most 15%, and adds 2% to
selling, which returns 30% between 20% and 40%. A faction's price multiplies with Charisma, but the total discount
never passes 35%. Selling is based on the catalog price, so given and looted gear sells too, and buying cheap to sell
dear never pays. In free mode everything costs nothing and sells for nothing.
"""
from classes.combat import Rules
from classes.gear import Rarity
from classes.kernel.ConfigData import ConfigData
from database.database import CharacterGear, Characters, GearItems
from resources.configs.ConfigMapping import ConfigMapping

BUY_STEP = 0.03
BEST_BUY = 0.85
SELL_RATE = 0.30
SELL_STEP = 0.02
SELL_LOWEST = 0.20
SELL_HIGHEST = 0.40
# Charisma and faction standing together never take more than this off.
LOWEST_PRICE = 0.65
MASTERWORK_SELL = 1.5
MASTERWORK = "masterwork"
CURSED = "cursed"
# How far a suggested price may sit either side of the middle.
SUGGESTION_SPREAD = 0.25


# ============================================================
def economy(guild_id: int) -> bool :
	return str(ConfigData().get_key(guild_id, ConfigMapping.ECONOMY)).lower() != "free"


# ============================================================
def charisma_modifier(character: Characters) -> int :
	base = ConfigData().get_int(character.guild_id, ConfigMapping.STAT_BASE)
	return Rules.modifier(getattr(character, "charisma", 5) or 0, 5 if base is None else base)


# ============================================================
def buy_multiplier(character: Characters) -> float :
	"""What Charisma does to a price: 0.85 at best, above 1 for low Charisma."""
	return max(BEST_BUY, 1 - BUY_STEP * charisma_modifier(character))


# ============================================================
def sell_rate(character: Characters) -> float :
	return min(SELL_HIGHEST, max(SELL_LOWEST, SELL_RATE + SELL_STEP * charisma_modifier(character)))


# ============================================================
def buy_price(character: Characters, item: GearItems) -> int :
	"""What this character pays for the item: Charisma and the item's faction, never under 65% of the catalog price."""
	if not economy(item.guild_id) or not item.price :
		return 0
	from classes.economy.FactionFlow import FactionFlow

	multiplier = buy_multiplier(character)
	faction_price = FactionFlow.price_for(character, item, item.price)
	if faction_price != item.price :
		multiplier *= faction_price / item.price
	return max(0, round(item.price * max(LOWEST_PRICE, multiplier)))


# ============================================================
def base_value(entry: CharacterGear, item: GearItems | None) -> int :
	"""What selling is worked out from: the catalog price, or what was paid when the item left the catalog."""
	return item.price if item is not None else (entry.price_paid or 0)


# ============================================================
def sell_value(entry: CharacterGear, character: Characters, item: GearItems | None) -> int :
	"""What the character gets for the whole entry (all of a stack); masterwork 50% more, cursed nothing."""
	if not economy(character.guild_id) or getattr(entry, "quality", None) == CURSED :
		return 0
	value = base_value(entry, item) * sell_rate(character) * max(1, getattr(entry, "quantity", 1) or 1)
	if getattr(entry, "quality", None) == MASTERWORK :
		value *= MASTERWORK_SELL
	return int(value)


# == suggested prices ==

# ============================================================
def _dice_average(dice) -> float :
	try :
		amount, sides = Rules.parse_dice(dice)
	except ValueError :
		return 0.0
	return amount * (sides + 1) / 2


# ============================================================
def suggest(kind: str, combat: dict | None, requirements: dict | None = None) -> int | None :
	"""A middle price for an item with these values, or None when there is nothing to go on (materials, items without
	combat values). Fitted to the fantasy pack, where stronger weapons need more SPECIAL: a weapon's price grows about
	45% per point of its highest requirement, with the square root of its average damage and 20% per point of hit_mod.
	Armor grows with the square of AC + DT."""
	combat = combat or {}
	if kind == "weapon" :
		average = _dice_average(combat.get("dice"))
		if not average :
			return None
		highest = max([int(value) for value in (requirements or {}).values()] or [0])
		price = 65 * 1.45 ** max(0, highest) * (average / 6) ** 0.5 * max(0.2, 1 + 0.2 * int(combat.get("hit_mod") or 0))
		return _round(price)
	if kind == "armor" :
		protection = int(combat.get("ac") or 0) + int(combat.get("dt") or 0)
		price = 100 + 50 * protection ** 2
		price += 300 * (int(combat.get("hit_mod") or 0) + int(combat.get("ability_hit_mod") or 0))
		return _round(price)
	if kind == "consumable" :
		average = _dice_average(combat.get("dice"))
		use = combat.get("use")
		if use == "heal" and average :
			return _round(1.5 * average ** 2)
		if use == "boost" :
			return _round(60 * max(1, int(combat.get("turns") or 2)))
		if use == "cure" :
			return 35
	return None


# ============================================================
def _round(price: float) -> int :
	step = 10 if price < 1000 else 50
	return max(step, int(round(price / step) * step))


# ============================================================
def suggestion_text(kind: str, combat: dict | None, requirements: dict | None, price: int | None,
                    guild_id: int) -> str :
	"""A note for staff: the suggested price range for these values, and how the given price compares."""
	middle = suggest(kind, combat, requirements)
	if middle is None :
		return ""
	low, high = _round(middle * (1 - SUGGESTION_SPREAD)), _round(middle * (1 + SUGGESTION_SPREAD))
	name = ConfigData().get_key(guild_id, ConfigMapping.CURRENCY_NAME)
	text = f" Suggested price for these values: {low} to {high} {name} ({Rarity.label(Rarity.from_price(middle))})."
	if price is not None and price < low :
		text += " The price you set is below that."
	elif price is not None and price > high :
		text += " The price you set is above that."
	return text
