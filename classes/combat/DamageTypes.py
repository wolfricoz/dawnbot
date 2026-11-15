"""Damage types: the default set, a server's own table, and describing what a type's effect does.

Every weapon, spell and ability has one damage type. Its effect triggers on a strong hit (or always, for Restoration,
which only heals). A server gets the default set the first time its types are used; staff change them with /damagetype.
"""
from classes.combat import Conditions
from database.transactions.DamageTypeTransactions import DamageTypeTransactions

STRONG_HIT = "strong_hit"
ALWAYS = "always"
TRIGGERS = [STRONG_HIT, ALWAYS]

# Effect kinds: a condition on the target, ignoring DT for the hit, arcing to another enemy for half the damage,
# removing a condition from a healed ally, or nothing.
CONDITION = "condition"
IGNORE_DT = "ignore_dt"
ARC = "arc"
CLEANSE = "cleanse"
NONE = "none"
EFFECT_KINDS = [CONDITION, IGNORE_DT, ARC, CLEANSE, NONE]
RESTORATION = "Restoration"
PACK = "default"

DEFAULTS = [
	("Slashing", STRONG_HIT, {"kind" : CONDITION, "condition" : Conditions.BLEEDING, "turns" : 2}),
	("Piercing", STRONG_HIT, {"kind" : IGNORE_DT}),
	("Blunt", STRONG_HIT, {"kind" : CONDITION, "condition" : Conditions.STUNNED, "turns" : 1}),
	("Fire", STRONG_HIT, {"kind" : CONDITION, "condition" : Conditions.BURNING, "turns" : 2}),
	("Frost", STRONG_HIT, {"kind" : CONDITION, "condition" : Conditions.SLOWED, "turns" : 1}),
	("Lightning", STRONG_HIT, {"kind" : ARC}),
	("Arcane", STRONG_HIT, {"kind" : CONDITION, "condition" : Conditions.MARKED, "turns" : 2}),
	("Poison", STRONG_HIT, {"kind" : CONDITION, "condition" : Conditions.WEAKENED, "turns" : 2}),
	("Radiant", STRONG_HIT, {"kind" : CONDITION, "condition" : Conditions.BLINDED, "turns" : 1}),
	("Mental", STRONG_HIT, {"kind" : CONDITION, "condition" : Conditions.SILENCED, "turns" : 1}),
	(RESTORATION, ALWAYS, {"kind" : CLEANSE}),
]


class DamageTypes :

	# ============================================================
	@staticmethod
	def ensure(guild_id: int) -> None :
		"""Gives a server the default types when it has none."""
		transactions = DamageTypeTransactions()
		if transactions.get_all(guild_id) :
			return
		for name, trigger, effect in DEFAULTS :
			transactions.add(guild_id, name, trigger=trigger, effect=effect, pack=PACK)

	# ============================================================
	@staticmethod
	def reset(guild_id: int) -> None :
		DamageTypeTransactions().delete_all(guild_id)
		DamageTypes.ensure(guild_id)

	# ============================================================
	@staticmethod
	def table(guild_id: int) -> dict[str, dict] :
		"""{lowercase name: {"name", "trigger", "effect"}} for the server."""
		DamageTypes.ensure(guild_id)
		return {record.name.lower() : {"name" : record.name, "trigger" : record.trigger, "effect" : record.effect or {}}
		        for record in DamageTypeTransactions().get_all(guild_id)}

	# ============================================================
	@staticmethod
	def names(guild_id: int) -> list[str] :
		return [entry["name"] for entry in DamageTypes.table(guild_id).values()]

	# ============================================================
	@staticmethod
	def check_effect(effect: dict) -> str | None :
		"""Why an effect is not valid, or None."""
		kind = effect.get("kind")
		if kind not in EFFECT_KINDS :
			return f"The effect must be one of {', '.join(EFFECT_KINDS)}."
		if kind == CONDITION :
			if effect.get("condition") not in Conditions.HARMFUL :
				return f"The condition must be one of {', '.join(Conditions.HARMFUL)}."
			turns = effect.get("turns")
			if not isinstance(turns, int) or not 1 <= turns <= 5 :
				return "A condition lasts 1 to 5 turns."
		return None

	# ============================================================
	@staticmethod
	def describe(effect: dict | None) -> str :
		effect = effect or {}
		kind = effect.get("kind")
		if kind == CONDITION :
			turns = int(effect.get("turns") or 1)
			return f"{Conditions.label(effect.get('condition', ''))}, {turns} turn{'s' if turns != 1 else ''}"
		if kind == IGNORE_DT :
			return "Ignores DT for that hit"
		if kind == ARC :
			return "Arcs to another enemy for half the damage"
		if kind == CLEANSE :
			return "Healing also removes one condition"
		return "No effect"

	# ============================================================
	@staticmethod
	def trigger_text(trigger: str) -> str :
		return "always" if trigger == ALWAYS else "strong hit"
