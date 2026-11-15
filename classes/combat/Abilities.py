"""The rules for abilities and spells: tiers, what a definition may contain, how many a character can know, and the
standard magic schools.

An ability is built from parts so the bot can resolve it: a kind (spell or ability), a tier, the stat it uses, a main
effect, a damage type, and optionally an area and a second condition. See design/combat.md, section 4.
"""
from classes.combat import Conditions, Rules
from classes.combat.DamageTypes import RESTORATION

SPELL = "spell"
ABILITY = "ability"
KINDS = [SPELL, ABILITY]

CANTRIP = "cantrip"
WEAK = "weak"
NORMAL = "normal"
STRONG = "strong"
TIERS = [CANTRIP, WEAK, NORMAL, STRONG]
# tier: (uses per fight (None is unlimited), dice, condition turns, save DC bonus, AP)
TIER_DATA = {
	CANTRIP : (None, "1d6", 1, 0, 3),
	WEAK    : (3, "2d6", 1, 1, 3),
	NORMAL  : (2, "3d6", 2, 2, 4),
	STRONG  : (1, "4d8", 3, 3, 5),
}

DAMAGE = "damage"
HEAL = "heal"
CONDITION = "condition"
SHIELD = "shield"
BOOST = "boost"
EFFECTS = [DAMAGE, HEAL, CONDITION, SHIELD, BOOST]
# Effects aimed at enemies; the others are aimed at allies (or the user).
OFFENSIVE = [DAMAGE, CONDITION]
AREA_TARGETS = 3
BOOSTS = [Conditions.INSPIRED, Conditions.REGENERATING]

# How many spells of each tier a spellcaster can know, and how many abilities (with at most one Strong) others can.
SPELL_SLOTS = {CANTRIP : 1, WEAK : 2, NORMAL : 2, STRONG : 1}
ABILITY_SLOTS = 3
ABILITY_STRONG_SLOTS = 1
LEGENDARY_EXTRA_SLOTS = 1

CASTING_STATS = ["intelligence", "charisma"]
# (name, casting stat, description) of the schools every server starts with.
STANDARD_SCHOOLS = [
	("Elementalism", "intelligence", "Fire, frost and lightning, shaped through study."),
	("Arcana", "intelligence", "Raw magical force, wards and binding."),
	("Necromancy", "intelligence", "Life force, decay and the dead."),
	("Divine", "charisma", "Power granted by gods, saints and faith."),
	("Nature", "charisma", "The voice of beasts, plants and the wild."),
	("Illusion", "charisma", "Tricks of the mind, light and shadow."),
]


# ============================================================
def uses(tier: str) -> int | None :
	return TIER_DATA[tier][0]


# ============================================================
def turns(tier: str) -> int :
	return TIER_DATA[tier][2]


# ============================================================
def dc_bonus(tier: str) -> int :
	return TIER_DATA[tier][3]


# ============================================================
def ap(tier: str) -> int :
	return TIER_DATA[tier][4]


# ============================================================
def dice(tier: str, effect: str, area: bool = False, secondary: str | None = None) -> str :
	"""The ability's dice: the tier's, one step lower when a damage ability adds a condition, halved for an area."""
	value = TIER_DATA[tier][1]
	if effect == DAMAGE and secondary :
		value = Rules.step_down(value)
	if area :
		value = Rules.halve_dice(value)
	return value


# ============================================================
def offensive(effect: str) -> bool :
	return effect in OFFENSIVE


# ============================================================
def check_definition(kind: str, tier: str, effect: str, stat: str, damage_type: str | None, condition: str | None,
                     secondary: str | None, area: bool, school_stat: str | None, type_names: list[str]) -> str | None :
	"""Why the parts don't make a valid ability, or None when they do. school_stat is the casting stat of the spell's
	school (None when it has none)."""
	if kind not in KINDS :
		return f"The kind must be {' or '.join(KINDS)}."
	if tier not in TIERS :
		return f"The tier must be one of {', '.join(TIERS)}."
	if effect not in EFFECTS :
		return f"The effect must be one of {', '.join(EFFECTS)}."
	if stat not in Rules.STATS :
		return "The stat must be a SPECIAL stat."
	if kind == SPELL :
		if school_stat is None :
			return "A spell needs an approved magic school."
		if stat != school_stat :
			return f"Spells of this school use {school_stat.capitalize()}."
	lowered = {name.lower() for name in type_names}
	if effect == HEAL :
		if (damage_type or RESTORATION).lower() != RESTORATION.lower() :
			return "Healing uses the Restoration damage type."
	elif not damage_type or damage_type.lower() not in lowered :
		return "Pick one of the server's damage types (see /damagetype list)."
	if effect == CONDITION :
		if condition not in Conditions.HARMFUL :
			return f"A condition ability needs one of: {', '.join(Conditions.HARMFUL)}."
		if tier == CANTRIP :
			return "Cantrips can't apply conditions; pick damage, heal or shield, or a higher tier."
	elif effect == BOOST :
		if condition not in BOOSTS :
			return f"A boost gives one of: {', '.join(BOOSTS)}."
		if tier == CANTRIP :
			return "Cantrips can't boost; pick damage, heal or shield, or a higher tier."
	elif condition :
		return "Only condition and boost abilities have a main condition; use the second condition for damage."
	if secondary :
		if effect != DAMAGE :
			return "Only damage abilities can add a second condition."
		if secondary not in Conditions.HARMFUL :
			return f"The second condition must be one of: {', '.join(Conditions.HARMFUL)}."
	if area and effect in (BOOST, SHIELD) and tier == CANTRIP :
		return "A cantrip can't affect an area with a shield or boost."
	return None


# ============================================================
def overflow(kinds_and_tiers: list[tuple[str, str]]) -> int :
	"""How many slots over the normal limits a set of (kind, tier) is."""
	spells = [tier for kind, tier in kinds_and_tiers if kind == SPELL]
	abilities = [tier for kind, tier in kinds_and_tiers if kind == ABILITY]
	extra = sum(max(0, spells.count(tier) - limit) for tier, limit in SPELL_SLOTS.items())
	extra += max(0, len(abilities) - ABILITY_SLOTS) + max(0, abilities.count(STRONG) - ABILITY_STRONG_SLOTS)
	return extra


# ============================================================
def check_learn(known: list[tuple[str, str, bool]], kind: str, tier: str, legendary: bool) -> str | None :
	"""Why a character can't learn another ability, or None. known holds (kind, tier, event) for what it knows; event
	abilities don't count. Spellcasters and ability users can't mix, and legendary characters get one extra slot."""
	counted = [(known_kind, known_tier) for known_kind, known_tier, event in known if not event]
	if kind == SPELL and any(known_kind == ABILITY for known_kind, _ in counted) :
		return "A character with abilities can't learn spells (unless an event grants them)."
	if kind == ABILITY and any(known_kind == SPELL for known_kind, _ in counted) :
		return "A spellcaster can't learn abilities (unless an event grants them)."
	allowed = LEGENDARY_EXTRA_SLOTS if legendary else 0
	if overflow(counted + [(kind, tier)]) > allowed :
		if kind == SPELL :
			return (f"Spellcasters know at most {SPELL_SLOTS[CANTRIP]} Cantrip, {SPELL_SLOTS[WEAK]} Weak, "
			        f"{SPELL_SLOTS[NORMAL]} Normal and {SPELL_SLOTS[STRONG]} Strong spell"
			        f"{' (plus one of any tier for legendary characters)' if legendary else ''}.")
		return (f"A character knows at most {ABILITY_SLOTS} abilities, with at most {ABILITY_STRONG_SLOTS} Strong"
		        f"{' (plus one of any tier for legendary characters)' if legendary else ''}.")
	return None


# ============================================================
def summary(kind: str, tier: str, effect: str, stat: str, damage_type: str | None, condition: str | None,
            secondary: str | None, area: bool) -> str :
	"""One line like `Normal spell · damage 2d6 + INT, Fire · area · adds Slowed · 4 AP, 2 uses`."""
	parts = [f"{tier.capitalize()} {kind}"]
	short = Rules.STAT_SHORT.get(stat, stat)
	if effect in (DAMAGE, HEAL, SHIELD) :
		parts.append(f"{effect} {dice(tier, effect, area, secondary)} + {short}")
	else :
		length = turns(tier)
		parts.append(f"{effect}: {Conditions.label(condition or '')} for {length} turn{'s' if length != 1 else ''}"
		             f" (uses {short})")
	if damage_type :
		parts.append(damage_type)
	if area :
		parts.append(f"area (up to {AREA_TARGETS})")
	if secondary :
		parts.append(f"adds {Conditions.label(secondary)}")
	count = uses(tier)
	parts.append(f"{ap(tier)} AP, {'unlimited uses' if count is None else f'{count} use' + ('s' if count != 1 else '')}")
	return " · ".join(parts)
