"""Conditions on combatants: what each one does, adding and removing them, and counting down their turns.

A combatant's conditions are a list of dicts: {"name": "bleeding", "turns": 2} for timed ones, plus "amount" for the
ones that carry a number (shielded, guard). Turns count the affected combatant's own turns and go down at the end of
each of them. Internal conditions (guard, exposed, helped, stun_immune) are not shown as conditions on the board.
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
}
# Conditions an ability can apply to an enemy, and the ones that help an ally (boosts).
HARMFUL = [STUNNED, WEAKENED, SLOWED, BURNING, BLEEDING, BLINDED, MARKED, SILENCED]
HELPFUL = [INSPIRED, REGENERATING, SHIELDED]
INTERNAL = [GUARD, EXPOSED, HELPED, STUN_IMMUNE]
DAMAGE_OVER_TIME = [BURNING, BLEEDING]


# ============================================================
def label(name: str) -> str :
	return DEFINITIONS.get(name, (name.capitalize(), None, ""))[0]


# ============================================================
def save_stat(name: str) -> str :
	return DEFINITIONS.get(name, ("", "endurance", ""))[1]


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
def add(conditions: list[dict], name: str, turns: int | None = 1, value: int | None = None) -> bool :
	"""Adds a condition, or refreshes it to the longer duration (and larger amount) when it is already there.

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
		conditions.append(condition)
		return True
	if turns is not None :
		current["turns"] = max(int(current.get("turns") or 0), int(turns))
	if value is not None :
		current["amount"] = max(int(current.get("amount") or 0), int(value))
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
