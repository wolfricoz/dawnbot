"""Passive abilities: always on, never activated. A passive is Weak, Normal or Strong and is built from passive effects
(classes/combat/PassiveCatalog.py), each magic or physical like active effects. An ability passive takes two of a
character's ability slots and only takes physical effects; a spell passive takes one spell slot of its tier and only
takes magic effects. Every passive also lowers the character's AP each turn, permanently, by the cost of its effects.

Each passive effect has a type, which is what the engine does with it:
- bonus: a flat bonus to to_hit, damage, ac, dt, hp or sequence. To hit and damage can be limited to a scope:
  melee, ranged, magic (spells), physical (weapons and physical abilities) or one damage type. AC stays within the cap.
- resist: hits of one damage type, of magic or of physical attacks do less damage (at least 1).
- immune: one harmful condition never takes hold.
- trigger: regenerate (heals at the start of each turn), last_stand (drops to 1 HP instead of going down, once per
  fight or twice at Strong), on_strong_hit (its strong hits add a condition), counter (an enemy that misses it in melee
  takes damage, once per round) or second_wind (heals once per fight when it drops to half HP or less).
- aura: standing allies get a bonus to to_hit, damage or ac while it stands (the best aura per bonus counts).
- stacks: every hit it takes from a source (magic, physical, any, or a damage type) adds a stack, each +1 to
  to_hit, damage or ac, for the rest of the fight, up to its own limit (1 to 30) or the tier's.
- lifesteal: its hits heal it for part of the damage.
- berserk: more damage while at half HP or less.
- crit: a wider crit range.
- dc: a higher DC for its abilities' saves.
- save: a bonus on its saves.
- heal_power: its heals heal more.
- thorns: melee attackers that hit it take damage.

The amounts come from the tier (see AMOUNTS). Engine.py applies them; this module holds the numbers and the checks.
"""
from classes.combat import Conditions, Rules
from classes.combat.Effects import Effect, MAGIC, PHYSICAL, REALMS, realm_of

WEAK = "weak"
NORMAL = "normal"
STRONG = "strong"
TIERS = [WEAK, NORMAL, STRONG]
TIER_INDEX = {WEAK : 0, NORMAL : 1, STRONG : 2}
# Ability slots a passive ability takes; a spell passive takes one spell slot instead.
SLOT_COST = 2
# How many effects a passive can hold, by tier.
MAX_EFFECTS = {WEAK : 1, NORMAL : 2, STRONG : 3}
# A Strong passive's effects each cost this much more AP.
STRONG_EXTRA_AP = 1
# A character can't learn a passive that would leave it fewer AP than this.
AP_FLOOR = 3

BONUS = "bonus"
RESIST = "resist"
IMMUNE = "immune"
TRIGGER = "trigger"
AURA = "aura"
STACKS = "stacks"
LIFESTEAL = "lifesteal"
BERSERK = "berserk"
CRIT = "crit"
DC = "dc"
SAVE = "save"
HEAL_POWER = "heal_power"
THORNS = "thorns"
TYPES = [BONUS, RESIST, IMMUNE, TRIGGER, AURA, STACKS, LIFESTEAL, BERSERK, CRIT, DC, SAVE, HEAL_POWER, THORNS]

TO_HIT = "to_hit"
DAMAGE = "damage"
AC = "ac"
DT = "dt"
HP = "hp"
SEQUENCE = "sequence"
FIELDS = [TO_HIT, DAMAGE, AC, DT, HP, SEQUENCE]
FIELD_LABELS = {TO_HIT : "to hit", DAMAGE : "damage", AC : "AC", DT : "DT", HP : "max HP", SEQUENCE : "Sequence"}
# Bonuses the engine adds during the fight; the others are added to the combatant when it joins.
ROLL_FIELDS = [TO_HIT, DAMAGE]
AURA_FIELDS = [TO_HIT, DAMAGE, AC]
STACK_FIELDS = [TO_HIT, DAMAGE, AC]
# (Weak, Normal, Strong)
AMOUNTS = {TO_HIT : (1, 2, 3), DAMAGE : (1, 2, 3), AC : (1, 2, 3), DT : (1, 2, 3), HP : (5, 10, 15),
           SEQUENCE : (2, 4, 6)}
RESIST_AMOUNTS = (2, 4, 6)
AURA_AMOUNTS = (1, 1, 2)
# The stack limit a stacks passive gets when it doesn't set its own, and the highest it may set.
MAX_STACKS = (2, 3, 5)
STACK_LIMIT_MAX = 30
TRIGGER_DICE = ("1d4", "1d6", "1d8")
TRIGGER_TURNS = (1, 2, 3)
LAST_STAND_USES = (0, 1, 2)
SECOND_WIND_DICE = ("1d6", "2d6", "3d6")
# Lifesteal heals the damage divided by this (a quarter, a third, half).
LIFESTEAL_DIVISOR = (4, 3, 2)
BERSERK_DAMAGE = (2, 3, 4)
CRIT_WIDEN = (1, 1, 2)
DC_BONUS = (1, 2, 3)
SAVE_BONUS = (1, 2, 3)
HEAL_BONUS = (2, 3, 4)
THORNS_DAMAGE = (2, 3, 4)

REGENERATE = "regenerate"
LAST_STAND = "last_stand"
ON_STRONG_HIT = "on_strong_hit"
COUNTER = "counter"
SECOND_WIND = "second_wind"
TRIGGERS = [REGENERATE, LAST_STAND, ON_STRONG_HIT, COUNTER, SECOND_WIND]

# Scopes and sources besides damage type names. CHOOSE in the catalog means the player picks it (the target option).
MELEE = Rules.MELEE
RANGED = Rules.RANGED
ANY = "any"
CHOOSE = "choose"
BONUS_SCOPES = [MELEE, RANGED, MAGIC, PHYSICAL]
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
	"""A passive effect's parts with every key present."""
	data = data or {}
	return {"type" : data.get("type"), "field" : data.get("field"), "scope" : data.get("scope"),
	        "trigger" : data.get("trigger"), "condition" : data.get("condition"), "limit" : data.get("limit")}


# ============================================================
def max_stacks(passive: dict) -> int :
	"""How many stacks a stacks passive can hold: its own limit, or its tier's."""
	limit = passive.get("limit")
	return int(limit) if limit else MAX_STACKS[index(passive.get("tier"))]


# ============================================================
def _named(value: str | None, names: list[str]) -> str | None :
	"""The value matched (without case) against names; None when it matches none."""
	if value is None :
		return None
	return next((name for name in names if name.lower() == str(value).strip().lower()), None)


# == building a passive from catalog effects ==

# ============================================================
def scope_choices(effect: Effect, type_names: list[str]) -> list[str] | None :
	"""What the player may pick as the target of an effect whose scope is CHOOSE, or None when it has a fixed one."""
	if effect.params.get("scope") != CHOOSE :
		return None
	kind = effect.mechanic
	if kind == RESIST :
		return RESIST_SOURCES + type_names
	if kind == STACKS :
		return STACK_SOURCES + type_names
	return BONUS_SCOPES + type_names


# ============================================================
def check(kind: str, tier: str, effects: list[Effect], target: str | None, limit: int | None,
          type_names: list[str]) -> tuple[str | None, str | None] :
	"""Checks a passive's effects. @return: the target matched to a scope name (or None), or the problem."""
	if tier not in TIERS :
		return None, "A passive is Weak, Normal or Strong."
	if not effects :
		return None, "Pick at least one passive effect."
	realm = realm_of(kind)
	wrong = [effect.name for effect in effects if effect.realm != realm]
	if wrong :
		other = PHYSICAL if realm == MAGIC else MAGIC
		article = "an" if kind[0] in "aeiou" else "a"
		return None, f"{', '.join(wrong)} {'is a' if len(wrong) == 1 else 'are'} {other} " \
		             f"effect{'s' if len(wrong) != 1 else ''}; {article} {kind} passive only takes {realm} effects."
	if len({effect.key for effect in effects}) != len(effects) :
		return None, "Each effect can only be picked once."
	if len(effects) > MAX_EFFECTS[tier] :
		return None, f"A {tier.capitalize()} passive holds at most {MAX_EFFECTS[tier]} effect" \
		             f"{'s' if MAX_EFFECTS[tier] != 1 else ''}."
	too_low = [effect.name for effect in effects if index(tier) < index(effect.tier if effect.tier in TIERS
	                                                                          else WEAK)]
	if too_low :
		return None, f"{', '.join(too_low)} needs a higher tier."
	choosing = [effect for effect in effects if effect.params.get("scope") == CHOOSE]
	matched = None
	if len(choosing) > 1 :
		return None, "Only one effect in a passive can have a target you pick."
	if choosing :
		options = scope_choices(choosing[0], type_names)
		matched = _named(target, options)
		if matched is None :
			return None, f"{choosing[0].name} needs a target: {', '.join(options)}."
	elif target :
		return None, "None of these effects takes a target."
	if limit is not None :
		if not any(effect.mechanic == STACKS for effect in effects) :
			return None, "Only stacks effects have a stack limit."
		if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= STACK_LIMIT_MAX :
			return None, f"The stack limit must be a whole number from 1 to {STACK_LIMIT_MAX}."
	return matched, None


# ============================================================
def effect_ap(tier: str, effect: Effect) -> int :
	return effect.cost + (STRONG_EXTRA_AP if tier == STRONG else 0)


# ============================================================
def ap_cost(tier: str, effects: list[Effect]) -> int :
	"""How much AP a passive takes away every turn."""
	return sum(effect_ap(tier, effect) for effect in effects)


# ============================================================
def entry(effect: Effect, tier: str, target: str | None, limit: int | None) -> dict :
	"""An effect's parts as the engine reads them (without the id and name of the ability)."""
	params = effect.params
	scope = params.get("scope")
	if scope == CHOOSE :
		scope = target
	return {"type" : effect.mechanic, "field" : params.get("field"), "scope" : scope,
	        "trigger" : params.get("trigger"), "condition" : params.get("condition"),
	        "limit" : limit if effect.mechanic == STACKS else None, "tier" : tier, "realm" : effect.realm,
	        "effect" : effect.key}


# ============================================================
def entries(ability_id: int, name: str, tier: str, effects: list[Effect], target: str | None,
            limit: int | None) -> list[dict] :
	"""A passive ability as the fight uses it: one entry per effect. The first keeps the ability's id (so a running
	fight's stacks and uses still match), the others get `id.n`; the first also carries the AP cost."""
	found = []
	for number, effect in enumerate(effects) :
		found.append({"id" : ability_id if number == 0 else f"{ability_id}.{number}", "name" : name}
		             | entry(effect, tier, target, limit)
		             | {"ap_cost" : ap_cost(tier, effects) if number == 0 else 0})
	return found


# ============================================================
def describe_effect(tier: str, data: dict) -> str :
	"""What one passive effect does, like `+3 to hit with Piercing`."""
	data = normalise(data) | {"tier" : tier}
	kind, field, scope, i = data["type"], data["field"], data["scope"], index(tier)
	if kind == BONUS :
		return f"+{AMOUNTS[field][i]} {FIELD_LABELS[field]}" + (f" with {scope}" if scope else "")
	if kind == RESIST :
		return f"takes {RESIST_AMOUNTS[i]} less damage from {scope} hits"
	if kind == IMMUNE :
		return f"can't be {Conditions.label(data['condition'] or '').lower()}"
	if kind == TRIGGER :
		trigger = data["trigger"]
		if trigger == REGENERATE :
			return f"heals {TRIGGER_DICE[i]} at the start of each turn"
		if trigger == LAST_STAND :
			return f"drops to 1 HP instead of going down ({LAST_STAND_USES[i]}× per fight)"
		if trigger == ON_STRONG_HIT :
			turns = TRIGGER_TURNS[i]
			return f"strong hits make the target {Conditions.label(data['condition'] or '').lower()} for {turns} " \
			       f"turn{'s' if turns != 1 else ''}"
		if trigger == SECOND_WIND :
			return f"heals {SECOND_WIND_DICE[i]} once per fight when it drops to half HP or less"
		return f"enemies that miss it in melee take {TRIGGER_DICE[i]} (once per round)"
	if kind == AURA :
		return f"standing allies get +{AURA_AMOUNTS[i]} {FIELD_LABELS[field]}"
	if kind == STACKS :
		source = "any" if scope == ANY else scope
		return f"each {source} hit it takes adds a stack of +1 {FIELD_LABELS[field]} (up to {max_stacks(data)})"
	if kind == LIFESTEAL :
		return f"its hits heal it for 1/{LIFESTEAL_DIVISOR[i]} of the damage"
	if kind == BERSERK :
		return f"+{BERSERK_DAMAGE[i]} damage at half HP or less"
	if kind == CRIT :
		return f"crit range {CRIT_WIDEN[i]} wider"
	if kind == DC :
		return f"+{DC_BONUS[i]} to the DC of its abilities"
	if kind == SAVE :
		return f"+{SAVE_BONUS[i]} on saves"
	if kind == HEAL_POWER :
		return f"its heals heal {HEAL_BONUS[i]} more"
	if kind == THORNS :
		return f"melee attackers that hit it take {THORNS_DAMAGE[i]}"
	return "does nothing the bot knows"


# ============================================================
def describe(kind: str, tier: str, effects: list[Effect], target: str | None, limit: int | None) -> str :
	"""`Strong passive · -3 AP every turn · 2 slots` followed by one line per effect."""
	slots = "1 spell slot" if kind == "spell" else f"{SLOT_COST} slots"
	head = f"{tier.capitalize()} passive · -{ap_cost(tier, effects)} AP every turn · {slots}"
	if not effects :
		return head + "\nNo effects yet: build it with /ability passive_edit."
	return head + "\n" + "\n".join(f"- {effect.name}: {describe_effect(tier, entry(effect, tier, target, limit))}"
	                               for effect in effects)


# == what the engine reads ==

# ============================================================
def join_bonus(passives: list[dict], field: str) -> int :
	"""The bonus to a field set when the combatant joins (ac, dt, hp, sequence)."""
	return sum(amount(passive["tier"], field) for passive in passives
	           if passive.get("type") == BONUS and passive.get("field") == field and not passive.get("scope"))


# ============================================================
def ap_penalty(passives: list[dict]) -> int :
	"""The AP the passives take away every turn."""
	return sum(int(passive.get("ap_cost") or 0) for passive in passives)


# ============================================================
def matches(scope: str | None, type_name: str | None, magic: bool, ranged: bool) -> bool :
	"""Whether a scope (or source) covers a hit of this damage type, by a spell or not, at range or not."""
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
def total(passives: list[dict], kind: str, table: tuple) -> int :
	"""The sum of a tier table (like DC_BONUS) over the passives of one type."""
	return sum(table[index(passive["tier"])] for passive in of_type(passives, kind))


# ============================================================
def of_type(passives: list[dict], kind: str) -> list[dict] :
	return [passive for passive in passives if passive.get("type") == kind]


# ============================================================
def triggers(passives: list[dict], trigger: str) -> list[dict] :
	return [passive for passive in of_type(passives, TRIGGER) if passive.get("trigger") == trigger]


# ============================================================
def realm_ok(kind: str, realm: str) -> bool :
	return realm in REALMS and realm_of(kind) == realm
