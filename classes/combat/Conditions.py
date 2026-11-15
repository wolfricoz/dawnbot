"""Conditions on combatants: what each one does, adding and removing them, and counting down their turns.

A combatant's conditions are a list of dicts: {"name": "bleeding", "turns": 2} for timed ones, plus "amount" for the
ones that carry a number (shielded, guard, vulnerable, drained, hasted, thorns, doomed), "source" for the ones tied to
whoever caused them (charmed, taunted) and "dice" for the ones that roll (companion, riposte). Turns count the affected
combatant's own turns and go down at the end of each of them. Internal conditions (guard, exposed, helped, stun_immune)
are not shown as conditions on the board.
"""

STUNNED = "stunned"
WEAKENED = "weakened"
SLOWED = "slowed"
BURNING = "burning"
BLEEDING = "bleeding"
BLINDED = "blinded"
MARKED = "marked"
SHIELDED = "shielded"
INSPIRED = "inspired"
REGENERATING = "regenerating"
SILENCED = "silenced"
# Harmful conditions added with the effect catalog.
POISONED = "poisoned"
PRONE = "prone"
FRIGHTENED = "frightened"
CONFUSED = "confused"
CHARMED = "charmed"
TAUNTED = "taunted"
ASLEEP = "asleep"
RESTRAINED = "restrained"
VULNERABLE = "vulnerable"
CORRODED = "corroded"
WITHERED = "withered"
DRAINED = "drained"
CURSED = "cursed"
DOOMED = "doomed"
DISARMED = "disarmed"
BANISHED = "banished"
# Helpful conditions added with the effect catalog.
EMPOWERED = "empowered"
FORTIFIED = "fortified"
HASTED = "hasted"
EVASIVE = "evasive"
HIDDEN = "hidden"
INTANGIBLE = "intangible"
WARDED = "warded"
REFLECTING = "reflecting"
VAMPIRIC = "vampiric"
FOCUSED = "focused"
BLESSED = "blessed"
RIPOSTE = "riposte"
COMPANION = "companion"
THORNS = "thorns"
UNDYING = "undying"

# Internal: unspent AP as AC (amount), the -2 AC after a fumble, +2 on the next roll (amount), and the turn after a stun.
GUARD = "guard"
EXPOSED = "exposed"
HELPED = "helped"
STUN_IMMUNE = "stun_immune"

# name: (label, the stat a save against it uses, what it does)
DEFINITIONS = {
	STUNNED      : ("Stunned", "endurance", "loses its next turn; can't be stunned two turns in a row"),
	WEAKENED     : ("Weakened", "strength", "-2 to hit and damage"),
	SLOWED       : ("Slowed", "agility", "acts last and has -2 AC"),
	BURNING      : ("Burning", "endurance", "takes 1d4 at the start of each of its turns"),
	BLEEDING     : ("Bleeding", "endurance", "takes 1d4 at the start of each of its turns"),
	BLINDED      : ("Blinded", "perception", "-4 to hit"),
	MARKED       : ("Marked", "agility", "attacks against it get +2"),
	SHIELDED     : ("Shielded", "endurance", "the next damage it takes is reduced by the shield"),
	INSPIRED     : ("Inspired", "charisma", "+2 to hit"),
	REGENERATING : ("Regenerating", "endurance", "heals 1d4 at the start of each of its turns"),
	SILENCED     : ("Silenced", "intelligence", "can't use abilities"),
	POISONED     : ("Poisoned", "endurance", "takes 1d4 at the start of each of its turns and has -1 to hit"),
	PRONE        : ("Prone", "agility", "-2 to hit and -2 AC"),
	FRIGHTENED   : ("Frightened", "charisma", "-2 to hit and -2 on saves"),
	CONFUSED     : ("Confused", "intelligence", "half of its attacks and abilities go to a random combatant"),
	CHARMED      : ("Charmed", "charisma", "can't attack or target whoever charmed it"),
	TAUNTED      : ("Taunted", "charisma", "its attacks must go to whoever taunted it"),
	ASLEEP       : ("Asleep", "endurance", "loses its turns until it takes damage or wakes"),
	RESTRAINED   : ("Restrained", "strength", "can't flee, -2 to hit, attacks against it get +2"),
	VULNERABLE   : ("Vulnerable", "endurance", "takes extra damage from every hit"),
	CORRODED     : ("Corroded", "endurance", "-2 DT"),
	WITHERED     : ("Withered", "endurance", "can't be healed"),
	DRAINED      : ("Drained", "endurance", "starts its next turn with less AP"),
	CURSED       : ("Cursed", "charisma", "rolls attacks and saves twice and keeps the lower"),
	DOOMED       : ("Doomed", "endurance", "takes heavy damage when the doom runs out"),
	DISARMED     : ("Disarmed", "strength", "can't make weapon attacks"),
	BANISHED     : ("Banished", "charisma", "loses its turns and can't be targeted"),
	EMPOWERED    : ("Empowered", "strength", "+2 damage"),
	FORTIFIED    : ("Fortified", "endurance", "+2 AC"),
	HASTED       : ("Hasted", "agility", "starts its next turns with extra AP"),
	EVASIVE      : ("Evasive", "agility", "the next attack against it misses"),
	HIDDEN       : ("Hidden", "agility", "attacks against it get -4; ends when it attacks"),
	INTANGIBLE   : ("Intangible", "endurance", "weapon attacks and physical abilities can't hurt it"),
	WARDED       : ("Warded", "intelligence", "takes half damage from spells"),
	REFLECTING   : ("Reflecting", "intelligence", "the next spell that hurts it hits the caster for half"),
	VAMPIRIC     : ("Vampiric", "endurance", "its hits heal it for half the damage"),
	FOCUSED      : ("Focused", "intelligence", "+2 to hit and +2 to the DC of its abilities"),
	BLESSED      : ("Blessed", "charisma", "+2 on saves"),
	RIPOSTE      : ("Riposte", "agility", "melee attackers that miss it take damage"),
	COMPANION    : ("Companion", "charisma", "a summoned ally attacks at the start of each of its turns"),
	THORNS       : ("Thorns", "endurance", "melee attackers that hit it take damage"),
	UNDYING      : ("Undying", "endurance", "the next hit that would down it leaves it at 1 HP"),
}
# The conditions from before the effect catalog: item choices only offer these (Discord lists hold 25 choices).
BASIC_HARMFUL = [STUNNED, WEAKENED, SLOWED, BURNING, BLEEDING, BLINDED, MARKED, SILENCED]
BASIC_HELPFUL = [INSPIRED, REGENERATING, SHIELDED]
# Conditions an effect can put on an enemy, and the ones that help an ally (boosts).
HARMFUL = BASIC_HARMFUL + [POISONED, PRONE, FRIGHTENED, CONFUSED, CHARMED, TAUNTED, ASLEEP, RESTRAINED, VULNERABLE,
                           CORRODED, WITHERED, DRAINED, CURSED, DOOMED, DISARMED, BANISHED]
HELPFUL = BASIC_HELPFUL + [EMPOWERED, FORTIFIED, HASTED, EVASIVE, HIDDEN, INTANGIBLE, WARDED, REFLECTING, VAMPIRIC,
                           FOCUSED, BLESSED, RIPOSTE, COMPANION, THORNS, UNDYING]
INTERNAL = [GUARD, EXPOSED, HELPED, STUN_IMMUNE]
DAMAGE_OVER_TIME = [BURNING, BLEEDING, POISONED]
# Conditions that cost the combatant its turn, and the ones that keep it from being targeted.
LOSE_TURN = [STUNNED, ASLEEP, BANISHED]
UNTARGETABLE = [BANISHED]
# Conditions that carry a number: the amount used when none is given.
AMOUNTS = {SHIELDED : 5, VULNERABLE : 2, DRAINED : 2, HASTED : 1, THORNS : 2, DOOMED : 10}
# Bonuses and penalties the engine reads.
HIT_MODIFIER = {WEAKENED : -2, BLINDED : -4, POISONED : -1, PRONE : -2, FRIGHTENED : -2, RESTRAINED : -2,
                INSPIRED : 2, FOCUSED : 2}
SAVE_MODIFIER = {FRIGHTENED : -2, BLESSED : 2}
AC_MODIFIER = {SLOWED : -2, EXPOSED : -2, PRONE : -2, FORTIFIED : 2}
DAMAGE_MODIFIER = {WEAKENED : -2, EMPOWERED : 2}
# Attack bonuses against a combatant with the condition (hidden makes it harder).
TARGET_MODIFIER = {MARKED : 2, RESTRAINED : 2, HIDDEN : -4}


# ============================================================
def label(name: str) -> str :
	return DEFINITIONS.get(name, (name.capitalize(), None, ""))[0]


# ============================================================
def save_stat(name: str) -> str :
	return DEFINITIONS.get(name, ("", "endurance", ""))[1]


# ============================================================
def describe(name: str) -> str :
	return DEFINITIONS.get(name, ("", "", ""))[2]


# ============================================================
def get(conditions: list[dict], name: str) -> dict | None :
	return next((condition for condition in conditions or [] if condition.get("name") == name), None)


# ============================================================
def has(conditions: list[dict], name: str) -> bool :
	return get(conditions, name) is not None


# ============================================================
def amount(conditions: list[dict], name: str) -> int :
	condition = get(conditions, name)
	return int(condition.get("amount") or 0) if condition else 0


# ============================================================
def total(conditions: list[dict], table: dict[str, int]) -> int :
	"""The sum of a table's values for the conditions present (like HIT_MODIFIER)."""
	return sum(value for name, value in table.items() if has(conditions, name))


# ============================================================
def add(conditions: list[dict], name: str, turns: int | None = 1, value: int | None = None, **extra) -> bool :
	"""Adds a condition, or refreshes it to the longer duration (and larger amount) when it is already there. extra
	holds keys like source or dice, which replace the old ones.

	@return: False when it could not be added (a stunned-last-turn combatant can't be stunned again).
	"""
	if name == STUNNED and has(conditions, STUN_IMMUNE) :
		return False
	current = get(conditions, name)
	if current is None :
		condition = {"name" : name}
		if turns is not None :
			condition["turns"] = int(turns)
		if value is not None :
			condition["amount"] = int(value)
		condition.update({key : item for key, item in extra.items() if item is not None})
		conditions.append(condition)
		return True
	if turns is not None :
		current["turns"] = max(int(current.get("turns") or 0), int(turns))
	if value is not None :
		current["amount"] = max(int(current.get("amount") or 0), int(value))
	current.update({key : item for key, item in extra.items() if item is not None})
	return True


# ============================================================
def remove(conditions: list[dict], name: str) -> bool :
	before = len(conditions)
	conditions[:] = [condition for condition in conditions if condition.get("name") != name]
	return len(conditions) != before


# ============================================================
def visible(conditions: list[dict]) -> list[dict] :
	return [condition for condition in conditions or [] if condition.get("name") not in INTERNAL]


# ============================================================
def count_down(conditions: list[dict]) -> list[str] :
	"""Ends one of the combatant's turns: timed conditions lose a turn and the ones that run out are removed.

	@return: the names of the conditions that ran out (visible ones only).
	"""
	expired = []
	for condition in list(conditions) :
		# Guard and exposed last until the start of the next turn; helped until it is used.
		if condition.get("name") in (GUARD, HELPED, EXPOSED) or "turns" not in condition :
			continue
		condition["turns"] = int(condition["turns"]) - 1
		if condition["turns"] <= 0 :
			conditions.remove(condition)
			if condition["name"] not in INTERNAL :
				expired.append(condition["name"])
	return expired


# ============================================================
def text(conditions: list[dict]) -> str :
	"""`Bleeding 2, Shielded (5)`"""
	parts = []
	for condition in visible(conditions) :
		part = label(condition["name"])
		if condition.get("amount") :
			part += f" ({condition['amount']})"
		elif condition.get("turns") :
			part += f" {condition['turns']}"
		parts.append(part)
	return ", ".join(parts)


# ============================================================
def cleanse(conditions: list[dict]) -> str | None :
	"""Removes one harmful condition (the first one); returns its name."""
	for condition in list(conditions) :
		if condition.get("name") in HARMFUL :
			conditions.remove(condition)
			return condition["name"]
	return None


# ============================================================
def dispel(conditions: list[dict]) -> str | None :
	"""Removes one helpful condition (the first one); returns its name."""
	for condition in list(conditions) :
		if condition.get("name") in HELPFUL :
			conditions.remove(condition)
			return condition["name"]
	return None


# ============================================================
def untargetable(conditions: list[dict]) -> bool :
	return any(has(conditions, name) for name in UNTARGETABLE)


# ============================================================
def source(conditions: list[dict], name: str) -> int | None :
	"""Who caused a condition (charmed, taunted), as a combatant id."""
	condition = get(conditions, name)
	return condition.get("source") if condition else None
