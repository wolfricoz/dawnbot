"""Passive abilities: always on, never activated. A passive is an ability (not a spell) of tier Weak, Normal or Strong,
and takes two of a character's ability slots (an active ability takes one).

A passive is one of:
- bonus: a flat bonus to to_hit, damage, ac, dt, hp, ap or sequence. To hit and damage can be limited to a scope:
  melee, ranged, magic (abilities and spells) or one damage type. AC stays within the cap of 18.
- resist: hits of one damage type, of magic or of physical attacks do less damage (at least 1).
- immune: one harmful condition never takes hold (Normal only).
- trigger: regenerate (heals at the start of each turn), last_stand (once per fight, or twice at Strong, drops to 1
  HP instead of going down; Normal or Strong), on_strong_hit (its strong hits add a condition) or counter (an enemy
  that misses it in melee takes damage, once per round).
- aura: standing allies get a bonus to to_hit, damage or ac while it stands (the best aura per bonus counts).
- stacks: every hit it takes from a source (magic, physical, any, or a damage type) adds a stack, each +1 to
  to_hit, damage or ac, up to a maximum, for the rest of the fight.

The amounts come from the tier (see AMOUNTS). Engine.py applies them; this module only holds the numbers and checks.
"""
from classes.combat import Conditions, Rules

WEAK = "weak"
NORMAL = "normal"
STRONG = "strong"
TIERS = [WEAK, NORMAL, STRONG]
TIER_INDEX = {WEAK : 0, NORMAL : 1, STRONG : 2}
SLOT_COST = 2

BONUS = "bonus"
RESIST = "resist"
IMMUNE = "immune"
TRIGGER = "trigger"
AURA = "aura"
STACKS = "stacks"
TYPES = [BONUS, RESIST, IMMUNE, TRIGGER, AURA, STACKS]
TYPE_LABELS = {BONUS : "Bonus", RESIST : "Resistance", IMMUNE : "Immunity", TRIGGER : "Trigger", AURA : "Aura",
               STACKS : "Stacks"}

TO_HIT = "to_hit"
DAMAGE = "damage"
AC = "ac"
DT = "dt"
HP = "hp"
AP = "ap"
SEQUENCE = "sequence"
FIELDS = [TO_HIT, DAMAGE, AC, DT, HP, AP, SEQUENCE]
FIELD_LABELS = {TO_HIT : "to hit", DAMAGE : "damage", AC : "AC", DT : "DT", HP : "max HP", AP : "AP",
                SEQUENCE : "Sequence"}
# Bonuses the engine adds during the fight; the others are added to the combatant when it joins.
ROLL_FIELDS = [TO_HIT, DAMAGE]
AURA_FIELDS = [TO_HIT, DAMAGE, AC]
STACK_FIELDS = [TO_HIT, DAMAGE, AC]
# (Weak, Normal, Strong)
AMOUNTS = {TO_HIT : (1, 2, 3), DAMAGE : (1, 2, 3), AC : (1, 2, 3), DT : (1, 2, 3), HP : (5, 10, 15), AP : (1, 1, 2),
           SEQUENCE : (2, 4, 6)}
RESIST_AMOUNTS = (2, 4, 6)
AURA_AMOUNTS = (1, 1, 2)
MAX_STACKS = (2, 3, 5)
TRIGGER_DICE = ("1d4", "1d6", "1d8")
TRIGGER_TURNS = (1, 2, 3)
LAST_STAND_USES = (0, 1, 2)

REGENERATE = "regenerate"
LAST_STAND = "last_stand"
ON_STRONG_HIT = "on_strong_hit"
COUNTER = "counter"
TRIGGERS = [REGENERATE, LAST_STAND, ON_STRONG_HIT, COUNTER]
TRIGGER_LABELS = {REGENERATE : "Regenerates", LAST_STAND : "Last stand", ON_STRONG_HIT : "Strong hits add",
                  COUNTER : "Counters melee misses"}

# Scopes and sources besides damage type names.
MELEE = Rules.MELEE
RANGED = Rules.RANGED
MAGIC = "magic"
PHYSICAL = "physical"
ANY = "any"
BONUS_SCOPES = [MELEE, RANGED, MAGIC]
RESIST_SOURCES = [MAGIC, PHYSICAL]
STACK_SOURCES = [ANY, MAGIC, PHYSICAL]


# ============================================================
def index(tier: str) -> int :
	return TIER_INDEX.get(tier, 0)


# ============================================================
def amount(tier: str, field: str) -> int :
	return AMOUNTS[field][index(tier)]


# ============================================================
def normalise(data: dict | None) -> dict :
	"""A passive's parts with every key present."""
	data = data or {}
	return {"type" : data.get("type"), "field" : data.get("field"), "scope" : data.get("scope"),
	        "trigger" : data.get("trigger"), "condition" : data.get("condition")}


# ============================================================
def _named(value: str | None, names: list[str]) -> str | None :
	"""The value matched (without case) against names; None when it matches none."""
	if value is None :
		return None
	return next((name for name in names if name.lower() == str(value).strip().lower()), None)


# ============================================================
def check(tier: str, data: dict, type_names: list[str]) -> tuple[dict | None, str | None] :
	"""Checks a passive's parts. @return: the corrected parts (scope names matched), or the problem."""
	data = normalise(data)
	kind, field, scope = data["type"], data["field"], data["scope"]
	if tier not in TIERS :
		return None, "A passive is Weak, Normal or Strong."
	if kind not in TYPES :
		return None, f"The passive must be one of: {', '.join(TYPES)}."
	clean = {"type" : kind, "field" : None, "scope" : None, "trigger" : None, "condition" : None}
	if kind == BONUS :
		if field not in FIELDS :
			return None, f"A bonus needs a field: {', '.join(FIELDS)}."
		clean["field"] = field
		if scope :
			if field not in ROLL_FIELDS :
				return None, "Only to hit and damage bonuses can be limited to melee, ranged, magic or a damage type."
			matched = _named(scope, BONUS_SCOPES + type_names)
			if matched is None :
				return None, "Limit it to melee, ranged, magic or one of the server's damage types."
			clean["scope"] = matched
	elif kind == RESIST :
		matched = _named(scope, RESIST_SOURCES + type_names)
		if matched is None :
			return None, "A resistance needs a damage type, magic or physical."
		clean["scope"] = matched
	elif kind == IMMUNE :
		if data["condition"] not in Conditions.HARMFUL :
			return None, f"An immunity needs a harmful condition: {', '.join(Conditions.HARMFUL)}."
		if tier != NORMAL :
			return None, "An immunity is a Normal passive."
		clean["condition"] = data["condition"]
	elif kind == TRIGGER :
		trigger = data["trigger"]
		if trigger not in TRIGGERS :
			return None, f"A trigger needs one of: {', '.join(TRIGGERS)}."
		clean["trigger"] = trigger
		if trigger == LAST_STAND and tier == WEAK :
			return None, "Last stand is a Normal (once per fight) or Strong (twice) passive."
		if trigger == ON_STRONG_HIT :
			if data["condition"] not in Conditions.HARMFUL :
				return None, f"A strong-hit trigger adds a harmful condition: {', '.join(Conditions.HARMFUL)}."
			clean["condition"] = data["condition"]
	elif kind == AURA :
		if field not in AURA_FIELDS :
			return None, f"An aura gives allies one of: {', '.join(AURA_FIELDS)}."
		clean["field"] = field
	elif kind == STACKS :
		if field not in STACK_FIELDS :
			return None, f"Stacks add to one of: {', '.join(STACK_FIELDS)}."
		matched = _named(scope or ANY, STACK_SOURCES + type_names)
		if matched is None :
			return None, "Stacks come from any hit, magic, physical attacks or one damage type."
		clean["field"], clean["scope"] = field, matched
	return clean, None


# ============================================================
def describe(tier: str, data: dict) -> str :
	"""One line like `Strong passive · +3 to hit with Piercing` (without the tier when it is left out)."""
	data = normalise(data)
	kind, field, scope, i = data["type"], data["field"], data["scope"], index(tier)
	if kind == BONUS :
		text = f"+{AMOUNTS[field][i]} {FIELD_LABELS[field]}" + (f" with {scope}" if scope else "")
	elif kind == RESIST :
		text = f"takes {RESIST_AMOUNTS[i]} less damage from {scope} hits"
	elif kind == IMMUNE :
		text = f"can't be {Conditions.label(data['condition'] or '').lower()}"
	elif kind == TRIGGER :
		trigger = data["trigger"]
		if trigger == REGENERATE :
			text = f"heals {TRIGGER_DICE[i]} at the start of each turn"
		elif trigger == LAST_STAND :
			uses = LAST_STAND_USES[i]
			text = f"drops to 1 HP instead of going down ({uses}× per fight)"
		elif trigger == ON_STRONG_HIT :
			turns = TRIGGER_TURNS[i]
			text = f"strong hits make the target {Conditions.label(data['condition'] or '').lower()} for {turns} " \
			       f"turn{'s' if turns != 1 else ''}"
		else :
			text = f"enemies that miss it in melee take {TRIGGER_DICE[i]} (once per round)"
	elif kind == AURA :
		text = f"standing allies get +{AURA_AMOUNTS[i]} {FIELD_LABELS[field]}"
	elif kind == STACKS :
		source = "any" if scope == ANY else scope
		text = f"each {source} hit it takes adds a stack of +1 {FIELD_LABELS[field]} (up to {MAX_STACKS[i]})"
	else :
		text = "does nothing the bot knows"
	return f"{tier.capitalize()} passive · {text} · {SLOT_COST} slots"


# == what the engine reads ==

# ============================================================
def join_bonus(passives: list[dict], field: str) -> int :
	"""The bonus to a field set when the combatant joins (ac, dt, hp, ap, sequence)."""
	return sum(amount(passive["tier"], field) for passive in passives
	           if passive.get("type") == BONUS and passive.get("field") == field and not passive.get("scope"))


# ============================================================
def matches(scope: str | None, type_name: str | None, magic: bool, ranged: bool) -> bool :
	"""Whether a scope (or source) covers a hit of this damage type, by magic or a weapon, at range or not."""
	if scope in (None, ANY) :
		return True
	if scope == MAGIC :
		return magic
	if scope == PHYSICAL :
		return not magic
	if scope == MELEE :
		return not magic and not ranged
	if scope == RANGED :
		return not magic and ranged
	return bool(type_name) and scope.lower() == type_name.lower()


# ============================================================
def roll_bonus(passives: list[dict], field: str, type_name: str | None, magic: bool, ranged: bool) -> int :
	"""The to hit or damage bonus for an attack of this kind."""
	return sum(amount(passive["tier"], field) for passive in passives
	           if passive.get("type") == BONUS and passive.get("field") == field
	           and matches(passive.get("scope"), type_name, magic, ranged))


# ============================================================
def of_type(passives: list[dict], kind: str) -> list[dict] :
	return [passive for passive in passives if passive.get("type") == kind]


# ============================================================
def triggers(passives: list[dict], trigger: str) -> list[dict] :
	return [passive for passive in of_type(passives, TRIGGER) if passive.get("trigger") == trigger]
