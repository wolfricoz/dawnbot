"""Carry weight and ammunition (design/economy.md, phase 2). Both are off by default.

Carry weight (CARRY_WEIGHT: off, kg or lb): items weigh their catalog weight (kept in kilograms) times how many. A
character carries 11 + 11 × Strength kg (25 + 25 × Strength lb, Fallout 2's formula). Over that, it has 2 AP less in
fights and travels half as fast again; past 150% it can't buy anything more (GMs can still grant items).

Ammunition (AMMO: off or die; counted shots are not built): a ranged weapon that isn't a focus or thrown has an
ammunition die, d12 when full. When a fight ends, the die of the weapon a character was holding is rolled: on a 1 or 2
it steps down, and a d4 that rolls 1 or 2 runs out. A weapon that ran out can't be used in a fight until it is refilled
at the shop, which costs REFILL_STEP for each step back up to d12.
"""
import random

from classes.kernel.ConfigData import ConfigData
from database.database import CharacterGear, Characters, GearItems
from resources.configs.ConfigMapping import ConfigMapping

OFF = "off"
KG = "kg"
LB = "lb"
LB_PER_KG = 2.20462
OVERLOAD_AP = 2
TRAVEL_SLOWDOWN = 1.5
HARD_LIMIT = 1.5

DIE = "die"
AMMO_DICE = ["d12", "d10", "d8", "d6", "d4"]
FULL = AMMO_DICE[0]
EMPTY = "empty"
REFILL_STEP = 20


# == carry weight ==

# ============================================================
def unit(guild_id: int) -> str :
	value = str(ConfigData().get_key(guild_id, ConfigMapping.CARRY_WEIGHT) or OFF).lower()
	return value if value in (KG, LB) else OFF


# ============================================================
def capacity_kg(character: Characters) -> float :
	"""11 + 11 × Strength kg, at least 11 (Strength 0 or below still carries something)."""
	return max(11.0, 11.0 + 11.0 * int(getattr(character, "strength", 0) or 0))


# ============================================================
def load_kg(inventory: list[tuple[CharacterGear, GearItems | None]]) -> float :
	return sum(float(getattr(item, "weight", None) or 0) * max(1, entry.quantity or 1)
	           for entry, item in inventory if entry.status == "owned" and item is not None)


# ============================================================
def show(guild_id: int, kilograms: float) -> str :
	if unit(guild_id) == LB :
		return f"{round(kilograms * LB_PER_KG, 1):g} lb"
	return f"{round(kilograms, 1):g} kg"


# ============================================================
def load_of(character: Characters) -> tuple[float, float] :
	"""(carried, capacity) in kilograms."""
	from classes.gear.Gear import Gear

	return load_kg(Gear.inventory(character.id)), capacity_kg(character)


# ============================================================
def overloaded(character: Characters) -> bool :
	if unit(character.guild_id) == OFF :
		return False
	carried, capacity = load_of(character)
	return carried > capacity


# ============================================================
def too_heavy(character: Characters, item: GearItems, amount: int = 1) -> str | None :
	"""Why the character can't take the item: it would carry more than 150% of what it can. None when it can."""
	if unit(character.guild_id) == OFF or not getattr(item, "weight", None) :
		return None
	carried, capacity = load_of(character)
	if carried + float(item.weight) * amount > capacity * HARD_LIMIT :
		return f"{character.name} can't carry {item.name} as well ({show(character.guild_id, carried)} of " \
		       f"{show(character.guild_id, capacity)} already)."
	return None


# ============================================================
def load_text(character: Characters) -> str :
	"""`Carrying 30 of 66 kg`, with a warning when overloaded; empty when carry weight is off."""
	if unit(character.guild_id) == OFF :
		return ""
	carried, capacity = load_of(character)
	text = f"Carrying {show(character.guild_id, carried)} of {show(character.guild_id, capacity)}"
	if carried > capacity :
		text += f" (overloaded: {OVERLOAD_AP} AP less in fights, slower travel)"
	return text


# ============================================================
def travel_factor(character: Characters) -> float :
	return TRAVEL_SLOWDOWN if overloaded(character) else 1.0


# == ammunition ==

# ============================================================
def ammo_on(guild_id: int) -> bool :
	return str(ConfigData().get_key(guild_id, ConfigMapping.AMMO) or OFF).lower() == DIE


# ============================================================
def uses_ammo(combat: dict | None) -> bool :
	combat = combat or {}
	properties = set(combat.get("properties") or [])
	return combat.get("range") == "ranged" and not properties & {"focus", "thrown"}


# ============================================================
def die_of(entry: CharacterGear) -> str :
	value = getattr(entry, "ammo_die", None)
	return value if value in AMMO_DICE or value == EMPTY else FULL


# ============================================================
def step_down(die: str) -> str :
	index = AMMO_DICE.index(die)
	return AMMO_DICE[index + 1] if index + 1 < len(AMMO_DICE) else EMPTY


# ============================================================
def roll_die(die: str, rng: random.Random | None = None) -> str :
	"""The die after a fight: a 1 or 2 steps it down."""
	if die == EMPTY :
		return EMPTY
	return step_down(die) if (rng or random).randint(1, int(die[1:])) <= 2 else die


# ============================================================
def empty(entry: CharacterGear, combat: dict | None, guild_id: int) -> bool :
	"""True for a weapon that ran out of ammunition (only while AMMO is on)."""
	return ammo_on(guild_id) and uses_ammo(combat) and die_of(entry) == EMPTY


# ============================================================
def use_ammo(guild_id: int, combatant, rng: random.Random | None = None) -> list[str] :
	"""Rolls the ammunition die of the weapon a combatant was holding when the fight ended; returns lines to post."""
	if not ammo_on(guild_id) :
		return []
	key = str(getattr(combatant, "weapon_key", None) or "")
	if not key.startswith("gear:") or not key[5:].isdigit() :
		return []
	from database.transactions.CharacterGearTransactions import CharacterGearTransactions
	from database.transactions.GearItemTransactions import GearItemTransactions

	entry = CharacterGearTransactions().get(int(key[5:]))
	item = GearItemTransactions().get(entry.gear_item_id) if entry is not None else None
	if entry is None or item is None or not uses_ammo(item.combat) :
		return []
	before = die_of(entry)
	after = roll_die(before, rng)
	if after == before :
		return []
	CharacterGearTransactions().update(entry.id, ammo_die=after)
	if after == EMPTY :
		return [f"**{entry.name}** is out of ammunition; refill it with /shop refill."]
	return [f"**{entry.name}**'s ammunition is down to {after}."]


# ============================================================
def refill_steps(entry: CharacterGear) -> int :
	die = die_of(entry)
	return len(AMMO_DICE) if die == EMPTY else AMMO_DICE.index(die)


# ============================================================
def refill_price(entry: CharacterGear, guild_id: int) -> int :
	from classes.gear import Pricing

	return refill_steps(entry) * REFILL_STEP if Pricing.economy(guild_id) else 0
