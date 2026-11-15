"""Turns a character or a bestiary entry into a combatant: the snapshot of stats, weapons, armor and abilities a fight
uses, and the derived numbers (HP, AP, AC, DT, Sequence).

The snapshot is taken when the combatant joins, so changing gear mid-fight does not change the fight.
"""
from classes.combat import Abilities as AbilityRules
from classes.combat import Effects, Items, Passives, Rules
from classes.combat.State import AUTO, CHARACTER, Combatant, NPC, PLAYER
from classes.kernel.ConfigData import ConfigData
from database.database import Bestiary, Characters
from resources.configs.ConfigMapping import ConfigMapping

NATURAL_KEY = "natural"
# Sheet answers for armor proficiency, mapped onto armor classes.
SHEET_ARMOR = {"unarmored" : Rules.CLOTHING, "none" : Rules.CLOTHING, "clothing" : Rules.CLOTHING,
               "light" : Rules.LIGHT, "medium" : Rules.MEDIUM, "heavy" : Rules.HEAVY}
SHEET_ARMOR_LABEL = "armor proficiency"

MINION = "minion"
STANDARD = "standard"
ELITE = "elite"
MINIBOSS = Rules.MINIBOSS
BOSS = Rules.BOSS
CUSTOM = "custom"
# preset: (HP, AC, DT, to hit, damage, AP). Minibosses and bosses start at 75 HP; the fight sets their HP from the
# number of player characters they face (Rules.boss_hp). A boss's 14 AP lets it act twice.
PRESETS = {
	MINION   : (8, 10, 0, 1, "1d6", 7),
	STANDARD : (20, 12, 1, 2, "2d6", 7),
	ELITE    : (40, 14, 2, 4, "2d8", 7),
	MINIBOSS : (Rules.BOSS_BASE_HP, 14, 2, 4, "2d8", 10),
	BOSS     : (Rules.BOSS_BASE_HP, 15, 3, 5, "3d8", 14),
}


# ============================================================
def preset_text(preset: str) -> str :
	"""`HP 20 · AC 12 · DT 1 · +2 · 2d6 · AP 7`, with the scaling HP of minibosses and bosses."""
	hp, ac, dt, to_hit, damage, ap = PRESETS[preset]
	hp_text = Rules.rank_text(preset) if preset in Rules.RANKS else str(hp)
	return f"HP {hp_text} · AC {ac} · DT {dt} · {to_hit:+d} · {damage} · AP {ap}"


# ============================================================
def rank_of(text: str | None) -> str | None :
	"""A rank typed by a GM (miniboss, mini, boss), or None for a normal NPC."""
	text = (text or "").strip().lower()
	if text.startswith("mini") :
		return MINIBOSS
	if text.startswith("boss") :
		return BOSS
	return None


class Loadout :

	# ============================================================
	@staticmethod
	def armor_proficiency(character: Characters) -> str | None :
		"""The character's armor proficiency: its own setting, or its sheet answer, or None (no penalty)."""
		if character.armor_proficiency in Rules.ARMOR_CLASSES :
			return character.armor_proficiency
		from database.transactions.CharacterInfoTransactions import CharacterInfoTransactions

		for info in CharacterInfoTransactions().get_all(character.id) :
			if info.key.strip().lower() == SHEET_ARMOR_LABEL :
				return SHEET_ARMOR.get((info.value or "").strip().lower())
		return None

	# ============================================================
	@staticmethod
	def abilities(character_id: int) -> list[dict] :
		"""The approved (or event-granted) abilities a character knows, as the fight uses them."""
		from database.transactions.AbilityTransactions import APPROVED, AbilityTransactions

		known = []
		for link, ability in AbilityTransactions().known(character_id) :
			if ability.state != APPROVED and not link.event :
				continue
			known.append(Loadout.ability_data(ability))
		return known

	# ============================================================
	@staticmethod
	def ability_data(ability) -> dict :
		"""An ability record as the fight uses it (see Abilities.fight_data)."""
		passive = (getattr(ability, "activation", None) or "active") == "passive"
		return AbilityRules.fight_data(ability.id, ability.name, ability.kind, ability.tier, ability.stat,
		                               ability.damage_type, ability.effects, passive)

	# ============================================================
	@staticmethod
	def split(abilities: list[dict]) -> tuple[list[dict], list[dict]] :
		"""Abilities as the fight uses them: the active ones (with at least one effect), and the passive ones as their
		entries."""
		actives, passives = [], []
		for ability in abilities :
			if ability.get("activation") == "passive" :
				passives += ability.get("entries") or []
			elif ability.get("effects") :
				actives.append(ability)
		return actives, passives

	# ============================================================
	@staticmethod
	def apply_passives(combatant: Combatant) -> Combatant :
		"""Adds the passives' join bonuses (max HP, AC within the cap, DT, Sequence) to a new combatant and takes away
		the AP they cost (it keeps at least the minimum AP)."""
		passives = combatant.stats.get("passives") or []
		hp = Passives.join_bonus(passives, Passives.HP)
		ac = Passives.join_bonus(passives, Passives.AC)
		combatant.hp += hp
		combatant.hp_max += hp
		penalty = Passives.ap_penalty(passives)
		if penalty :
			combatant.ap_max = max(Rules.AP_MINIMUM, combatant.ap_max - penalty)
			combatant.ap = min(combatant.ap, combatant.ap_max)
		if ac :
			combatant.ac = max(combatant.ac, min(Rules.AC_CAP, combatant.ac + ac))
		combatant.dt += Passives.join_bonus(passives, Passives.DT)
		combatant.sequence += Passives.join_bonus(passives, Passives.SEQUENCE)
		return combatant

	# ============================================================
	@staticmethod
	def character_stats(character: Characters) -> dict :
		"""The snapshot of a character: SPECIAL, level, weapons (with proficiency), armor, shield and abilities."""
		from classes.characters.Special import Special
		from classes.gear.Gear import ARMOR, CONSUMABLE, Gear, WEAPON

		base = Special.rules(character.guild_id).base
		special = {stat : int(getattr(character, stat) or 0) for stat in Rules.STATS}
		crippled_strength = special["strength"] <= 0
		weapons, shield, armor, items = [], False, None, []
		for entry, item in Gear.inventory(character.id) :
			combat = item.combat if item is not None else {}
			requirements = item.requirements if item is not None else {}
			if entry.kind == WEAPON :
				weapon = Rules.normalise_weapon(combat)
				if crippled_strength and "two_handed" in weapon["properties"] :
					continue
				weapon.update({"key" : f"gear:{entry.id}", "name" : entry.name, "entry_id" : entry.id,
				               "proficiency" : entry.proficiency or Rules.AWFUL,
				               "requirement_penalty" : Rules.unmet_penalty(special, requirements),
				               "equipped" : bool(entry.equipped)})
				if "shield" in weapon["properties"] and entry.equipped :
					shield = True
				weapons.append(weapon)
			elif entry.kind == CONSUMABLE :
				items.append(Items.snapshot(entry.id, entry.name, combat))
			elif entry.kind == ARMOR and entry.equipped :
				candidate = Rules.normalise_armor(combat) | {"name" : entry.name}
				if crippled_strength and candidate["armor_class"] == Rules.HEAVY :
					continue
				armor = candidate
		weapons.append(dict(Rules.UNARMED))
		armor = armor or (dict(Rules.ARMOR_DEFAULTS) | {"name" : "No armor"})
		actives, passives = Loadout.split(Loadout.abilities(character.id))
		level_bonus = Rules.level_bonus(character.level) if ConfigData().get_toggle(
			character.guild_id, ConfigMapping.COMBAT_LEVEL_BONUS) else 0
		luck = special["luck"]
		return {"base" : base, "special" : special, "level" : int(character.level or 1),
		        "legendary" : bool(getattr(character, "legendary", False)), "weapons" : weapons, "armor" : armor,
		        "shield" : shield, "armor_penalty" : Rules.armor_penalty(armor["armor_class"],
		                                                                  Loadout.armor_proficiency(character)),
		        "level_bonus" : level_bonus, "abilities" : actives, "passives" : passives, "items" : items,
		        "bad_streak" : int(getattr(character, "bad_streak", 0) or 0),
		        "crit_min" : Rules.crit_min(luck), "fumble_max" : Rules.fumble_max(luck), "confirm_crits" : luck <= 0,
		        "crippled" : Rules.crippled(special)}

	# ============================================================
	@staticmethod
	def default_weapon(weapons: list[dict]) -> str | None :
		"""The weapon a combatant starts the fight holding: an equipped one (not a shield), else the first."""
		usable = [weapon for weapon in weapons if "shield" not in (weapon.get("properties") or [])]
		equipped = [weapon for weapon in usable if weapon.get("equipped")]
		chosen = (equipped or usable or weapons or [None])[0]
		return chosen.get("key") if chosen else None

	# ============================================================
	@staticmethod
	def for_character(character: Characters, side_id: int, position: int = 0) -> Combatant :
		stats = Loadout.character_stats(character)
		special, base = stats["special"], stats["base"]
		hp = Rules.hp_max(special, stats["level"], base)
		ap = Rules.ap_max(special)
		return Loadout.apply_passives(Combatant(
			id=0, side_id=side_id, kind=CHARACTER, name=character.name, stats=stats, character_id=character.id,
			uid=character.uid, controller=PLAYER, behavior="weakest", hp=hp, hp_max=hp, ap=ap, ap_max=ap,
			ac=Rules.armor_class(special, stats["armor"], stats["shield"], base), dt=int(stats["armor"].get("dt") or 0),
			sequence=Rules.sequence(special), weapon_key=Loadout.default_weapon(stats["weapons"]), position=position))

	# ============================================================
	@staticmethod
	def npc_stats(hp: int, ac: int, dt: int, to_hit: int, damage: str, damage_type: str | None, attack_name: str,
	              ap: int, abilities: list[dict] | None = None, rewards: dict | None = None,
	              preset: str = CUSTOM) -> dict :
		weapon = {"key" : NATURAL_KEY, "name" : attack_name or "Attack", "type" : damage_type, "dice" : damage,
		          "to_hit" : int(to_hit), "range" : Rules.MELEE, "properties" : [], "ap" : 3}
		actives, passives = Loadout.split(abilities or [])
		return {"npc" : True, "base" : 5, "special" : {}, "level" : 1, "weapons" : [weapon],
		        "armor" : {"name" : "Natural", "armor_class" : Rules.CLOTHING, "ac" : 0, "dt" : int(dt)},
		        "abilities" : actives, "passives" : passives, "ability_mod" : int(to_hit), "crit_min" : 20, "fumble_max" : 1,
		        "rewards" : rewards or {}, "preset" : preset}

	# ============================================================
	@staticmethod
	def for_bestiary(entry: Bestiary, side_id: int, name: str | None = None, position: int = 0,
	                 controller: str = AUTO, rank: str | None = None) -> Combatant :
		"""An NPC from the bestiary. rank makes it a miniboss or boss (an entry with that preset already is one)."""
		combatant = Loadout._for_bestiary(entry, side_id, name, position, controller)
		rank = rank or (entry.preset if entry.preset in Rules.RANKS else None)
		if rank :
			combatant.stats["rank"] = rank
		return combatant

	# ============================================================
	@staticmethod
	def _for_bestiary(entry: Bestiary, side_id: int, name: str | None, position: int, controller: str) -> Combatant :
		from database.transactions.AbilityTransactions import AbilityTransactions

		abilities = [Loadout.ability_data(ability) for ability in
		             (AbilityTransactions().get(ability_id) for ability_id in entry.ability_ids or []) if ability]
		if entry.special :
			return Loadout.for_special_entry(entry, side_id, name or entry.name, position, controller, abilities)
		stats = Loadout.npc_stats(entry.hp, entry.ac, entry.dt, entry.to_hit, entry.damage, entry.damage_type,
		                          entry.attack_name, entry.ap, abilities,
		                          {"xp" : entry.reward_xp, "currency" : entry.reward_currency}, entry.preset)
		stats["avatar_url"] = entry.avatar_url
		return Loadout.apply_passives(Combatant(
			id=0, side_id=side_id, kind=NPC, name=name or entry.name, stats=stats, bestiary_id=entry.id,
			controller=controller, behavior=entry.behavior or "aggressive", hp=entry.hp, hp_max=entry.hp, ap=entry.ap,
			ap_max=entry.ap, ac=entry.ac, dt=entry.dt, sequence=entry.sequence, weapon_key=NATURAL_KEY,
			position=position))

	# ============================================================
	@staticmethod
	def special_stats(guild_id: int, special: dict, level: int, weapon_items: list, armor_item,
	                  abilities: list[dict], rewards: dict | None = None) -> dict :
		"""The snapshot of a bestiary entry built from SPECIAL: derived like a character's, with catalog weapons
		(Average proficiency) and armor it is trained for."""
		base = 5
		special = {stat : int(special.get(stat, base)) for stat in Rules.STATS}
		crippled_strength = special["strength"] <= 0
		weapons, shield = [], False
		for item in weapon_items :
			weapon = Rules.normalise_weapon(item.combat)
			if crippled_strength and "two_handed" in weapon["properties"] :
				continue
			weapon.update({"key" : f"catalog:{item.id}", "name" : item.name, "proficiency" : Rules.AVERAGE,
			               "requirement_penalty" : Rules.unmet_penalty(special, item.requirements),
			               "equipped" : True})
			shield = shield or "shield" in weapon["properties"]
			weapons.append(weapon)
		weapons.append(dict(Rules.UNARMED))
		armor = dict(Rules.ARMOR_DEFAULTS) | {"name" : "No armor"}
		if armor_item is not None :
			candidate = Rules.normalise_armor(armor_item.combat) | {"name" : armor_item.name}
			if not (crippled_strength and candidate["armor_class"] == Rules.HEAVY) :
				armor = candidate
		level_bonus = Rules.level_bonus(level) if ConfigData().get_toggle(guild_id,
		                                                                  ConfigMapping.COMBAT_LEVEL_BONUS) else 0
		luck = special["luck"]
		actives, passives = Loadout.split(abilities)
		return {"base" : base, "special" : special, "level" : int(level or 1), "legendary" : False,
		        "weapons" : weapons, "armor" : armor, "shield" : shield, "armor_penalty" : 0,
		        "level_bonus" : level_bonus, "abilities" : actives, "passives" : passives, "items" : [],
		        "crit_min" : Rules.crit_min(luck), "fumble_max" : Rules.fumble_max(luck), "confirm_crits" : luck <= 0,
		        "crippled" : Rules.crippled(special), "rewards" : rewards or {}, "preset" : "special"}

	# ============================================================
	@staticmethod
	def for_special_entry(entry: Bestiary, side_id: int, name: str, position: int, controller: str,
	                      abilities: list[dict]) -> Combatant :
		from database.transactions.GearItemTransactions import GearItemTransactions

		items = GearItemTransactions()
		weapons = [item for item in (items.get(item_id) for item_id in entry.weapon_ids or []) if item is not None]
		armor = items.get(entry.armor_id) if entry.armor_id else None
		stats = Loadout.special_stats(entry.guild_id, entry.special or {}, entry.level or 1, weapons, armor, abilities,
		                              {"xp" : entry.reward_xp, "currency" : entry.reward_currency})
		stats["avatar_url"] = entry.avatar_url
		special, base = stats["special"], stats["base"]
		hp = Rules.hp_max(special, stats["level"], base)
		ap = Rules.ap_max(special)
		return Loadout.apply_passives(Combatant(
			id=0, side_id=side_id, kind=NPC, name=name, stats=stats, bestiary_id=entry.id, controller=controller,
			behavior=entry.behavior or "aggressive", hp=hp, hp_max=hp, ap=ap, ap_max=ap,
			ac=Rules.armor_class(special, stats["armor"], stats["shield"], base), dt=int(stats["armor"].get("dt") or 0),
			sequence=Rules.sequence(special), weapon_key=Loadout.default_weapon(stats["weapons"]), position=position))

	# ============================================================
	@staticmethod
	def for_preset(preset: str, name: str, side_id: int, damage_type: str | None = None, position: int = 0,
	               controller: str = AUTO) -> Combatant :
		hp, ac, dt, to_hit, damage, ap = PRESETS[preset]
		stats = Loadout.npc_stats(hp, ac, dt, to_hit, damage, damage_type, "Attack", ap, preset=preset)
		if preset in Rules.RANKS :
			stats["rank"] = preset
		return Combatant(id=0, side_id=side_id, kind=NPC, name=name, stats=stats, controller=controller,
		                 behavior="aggressive", hp=hp, hp_max=hp, ap=ap, ap_max=ap, ac=ac, dt=dt, sequence=10,
		                 weapon_key=NATURAL_KEY, position=position)

	# ============================================================
	@staticmethod
	def weapon_line(stats: dict, weapon: dict) -> str :
		"""`Arming Sword: 2d6 +3, +4 to hit, 3 AP (Slashing)`"""
		bonus = sum(b.value for b in Rules.weapon_bonuses(stats, weapon, int(stats.get("base", 5))))
		damage = Rules.damage_bonus(stats, weapon, int(stats.get("base", 5)))
		dice = weapon.get("dice", "1d4") + (f" {damage:+d}" if damage else "")
		kind = f" ({weapon['type']})" if weapon.get("type") else ""
		return f"{weapon.get('name', 'Weapon')}: {dice}, {bonus:+d} to hit, {Rules.weapon_ap(weapon)} AP{kind}"

	# ============================================================
	@staticmethod
	def ability_line(ability: dict) -> str :
		return f"{ability['name']}: {ability.get('summary') or ''}"
