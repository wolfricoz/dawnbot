"""The rules for abilities and spells: kinds and tiers, how many a character can know, building one from catalog
effects, and the standard magic schools.

An ability is a kind (spell or ability), a tier, the stat it uses and a list of effects from the catalog
(classes/combat/Effects.py). Spells only take magic effects and abilities only physical ones. Its AP cost is the
tier's base plus the effects' costs. A passive is built the same way from passive effects (classes/combat/Passives.py).
See design/combat.md, section 4.
"""
from classes.combat import EffectCatalog, Effects, PassiveCatalog, Passives
from classes.combat.Effects import CANTRIP, NORMAL, STRONG, TIERS, WEAK, Effect

SPELL = "spell"
ABILITY = "ability"
KINDS = [SPELL, ABILITY]
TIER_DATA = Effects.TIER_DATA

# How many spells of each tier a spellcaster can know, and how many abilities (with at most one Strong) others can.
SPELL_SLOTS = {CANTRIP : 1, WEAK : 2, NORMAL : 2, STRONG : 1}
ABILITY_SLOTS = 3
ABILITY_STRONG_SLOTS = 1
# A passive ability takes this many of the ability slots; a spell passive takes one spell slot of its tier.
PASSIVE_SLOTS = Passives.SLOT_COST
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
	return Effects.uses(tier)


# ============================================================
def turns(tier: str) -> int :
	return Effects.turns(tier)


# ============================================================
def dc_bonus(tier: str) -> int :
	return Effects.dc_bonus(tier)


# == effects stored on an ability ==

# ============================================================
def keys(stored: list | None) -> list[str] :
	"""The effect keys of an ability's stored effects ([{"key": ...}, ...], or plain keys)."""
	return [entry.get("key") if isinstance(entry, dict) else str(entry) for entry in stored or []]


# ============================================================
def options(stored: list | None) -> tuple[str | None, int | None] :
	"""A passive's target and stack limit, kept on its stored effects."""
	target = limit = None
	for entry in stored or [] :
		if isinstance(entry, dict) :
			target = target or entry.get("target")
			limit = limit or entry.get("limit")
	return target, limit


# ============================================================
def store(effects: list[Effect], target: str | None = None, limit: int | None = None) -> list[dict] :
	"""Effects as an ability record keeps them."""
	stored = []
	for effect in effects :
		entry = {"key" : effect.key}
		if target and effect.params.get("scope") == Passives.CHOOSE :
			entry["target"] = target
		if limit and effect.mechanic == Passives.STACKS :
			entry["limit"] = limit
		stored.append(entry)
	return stored


# ============================================================
def active_effects(stored: list | None) -> list[Effect] :
	"""The catalog entries of an active ability's effects; keys no longer in the catalog are left out."""
	return [effect for effect in (EffectCatalog.get(key) for key in keys(stored)) if effect is not None]


# ============================================================
def passive_effects(stored: list | None) -> list[Effect] :
	return [effect for effect in (PassiveCatalog.get(key) for key in keys(stored)) if effect is not None]


# ============================================================
def ap(tier: str, stored: list | None) -> int :
	"""What using an active ability costs."""
	return Effects.ap_cost(tier, active_effects(stored))


# ============================================================
def check_active(kind: str, tier: str, effects: list[Effect], school_stat: str | None, stat: str | None) -> str | None :
	"""Why the parts don't make a valid active ability, or None. school_stat is the casting stat of the spell's school
	(None when it has none)."""
	if kind not in KINDS :
		return f"The kind must be {' or '.join(KINDS)}."
	if kind == SPELL :
		if school_stat is None :
			return "A spell needs an approved magic school."
		if stat != school_stat :
			return f"Spells of this school use {school_stat.capitalize()}."
	return Effects.check(kind, tier, effects)


# == slots ==

# ============================================================
def slots(passive: bool) -> int :
	"""How many ability slots an ability takes: an active one 1, a passive one 2."""
	return PASSIVE_SLOTS if passive else 1


# ============================================================
def overflow(known: list[tuple]) -> int :
	"""How many slots over the normal limits a set of (kind, tier) or (kind, tier, passive) is. Spell passives take a
	spell slot of their tier like any spell."""
	spells = [entry[1] for entry in known if entry[0] == SPELL]
	abilities = [entry for entry in known if entry[0] == ABILITY]
	extra = sum(max(0, spells.count(tier) - limit) for tier, limit in SPELL_SLOTS.items())
	used = sum(slots(len(entry) > 2 and bool(entry[2])) for entry in abilities)
	strong = len([entry for entry in abilities if entry[1] == STRONG])
	extra += max(0, used - ABILITY_SLOTS) + max(0, strong - ABILITY_STRONG_SLOTS)
	return extra


# ============================================================
def check_learn(known: list[tuple], kind: str, tier: str, legendary: bool, passive: bool = False) -> str | None :
	"""Why a character can't learn another ability, or None. known holds (kind, tier, event) or (kind, tier, event,
	passive) for what it knows; event abilities don't count. Spellcasters and ability users can't mix, a passive
	ability takes two of the three ability slots, a spell passive one spell slot, and legendary characters get one
	extra slot."""
	counted = [(entry[0], entry[1], len(entry) > 3 and bool(entry[3])) for entry in known if not entry[2]]
	if kind == SPELL and any(known_kind == ABILITY for known_kind, _, _ in counted) :
		return "A character with abilities can't learn spells (unless an event grants them)."
	if kind == ABILITY and any(known_kind == SPELL for known_kind, _, _ in counted) :
		return "A spellcaster can't learn abilities (unless an event grants them)."
	allowed = LEGENDARY_EXTRA_SLOTS if legendary else 0
	if overflow(counted + [(kind, tier, passive)]) > allowed :
		if kind == SPELL :
			return (f"Spellcasters know at most {SPELL_SLOTS[CANTRIP]} Cantrip, {SPELL_SLOTS[WEAK]} Weak, "
			        f"{SPELL_SLOTS[NORMAL]} Normal and {SPELL_SLOTS[STRONG]} Strong spell (passive spells take a "
			        f"slot of their tier too)"
			        f"{', plus one of any tier for legendary characters' if legendary else ''}.")
		return (f"A character has {ABILITY_SLOTS} ability slots (an active ability takes 1, a passive "
		        f"{PASSIVE_SLOTS}) and at most {ABILITY_STRONG_SLOTS} Strong"
		        f"{' (plus one slot for legendary characters)' if legendary else ''}.")
	return None


# == describing ==

# ============================================================
def summary(kind: str, tier: str, stat: str, stored: list | None, damage_type: str | None = None,
            passive: bool = False) -> str :
	"""The rules of an ability: a head line (tier, AP, uses) and one line per effect."""
	if passive :
		target, limit = options(stored)
		return Passives.describe(kind, tier, passive_effects(stored), target, limit)
	return Effects.summary(kind, tier, stat, active_effects(stored), damage_type)


# ============================================================
def short(kind: str, tier: str, stored: list | None, passive: bool = False) -> str :
	"""One line like `Normal spell · 6 AP · Pyrokinesis, Widened`."""
	if passive :
		effects = passive_effects(stored)
		head = f"{tier.capitalize()} passive {kind} · -{Passives.ap_cost(tier, effects)} AP"
	else :
		effects = active_effects(stored)
		head = f"{tier.capitalize()} {kind} · {Effects.ap_cost(tier, effects)} AP"
	return head + (" · " + ", ".join(effect.name for effect in effects) if effects else " · no effects yet")
