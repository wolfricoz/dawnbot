"""Magic items: enchantments, attunement, charges and identification (design/economy.md, phase 5).

An enchanted catalog item carries one enchantment built from the effect catalogs abilities use, so there is no second
rules system: `activation` passive (effects from the passive catalog, always on) or active (effects from the effect
catalog, used as an action for AP like an ability, with charges that come back after each fight or each day). It can
also give +1 (`bonus`): +1 to hit for a weapon, +1 DT for armor, on top of masterwork, so an item gives at most +2.

Rarity sets the budget: Uncommon one effect up to Weak; Rare one up to Normal or two up to Weak; Very rare one up to
Strong or two up to Normal; Legendary up to three of any tier (staff decide). The item's tier in a fight follows its
rarity (Uncommon Weak, Rare Normal, Very rare and Legendary Strong). An item's spell effect rolls with the item's own
bonus instead of a stat: Uncommon +3, Rare +4, Very rare +5, Legendary as staff set it (default +6). Item passives cost
no AP; attunement is their limit.

Attunement: an enchanted item only works while attuned, and armor and accessories also while worn. A character can
attune ATTUNEMENT_SLOTS items (3), a legendary character one more. Attuning takes a day of downtime (/gear attune), or
a GM attunes it on the spot (/gm gear attune).

Identification (IDENTIFY, off by default): enchanted loot drops unidentified, shown by its unidentified name and doing
nothing until identified, by attuning it, a day of downtime with Intelligence against 10 + 2 per rarity step, or a
merchant's identify service.
"""
from datetime import datetime, timezone

from classes.combat import Abilities, EffectCatalog, Effects, PassiveCatalog, Passives
from classes.gear import Rarity
from classes.kernel import RoleplaySettings
from database.database import CharacterGear, Characters, GearItems
from database.transactions.CharacterGearTransactions import CharacterGearTransactions
from resources.configs.ConfigMapping import ConfigMapping

PASSIVE = "passive"
ACTIVE = "active"
FIGHT = "fight"
DAY = "day"
TIER_ORDER = Effects.TIERS
# (most effects, highest tier) pairs a rarity allows; any one of them fits.
BUDGETS = {
	Rarity.UNCOMMON  : [(1, Effects.WEAK)],
	Rarity.RARE      : [(1, Effects.NORMAL), (2, Effects.WEAK)],
	Rarity.VERY_RARE : [(1, Effects.STRONG), (2, Effects.NORMAL)],
	Rarity.LEGENDARY : [(3, Effects.STRONG)],
}
ITEM_TIER = {Rarity.UNCOMMON : Effects.WEAK, Rarity.RARE : Effects.NORMAL, Rarity.VERY_RARE : Effects.STRONG,
             Rarity.LEGENDARY : Effects.STRONG}
ITEM_BONUS = {Rarity.UNCOMMON : 3, Rarity.RARE : 4, Rarity.VERY_RARE : 5, Rarity.LEGENDARY : 6}
IDENTIFY_DC = {Rarity.COMMON : 10, Rarity.UNCOMMON : 12, Rarity.RARE : 14, Rarity.VERY_RARE : 16,
               Rarity.LEGENDARY : 18}


# == the enchantment ==

# ============================================================
def of(item: GearItems | None) -> dict :
	return dict((getattr(item, "enchantments", None) or {}) if item is not None else {})


# ============================================================
def enchanted(item: GearItems | None) -> bool :
	data = of(item)
	return bool(data.get("effects") or data.get("bonus"))


# ============================================================
def effects_of(data: dict) -> list :
	stored = data.get("effects") or []
	return Abilities.passive_effects(stored) if data.get("activation") == PASSIVE else Abilities.active_effects(stored)


# ============================================================
def lookup(activation: str, key: str) :
	return (PassiveCatalog if activation == PASSIVE else EffectCatalog).get(key)


# ============================================================
def check(rarity: str, data: dict) -> str | None :
	"""Why an enchantment doesn't fit its rarity, or None."""
	keys = Abilities.keys(data.get("effects"))
	if not keys and not data.get("bonus") :
		return "An enchantment needs an effect or the +1 bonus."
	if rarity == Rarity.COMMON :
		return "Common items can't be enchanted; give the item a rarity of Uncommon or higher."
	activation = data.get("activation") or ACTIVE
	if activation not in (ACTIVE, PASSIVE) :
		return "An enchantment is active or passive."
	effects = [lookup(activation, key) for key in keys]
	unknown = [key for key, effect in zip(keys, effects) if effect is None]
	if unknown :
		return f"Unknown {activation} effects: {', '.join(unknown)}."
	if not effects :
		return None
	highest = max(TIER_ORDER.index(effect.tier) if effect.tier in TIER_ORDER else 0 for effect in effects)
	if not any(len(effects) <= most and highest <= TIER_ORDER.index(tier) for most, tier in BUDGETS[rarity]) :
		allowed = " or ".join(f"{most} up to {tier.capitalize()}" for most, tier in BUDGETS[rarity])
		return f"A {Rarity.label(rarity)} item can have {allowed}."
	charges = data.get("charges")
	if charges is not None and not 1 <= int(charges) <= 10 :
		return "Charges go from 1 to 10."
	return None


# ============================================================
def build(activation: str, effect_texts: list[str | None], charges: int | None = None, recharge: str | None = None,
          bonus: bool = False, item_bonus: int | None = None, damage_type: str | None = None) -> tuple[dict | None,
                                                                                                    str | None] :
	"""An enchantment from what staff or a player typed (effects by key or name), or None and why not. The budget is
	checked separately with check()."""
	catalog = PassiveCatalog if activation == PASSIVE else EffectCatalog
	effects = []
	for text in [text for text in effect_texts if text] :
		effect = catalog.find(text)
		if effect is None :
			return None, f"There is no {activation} effect called {text}."
		effects.append(effect)
	data = {"activation" : activation, "effects" : Abilities.store(effects), "bonus" : bool(bonus)}
	if activation == ACTIVE and charges :
		data["charges"] = int(charges)
		data["recharge"] = DAY if recharge == DAY else FIGHT
	if item_bonus is not None :
		data["item_bonus"] = int(item_bonus)
	if damage_type :
		data["damage_type"] = damage_type
	return data, None


# ============================================================
def describe(item: GearItems | None) -> str :
	"""`Active (2 charges a day): Firebolt, Widened · +1` and the like; empty for a plain item."""
	data = of(item)
	if not enchanted(item) :
		return ""
	parts = []
	effects = effects_of(data)
	if effects :
		head = "Passive" if data.get("activation") == PASSIVE else "Active"
		if data.get("activation") != PASSIVE and data.get("charges") :
			head += f" ({data['charges']} charges a {'day' if data.get('recharge') == DAY else 'fight'})"
		parts.append(f"{head}: {', '.join(effect.name for effect in effects)}")
	if data.get("bonus") :
		parts.append("+1 to hit" if item.kind == "weapon" else "+1 DT" if item.kind == "armor" else "+1")
	return " · ".join(parts)


# ============================================================
def item_bonus(item: GearItems) -> int :
	rarity = Rarity.of(item)
	return int(of(item).get("item_bonus") or ITEM_BONUS.get(rarity, 3))


# == attunement ==

# ============================================================
def slots(character: Characters) -> int :
	return RoleplaySettings.number(character.guild_id, ConfigMapping.ATTUNEMENT_SLOTS) + \
	       (1 if getattr(character, "legendary", False) else 0)


# ============================================================
def attuned(character: Characters) -> list[CharacterGear] :
	return [entry for entry in CharacterGearTransactions().get_all(character.id) if entry.attuned]


# ============================================================
def attune_problem(character: Characters, entry: CharacterGear, item: GearItems | None) -> str | None :
	if entry.character_id != character.id or entry.status != "owned" :
		return f"{entry.name} isn't in {character.name}'s inventory."
	if entry.attuned :
		return f"{character.name} is already attuned to {entry.name}."
	if not enchanted(item) :
		return f"{entry.name} isn't a magic item."
	used = len(attuned(character))
	if used >= slots(character) :
		return f"{character.name} is attuned to {used} items already, the most it can be; unattune one first."
	return None


# ============================================================
def attune(entry: CharacterGear) -> CharacterGear | None :
	"""Attunes an item; attuning also identifies it."""
	return CharacterGearTransactions().update(entry.id, attuned=True, identified=True)


# ============================================================
def unattune(entry: CharacterGear) -> CharacterGear | None :
	"""Ends attunement. A cursed item won't let go until a GM lifts the curse (returns None)."""
	if getattr(entry, "quality", None) == "cursed" :
		return None
	return CharacterGearTransactions().update(entry.id, attuned=False)


# ============================================================
def working(entry: CharacterGear, item: GearItems | None) -> bool :
	"""Whether an item's enchantment works now: attuned, identified, and worn when it is armor or an accessory."""
	if not enchanted(item) or not entry.attuned or not getattr(entry, "identified", True) :
		return False
	return entry.kind == "weapon" or bool(entry.equipped)


# == charges ==

# ============================================================
def today() -> str :
	return datetime.now(timezone.utc).date().isoformat()


# ============================================================
def charges(entry: CharacterGear, item: GearItems | None, day: str | None = None) -> int | None :
	"""The uses an active enchantment has: per fight, its charges (plus any extra); per day, what is left today.
	None for an enchantment without charges (it uses its tier's usual uses)."""
	data = of(item)
	total = data.get("charges")
	if total is None :
		return None
	total = int(total) + int(getattr(entry, "extra_charges", 0) or 0)
	if data.get("recharge") != DAY :
		return total
	if getattr(entry, "charges_day", None) != (day or today()) or entry.charges_left is None :
		return total
	return max(0, int(entry.charges_left))


# ============================================================
def spend_charges(entry_id: int, used: int, day: str | None = None) -> None :
	"""Counts a fight's uses of a daily enchantment against today's charges."""
	from database.transactions.GearItemTransactions import GearItemTransactions

	entry = CharacterGearTransactions().get(entry_id)
	item = GearItemTransactions().get(entry.gear_item_id) if entry is not None else None
	if entry is None or of(item).get("recharge") != DAY or used <= 0 :
		return
	left = charges(entry, item, day)
	if left is None :
		return
	CharacterGearTransactions().update(entry.id, charges_left=max(0, left - used), charges_day=day or today())


# == fights ==

# ============================================================
def fight_key(entry_id: int) -> str :
	return f"item:{entry_id}"


# ============================================================
def fight_ability(entry: CharacterGear, item: GearItems) -> dict | None :
	"""An active enchantment as the fight uses it: an ability with the item's tier, its own bonus instead of a stat,
	and its charges as uses."""
	data = of(item)
	if data.get("activation") == PASSIVE or not data.get("effects") :
		return None
	effects = Abilities.active_effects(data["effects"])
	if not effects :
		return None
	tier = ITEM_TIER.get(Rarity.of(item), Effects.WEAK)
	kind = Abilities.SPELL if all(effect.realm == Effects.MAGIC for effect in effects) else Abilities.ABILITY
	ability = Abilities.fight_data(fight_key(entry.id), entry.name, kind, tier, "intelligence",
	                               data.get("damage_type"), data["effects"])
	ability["fixed_bonus"] = item_bonus(item)
	ability["entry_id"] = entry.id
	uses = charges(entry, item)
	if uses is not None :
		ability["uses"] = uses
	return ability


# ============================================================
def fight_passives(entry: CharacterGear, item: GearItems) -> list[dict] :
	"""A passive enchantment's entries; items cost no AP (attunement is their limit)."""
	data = of(item)
	if data.get("activation") != PASSIVE or not data.get("effects") :
		return []
	effects = Abilities.passive_effects(data["effects"])
	tier = ITEM_TIER.get(Rarity.of(item), Effects.WEAK)
	tier = tier if tier in Passives.TIERS else Passives.WEAK
	target, limit = Abilities.options(data["effects"])
	return [found | {"ap_cost" : 0} for found in Passives.entries(fight_key(entry.id), entry.name, tier, effects,
	                                                              target, limit)]


# ============================================================
def plus(entry: CharacterGear, item: GearItems | None) -> int :
	"""The enchantment's +1, when it works."""
	return 1 if working(entry, item) and of(item).get("bonus") else 0


# == identification ==

# ============================================================
def identify_on(guild_id: int) -> bool :
	return RoleplaySettings.toggle(guild_id, ConfigMapping.IDENTIFY)


# ============================================================
def shown_name(entry: CharacterGear, item: GearItems | None) -> str :
	if getattr(entry, "identified", True) or item is None :
		return entry.name
	return item.unidentified_name or f"an unknown {entry.kind}"


# ============================================================
def identify_dc(item: GearItems) -> int :
	return IDENTIFY_DC.get(Rarity.of(item), 12)


# ============================================================
def identify(entry: CharacterGear) -> CharacterGear | None :
	return CharacterGearTransactions().update(entry.id, identified=True)
