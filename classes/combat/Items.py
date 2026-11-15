"""Consumables: catalog items used up in a fight with the Use item action (2 AP).

A consumable's combat values are {"use": ..., "dice": ..., "condition": ..., "turns": ...}:
- heal: heals the dice. On a downed ally it is an automatic revive with that much HP, so a character whose
  Intelligence is too low for the Revive action can still bring someone back.
- cure: removes `condition` from the target, or its first harmful condition when no condition is named.
- boost: gives the target `condition` (Inspired, Regenerating or Shielded) for `turns` turns; a shield absorbs the
  dice.
- none: the bot only spends the item and its AP; the GM settles what it does.
"""
from classes.combat import Conditions, Rules

HEAL = "heal"
CURE = "cure"
BOOST = "boost"
NONE = "none"
USES = [HEAL, CURE, BOOST, NONE]
USE_LABELS = {HEAL : "Heals", CURE : "Cures", BOOST : "Boosts", NONE : "GM settles"}

AP_ITEM = 2
TURNS_LIMIT = 5
DEFAULTS = {"use" : HEAL, "dice" : "2d4", "condition" : None, "turns" : 2}
BOOSTS = Conditions.HELPFUL
CURES = Conditions.HARMFUL


# ============================================================
def normalise(combat: dict | None) -> dict :
	"""A consumable's combat values with the defaults filled in."""
	values = dict(DEFAULTS)
	for key, value in (combat or {}).items() :
		if key in DEFAULTS :
			values[key] = value
	if values["use"] not in USES :
		values["use"] = NONE
	return values


# ============================================================
def check(values: dict) -> str | None :
	"""What is wrong with a consumable's values, or None."""
	use = values.get("use")
	if use not in USES :
		return f"use must be one of {', '.join(USES)}."
	condition = values.get("condition")
	if use == BOOST and condition not in BOOSTS :
		return f"A boost item needs a condition: {', '.join(BOOSTS)}."
	if use == CURE and condition is not None and condition not in CURES :
		return f"A cure item removes one of: {', '.join(CURES)} (or leave the condition empty for any)."
	if use == HEAL or (use == BOOST and condition == Conditions.SHIELDED) :
		if not isinstance(values.get("dice"), str) or not Rules.DICE.fullmatch(values["dice"]) :
			return "A healing or shield item needs dice, like 2d4."
	turns = values.get("turns")
	if not isinstance(turns, int) or isinstance(turns, bool) or not 1 <= turns <= TURNS_LIMIT :
		return f"turns must be a whole number from 1 to {TURNS_LIMIT}."
	return None


# ============================================================
def describe(values: dict) -> str :
	"""`Heals 2d4 (revives a downed ally)`, `Cures bleeding`, `Inspired for 2 turns`."""
	values = normalise(values)
	use, condition = values["use"], values.get("condition")
	if use == HEAL :
		return f"Heals {values['dice']} (revives a downed ally)"
	if use == CURE :
		return f"Cures {Conditions.label(condition).lower()}" if condition else "Cures one harmful condition"
	if use == BOOST :
		amount = f" ({values['dice']})" if condition == Conditions.SHIELDED else ""
		return f"{Conditions.label(condition or '')}{amount} for {values['turns']} turn" \
		       f"{'s' if values['turns'] != 1 else ''}"
	return "The GM settles what it does"


# ============================================================
def snapshot(entry_id: int, name: str, combat: dict | None) -> dict :
	"""How a carried consumable is stored in a combatant's snapshot."""
	return {"key" : f"item:{entry_id}", "entry_id" : entry_id, "name" : name} | normalise(combat)
