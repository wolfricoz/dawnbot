"""Gear condition, wear after fights and repairs (design/economy.md, phase 2).

Items are Good, Worn, Damaged or Broken. Worn does nothing; Damaged gives a weapon −1 to hit and armor −1 DT (never
below 0); a Broken weapon can't be used and Broken armor gives nothing. Broken items stay in the inventory.

Wear is rolled once per fight, not per attack (GEAR_WEAR, on by default): when a fight ends, the weapon each character
was holding and its worn armor each have a 1 in 20 chance to drop one step, 1 in 40 for masterwork. Worn does nothing,
so a typical item takes about 40 fights to reach Damaged.

Repairs bring an item back to Good: at the shop for 5%, 15% or 40% of its catalog price (Worn, Damaged, Broken; Charisma
changes it like any purchase), or with a day of downtime by a character whose occupation staff marked as repairing that
kind of gear (the better of Agility and Intelligence against DC 10, 13 or 16). A repair by hand uses one unit of a
material the item salvages into when it has a salvage list. Cursed items can't be repaired until a GM lifts the curse.
"""
import random

from classes.checks import Checks
from classes.kernel.ConfigData import ConfigData
from database.database import CharacterGear, Characters, GearItems
from resources.configs.ConfigMapping import ConfigMapping

GOOD = "good"
WORN = "worn"
DAMAGED = "damaged"
BROKEN = "broken"
STEPS = [GOOD, WORN, DAMAGED, BROKEN]
LABELS = {GOOD : "Good", WORN : "Worn", DAMAGED : "Damaged", BROKEN : "Broken"}
WEAR_CHANCE = 20
MASTERWORK_WEAR_CHANCE = 40
REPAIR_SHARE = {WORN : 0.05, DAMAGED : 0.15, BROKEN : 0.40}
REPAIR_DC = {WORN : 10, DAMAGED : 13, BROKEN : 16}
# The kinds of gear an occupation can be set to repair: weapons, armor by its class, and accessories.
REPAIR_KINDS = ["weapon", "clothing", "light", "medium", "heavy", "accessory"]
REPAIR_STATS = ["agility", "intelligence"]


# ============================================================
def of(entry: CharacterGear) -> str :
	condition = getattr(entry, "condition", None)
	return condition if condition in STEPS else GOOD


# ============================================================
def label(condition: str) -> str :
	return LABELS.get(condition, str(condition).capitalize())


# ============================================================
def worse(condition: str) -> str :
	return STEPS[min(len(STEPS) - 1, STEPS.index(condition) + 1)]


# ============================================================
def adjust(kind: str, combat: dict, condition: str) -> dict | None :
	"""Combat values after condition: Damaged −1 to hit or −1 DT; None for a Broken item, which a fight leaves out."""
	if condition == BROKEN :
		return None
	if condition != DAMAGED :
		return combat
	combat = dict(combat)
	if kind == "weapon" :
		combat["hit_mod"] = int(combat.get("hit_mod") or 0) - 1
	elif kind == "armor" :
		combat["dt"] = max(0, int(combat.get("dt") or 0) - 1)
	return combat


# == wear ==

# ============================================================
def wear_on(guild_id: int) -> bool :
	return ConfigData().get_toggle(guild_id, ConfigMapping.GEAR_WEAR, default="ENABLED")


# ============================================================
def wear_roll(entry: CharacterGear, rng: random.Random | None = None) -> bool :
	"""True when the item drops a step this fight."""
	if of(entry) == BROKEN :
		return False
	chance = MASTERWORK_WEAR_CHANCE if getattr(entry, "quality", None) == "masterwork" else WEAR_CHANCE
	return (rng or random).randint(1, chance) == 1


# ============================================================
def wear(entry_ids: list[int], rng: random.Random | None = None) -> list[tuple[CharacterGear, str]] :
	"""Rolls wear for these items and saves it: [(entry, new condition)] for the ones that wore down."""
	from database.transactions.CharacterGearTransactions import CharacterGearTransactions, OWNED

	worn = []
	transactions = CharacterGearTransactions()
	for entry_id in dict.fromkeys(entry_ids) :
		entry = transactions.get(entry_id)
		if entry is None or entry.status != OWNED or not wear_roll(entry, rng) :
			continue
		condition = worse(of(entry))
		transactions.update(entry.id, condition=condition)
		worn.append((entry, condition))
	return worn


# ============================================================
def fight_items(combatant) -> list[int] :
	"""The gear a character's combatant wears down: the weapon it was holding and its worn armor."""
	ids = []
	key = str(getattr(combatant, "weapon_key", None) or "")
	if key.startswith("gear:") and key[5:].isdigit() :
		ids.append(int(key[5:]))
	armor_id = ((combatant.stats or {}).get("armor") or {}).get("entry_id")
	if armor_id :
		ids.append(int(armor_id))
	return ids


# ============================================================
def after_fight(fight, rng: random.Random | None = None) -> list[str] :
	"""Wears down the characters' gear when a fight ends and runs their ammunition down; returns lines to post."""
	from classes.gear import Carry
	from database.transactions.CharacterTransactions import CharacterTransactions

	lines = []
	wearing = wear_on(fight.guild_id)
	for combatant in fight.combatants :
		if not combatant.character_id or combatant.state == "removed" :
			continue
		character = CharacterTransactions().get_by_id(combatant.character_id)
		if character is None :
			continue
		if wearing :
			for entry, condition in wear(fight_items(combatant), rng) :
				lines.append(f"🔧 {character.name}'s **{entry.name}** is now {label(condition).lower()}.")
		lines += [f"🏹 {character.name}: {line}" for line in Carry.use_ammo(fight.guild_id, combatant, rng)]
		# Daily charges of magic items used in this fight are spent (classes/gear/Magic.py).
		from classes.gear import Magic

		for key, used in (getattr(combatant, "ability_uses", None) or {}).items() :
			if str(key).startswith("item:") and str(key)[5:].isdigit() :
				Magic.spend_charges(int(str(key)[5:]), int(used or 0))
	return lines


# == repairs ==

# ============================================================
def repair_kind(entry: CharacterGear, item: GearItems | None) -> str :
	"""What kind of repair an item needs: weapon, accessory, or its armor class."""
	if entry.kind == "armor" :
		return ((item.combat or {}) if item is not None else {}).get("armor_class") or "light"
	return entry.kind


# ============================================================
def repair_problem(entry: CharacterGear) -> str | None :
	if entry.status != "owned" :
		return f"{entry.name} is {entry.status}."
	if of(entry) == GOOD :
		return f"{entry.name} is in good condition already."
	if getattr(entry, "quality", None) == "cursed" :
		return f"The curse on {entry.name} has to be lifted by a GM before it can be repaired."
	return None


# ============================================================
def shop_price(entry: CharacterGear, item: GearItems | None, character: Characters) -> int :
	"""What the shop charges to repair the item: a share of its catalog price by condition, through Charisma."""
	from classes.gear import Pricing

	if not Pricing.economy(character.guild_id) :
		return 0
	base = Pricing.base_value(entry, item)
	return max(1, round(base * REPAIR_SHARE.get(of(entry), 0) * Pricing.buy_multiplier(character))) if base else 0


# ============================================================
def can_repair(repairer: Characters, kind: str) -> bool :
	from database.transactions.OccupationTransactions import OccupationTransactions

	occupation = OccupationTransactions().get(repairer.occupation_id) if repairer.occupation_id else None
	return occupation is not None and kind in (occupation.repairs or [])


# ============================================================
def repair_stat(repairer: Characters) -> str :
	return max(REPAIR_STATS, key=lambda stat : int(getattr(repairer, stat) or 0))


# ============================================================
def material_for(repairer: Characters, item: GearItems | None) -> CharacterGear | None | bool :
	"""The repairer's material the repair uses: one the item salvages into. True when the item needs none (no salvage
	list), None when the repairer has none of them."""
	salvage = (getattr(item, "salvage", None) or {}) if item is not None else {}
	if not salvage :
		return True
	from database.transactions.CharacterGearTransactions import CharacterGearTransactions

	names = {name.lower() for name in salvage}
	return next((entry for entry in CharacterGearTransactions().get_all(repairer.id)
	             if entry.kind == "material" and entry.name.lower() in names and (entry.quantity or 0) > 0), None)


# ============================================================
def use_material(material: CharacterGear) -> None :
	from database.transactions.CharacterGearTransactions import CharacterGearTransactions, USED

	if (material.quantity or 1) > 1 :
		CharacterGearTransactions().update(material.id, quantity=material.quantity - 1)
	else :
		CharacterGearTransactions().update(material.id, status=USED)


# ============================================================
def repair_roll(repairer: Characters, condition: str, rng: random.Random | None = None) :
	"""The repair check: the better of Agility and Intelligence against the condition's DC."""
	from classes.characters.Special import Special

	stat = repair_stat(repairer)
	return stat, Checks.roll(Checks.stats_of(repairer), stat, REPAIR_DC[condition],
	                         base=Special.rules(repairer.guild_id).base, rng=rng)


# ============================================================
def repair_by_hand(repairer: Characters, entry: CharacterGear, item: GearItems | None, owner: Characters,
                   rng: random.Random | None = None) -> tuple[str | None, list[str]] :
	"""A day of downtime repairing an item: (outcome, lines), or (None, [why it can't]) when it can't be tried.

	Success or better brings it back to Good and uses the material; a bad failure or a fumble wastes the material."""
	problem = repair_problem(entry)
	if problem :
		return None, [problem]
	kind = repair_kind(entry, item)
	if not can_repair(repairer, kind) :
		return None, [f"{repairer.name}'s occupation can't repair {kind} gear; staff set what an occupation repairs "
		              f"with /downtime occupation."]
	material = material_for(repairer, item)
	if material is None :
		names = ", ".join(((getattr(item, "salvage", None) or {}) if item is not None else {}).keys())
		return None, [f"{repairer.name} needs one of these to repair {entry.name}: {names}."]
	condition = of(entry)
	stat, result = repair_roll(repairer, condition, rng)
	whose = "its own" if owner.id == repairer.id else f"{owner.name}'s"
	lines = [f"🔧 {repairer.name} repairs {whose} **{entry.name}** ({label(condition).lower()}): "
	         f"{result.breakdown()} on {stat.capitalize()} against {REPAIR_DC[condition]} · "
	         f"{Checks.OUTCOME_LABELS[result.outcome]}"]
	fixed = result.outcome in (Checks.SUCCESS, Checks.STRONG, Checks.CRIT)
	if fixed :
		restore(entry, repairer.uid)
		lines.append(f"**{entry.name}** is as good as new.")
	else :
		lines.append("It isn't fixed yet.")
	if material is not True and (fixed or result.outcome in (Checks.BAD, Checks.FUMBLE)) :
		use_material(material)
		lines.append(f"Used one {material.name}.")
	return result.outcome, lines


# ============================================================
def restore(entry: CharacterGear, actor_uid: int | None = None) -> CharacterGear | None :
	from database.transactions.CharacterGearTransactions import CharacterGearTransactions

	return CharacterGearTransactions().update(entry.id, condition=GOOD, changed_by=actor_uid)
