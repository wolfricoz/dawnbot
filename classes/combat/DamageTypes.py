"""Damage types: the default set, a server's own table, and describing what a type's effect does.

Every weapon, spell and ability has one damage type. Its effect triggers on a strong hit (or always, for Restoration,
which only heals). A server gets the default set the first time its types are used; staff change them with /damagetype.
"""
import logging

from classes.combat import Conditions

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
# Config row listing the default types a server has been given, so a type staff deleted on purpose isn't put back, and
# defaults added in later versions still reach servers that already had a table.
OFFERED_KEY = "DAMAGE_TYPE_DEFAULTS"
# The defaults every server with a table already had before OFFERED_KEY existed.
ORIGINAL_DEFAULTS = ["Slashing", "Piercing", "Blunt", "Fire", "Frost", "Lightning", "Arcane", "Poison", "Radiant",
                     "Mental", "Restoration"]

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
	("Acid", STRONG_HIT, {"kind" : CONDITION, "condition" : Conditions.CORRODED, "turns" : 2}),
	("Necrotic", STRONG_HIT, {"kind" : CONDITION, "condition" : Conditions.WITHERED, "turns" : 2}),
	("Sonic", STRONG_HIT, {"kind" : CONDITION, "condition" : Conditions.PRONE, "turns" : 1}),
	(RESTORATION, ALWAYS, {"kind" : CLEANSE}),
]



# ============================================================
def _transactions() :
	"""The damage type table, imported when first needed so the engine (which only reads the constants above) never
	loads the database."""
	from database.transactions.DamageTypeTransactions import DamageTypeTransactions

	return DamageTypeTransactions()

class DamageTypes :

	# ============================================================
	@staticmethod
	def ensure(guild_id: int) -> None :
		"""Gives a server the default types when it has none, and any default added since it got its table (like Acid,
		Necrotic and Sonic) that it doesn't have yet. Each default is only offered once, so deleting one sticks."""
		transactions = _transactions()
		existing = {record.name.lower() for record in transactions.get_all(guild_id)}
		offered = DamageTypes.offered(guild_id)
		if not existing :
			offered = []
		elif offered is None :
			offered = list(ORIGINAL_DEFAULTS)
		added = False
		for name, trigger, effect in DEFAULTS :
			if name in offered :
				continue
			if name.lower() not in existing :
				transactions.add(guild_id, name, trigger=trigger, effect=effect, pack=PACK)
			offered.append(name)
			added = True
		if added or DamageTypes.offered(guild_id) is None :
			DamageTypes.remember(guild_id, offered)

	# ============================================================
	@staticmethod
	def offered(guild_id: int) -> list[str] | None :
		"""The default types the server has been given, or None when that was never written down."""
		from classes.kernel.ConfigData import ConfigData

		try :
			value = ConfigData().get_guild(guild_id).get(OFFERED_KEY)
		except Exception :
			return None
		if not value :
			return None
		return [name.strip() for name in str(value).split(",") if name.strip()]

	# ============================================================
	@staticmethod
	def remember(guild_id: int, names: list[str]) -> None :
		from classes.kernel.ConfigData import ConfigData

		try :
			ConfigData().add_key(guild_id, OFFERED_KEY, ",".join(dict.fromkeys(names)), overwrite=True)
		except Exception as e :
			# A server not in the servers table yet can't keep config; it is offered the defaults again next time.
			logging.debug(f"Could not remember the damage type defaults of {guild_id}: {e}")

	# ============================================================
	@staticmethod
	def reset(guild_id: int) -> None :
		_transactions().delete_all(guild_id)
		DamageTypes.ensure(guild_id)

	# ============================================================
	@staticmethod
	def top_up(guild_id: int) -> None :
		"""At start-up: gives servers that already have a table the defaults added since (servers without one get
		the whole set the first time they use damage types)."""
		if _transactions().get_all(guild_id) :
			DamageTypes.ensure(guild_id)

	# ============================================================
	@staticmethod
	def table(guild_id: int) -> dict[str, dict] :
		"""{lowercase name: {"name", "trigger", "effect"}} for the server."""
		DamageTypes.ensure(guild_id)
		return {record.name.lower() : {"name" : record.name, "trigger" : record.trigger, "effect" : record.effect or {}}
		        for record in _transactions().get_all(guild_id)}

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
