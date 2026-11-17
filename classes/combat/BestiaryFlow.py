"""Bestiary entries: checking the values staff type, entries built from SPECIAL with catalog gear, and importing
entries from a genre pack or from the old global npcs and monsters tables.

An entry either has its own stat block (HP, AC, DT, to hit, one attack), filled in from a difficulty preset, or SPECIAL
plus catalog weapons and armor, in which case it is derived like a character (see Loadout.special_stats).
"""
import re

import discord

from classes.characters.Special import STATS
from classes.combat import Rules
from classes.combat.DamageTypes import DamageTypes
from classes.combat.Engine import BEHAVIORS
from classes.combat.Loadout import CUSTOM, PRESETS
from classes.gear.Gear import ARMOR, WEAPON
from classes.gear.Legacy import Legacy
from classes.gear.Packs import Packs
from database.database import Bestiary
from database.transactions.AbilityTransactions import APPROVED, AbilityTransactions
from database.transactions.BestiaryTransactions import BestiaryTransactions
from database.transactions.GearItemTransactions import GearItemTransactions

SPECIAL_MIN = -2
SPECIAL_MAX = 26
LEVEL_MAX = 50
CLEAR = ("", "none", "-")
# Old characters had about 100 HP where the new rules give about 30, so old NPC HP is scaled by this.
LEGACY_HP_SCALE = 0.3
LEGACY_HP_MIN = 5
# The keys a pack's bestiary entry may have besides name and preset.
PACK_KEYS = {"description", "hp", "ac", "dt", "to_hit", "damage", "damage_type", "attack_name", "ap", "sequence",
             "behavior", "reward_xp", "reward_currency", "special", "level", "weapons", "armor", "avatar_url"}


class BestiaryFlow :

	# == values ==

	# ============================================================
	@staticmethod
	def preset_values(preset: str) -> dict :
		hp, ac, dt, to_hit, damage, ap = PRESETS[preset]
		return {"preset" : preset, "hp" : hp, "ac" : ac, "dt" : dt, "to_hit" : to_hit, "damage" : damage, "ap" : ap,
		        "sequence" : 10, "behavior" : "aggressive", "attack_name" : "Attack", "ability_ids" : []}

	# ============================================================
	@staticmethod
	def parse_special(value) -> dict | None :
		"""SPECIAL from seven numbers in order (`6 5 5 4 4 7 5`), from `str 6, agi 7` (the rest are 5), or from a
		dict. `none` clears it (None). Raises ValueError with a message for staff."""
		if isinstance(value, dict) :
			parts = [f"{key} {number}" for key, number in value.items()]
			text = ", ".join(parts)
		else :
			text = str(value or "").strip()
		if text.lower() in CLEAR :
			return None
		numbers = re.findall(r"-?\d+", text)
		if re.fullmatch(r"[\s,;/-]*(-?\d+[\s,;/]+){6}-?\d+[\s,;/]*", text) and len(numbers) == 7 :
			special = {stat : int(number) for stat, number in zip(STATS, numbers)}
		else :
			special = {stat : 5 for stat in STATS}
			for part in re.split(r"[,;\n]+", text) :
				part = part.strip()
				if not part :
					continue
				match = re.fullmatch(r"([A-Za-z]+)\s*[:=]?\s*(-?\d+)", part)
				stat = Packs.stat(match.group(1)) if match else None
				if stat is None and match and match.group(1).lower() in ("lck", "luk") :
					stat = "luck"
				if stat is None :
					raise ValueError(f"I could not read `{part}`. Write SPECIAL as seven numbers (`6 5 5 4 4 7 5`) "
					                 f"or like `str 6, agi 7`.")
				special[stat] = int(match.group(2))
		for stat, number in special.items() :
			if not SPECIAL_MIN <= number <= SPECIAL_MAX :
				raise ValueError(f"{stat.capitalize()} must be from {SPECIAL_MIN} to {SPECIAL_MAX}, not {number}.")
		return special

	# ============================================================
	@staticmethod
	def catalog_items(guild_id: int, names, kind: str) -> list :
		"""Catalog items by name (a list, or text separated by commas). Raises ValueError for unknown names."""
		if isinstance(names, str) :
			names = [part.strip() for part in names.split(",")]
		found = []
		for name in [name for name in names or [] if name and name.strip().lower() not in CLEAR] :
			item = GearItemTransactions().find(guild_id, name.strip())
			if item is None :
				raise ValueError(f"The catalog has no item called {name}; see /armory list.")
			if item.kind != kind :
				raise ValueError(f"{item.name} is {item.kind}, not {'a weapon' if kind == WEAPON else 'armor'}.")
			found.append(item)
		return found

	# ============================================================
	@staticmethod
	def values(guild_id: int, current: dict, **options) -> dict :
		"""The entry's fields with the filled-in options applied. Raises ValueError for bad values."""
		values = dict(current)
		for key, value in options.items() :
			if value is None :
				continue
			if isinstance(value, discord.app_commands.Choice) :
				value = value.value
			if key == "damage" :
				Rules.parse_dice(str(value))
				value = str(value).strip().lower()
			elif key == "damage_type" :
				if str(value).strip().lower() in CLEAR :
					value = None
				else :
					value = next((name for name in DamageTypes.names(guild_id) if name.lower() == value.lower()), None)
					if value is None :
						raise ValueError(f"The server has no damage type called {options[key]}; see /damagetype list.")
			elif key == "abilities" :
				ids = []
				for name in [part.strip() for part in str(value).split(",") if part.strip()] :
					ability = AbilityTransactions().find(guild_id, name)
					if ability is None or ability.state != APPROVED :
						raise ValueError(f"There is no approved ability called {name}.")
					ids.append(ability.id)
				key, value = "ability_ids", ids
			elif key == "behavior" :
				if value not in BEHAVIORS :
					raise ValueError(f"behavior must be one of {', '.join(BEHAVIORS)}.")
			elif key == "special" :
				value = BestiaryFlow.parse_special(value)
			elif key == "level" :
				if not isinstance(value, int) or not 1 <= value <= LEVEL_MAX :
					raise ValueError(f"level must be a whole number from 1 to {LEVEL_MAX}.")
			elif key == "weapons" :
				key, value = "weapon_ids", [item.id for item in BestiaryFlow.catalog_items(guild_id, value, WEAPON)]
			elif key == "armor" :
				items = BestiaryFlow.catalog_items(guild_id, [value] if isinstance(value, str) else value, ARMOR)
				key, value = "armor_id", items[0].id if items else None
			values[key] = value
		return values

	# == showing ==

	# ============================================================
	@staticmethod
	def embed(entry: Bestiary) -> discord.Embed :
		from classes.combat.Loadout import Loadout

		embed = discord.Embed(title=entry.name[:256], description=(entry.description or "")[:4000],
		                      color=discord.Color.dark_red())
		if entry.special :
			combatant = Loadout.for_bestiary(entry, 0)
			special = " · ".join(f"{Rules.STAT_SHORT[stat]} {combatant.special[stat]}" for stat in Rules.STATS)
			weapons = "\n".join(Loadout.weapon_line(combatant.stats, weapon) for weapon in combatant.weapons)
			embed.add_field(name="Stats", inline=False,
			                value=f"{special} · level {entry.level}\nHP {combatant.hp} · AC {combatant.ac} · DT "
			                      f"{combatant.dt} · AP {combatant.ap} · Sequence {combatant.sequence} · "
			                      f"{combatant.stats['armor']['name']}\nBehavior: {entry.behavior}")
			embed.add_field(name="Weapons", value=weapons[:1024], inline=False)
		else :
			attack = f"{entry.attack_name}: {entry.damage}, {entry.to_hit:+d} to hit" + \
			         (f" ({entry.damage_type})" if entry.damage_type else "")
			embed.add_field(name="Stats", inline=False,
			                value=f"HP {entry.hp} · AC {entry.ac} · DT {entry.dt} · AP {entry.ap} · Sequence "
			                      f"{entry.sequence}\n{attack}\nBehavior: {entry.behavior} · preset {entry.preset}")
		abilities = [AbilityTransactions().get(ability_id) for ability_id in entry.ability_ids or []]
		if any(abilities) :
			embed.add_field(name="Abilities", value=", ".join(ability.name for ability in abilities if ability)[:1024],
			                inline=False)
		if entry.reward_xp or entry.reward_currency :
			embed.add_field(name="Rewards", value=f"{entry.reward_xp} XP, {entry.reward_currency} currency")
		if entry.avatar_url :
			embed.set_thumbnail(url=entry.avatar_url)
		return embed

	# ============================================================
	@staticmethod
	def line(entry: Bestiary) -> str :
		if entry.special :
			return f"**{entry.name}** · SPECIAL, level {entry.level} · {entry.behavior}"
		return f"**{entry.name}** · {entry.preset} · HP {entry.hp} · AC {entry.ac} · {entry.damage}"

	# == importing ==

	# ============================================================
	@staticmethod
	def pack_entries(name: str) -> list[dict] :
		"""A pack's bestiary entries, checked for their shape (catalog names are checked when importing)."""
		pack = Packs.load(name)
		entries = pack.get("bestiary") or []
		if not isinstance(entries, list) :
			raise ValueError(f"{name}: bestiary must be a list.")
		checked = []
		for number, entry in enumerate(entries, start=1) :
			if not isinstance(entry, dict) or not isinstance(entry.get("name"), str) or not entry["name"].strip() :
				raise ValueError(f"{name}, bestiary entry #{number}: it needs a name.")
			if entry.get("preset", "standard") not in PRESETS :
				raise ValueError(f"{name}, bestiary entry {entry['name']}: preset must be one of "
				                 f"{', '.join(PRESETS)}.")
			unknown = set(entry) - PACK_KEYS - {"name", "preset", "loot"}
			if unknown :
				raise ValueError(f"{name}, bestiary entry {entry['name']}: unknown keys {', '.join(sorted(unknown))}.")
			checked.append(entry)
		return checked

	# ============================================================
	@staticmethod
	def import_pack(guild_id: int, name: str, creator_uid: int | None) -> tuple[list[Bestiary], list[str], list[str]] :
		"""Copies a pack's bestiary into the server's, leaving out names it already has.

		@return: the entries added, the names skipped, and problems (an entry whose weapons aren't in the catalog
		is added without them).
		"""
		added, skipped, problems = [], [], []
		transactions = BestiaryTransactions()
		for entry in BestiaryFlow.pack_entries(name) :
			if transactions.find(guild_id, entry["name"].strip()) is not None :
				skipped.append(entry["name"])
				continue
			options = {key : entry[key] for key in PACK_KEYS if key in entry}
			try :
				values = BestiaryFlow.values(guild_id, BestiaryFlow.preset_values(entry.get("preset", "standard")),
				                             **options)
			except ValueError as e :
				gear = {key : options.pop(key) for key in ("weapons", "armor") if key in options}
				try :
					values = BestiaryFlow.values(guild_id, BestiaryFlow.preset_values(entry.get("preset", "standard")),
					                             **options)
				except ValueError as second :
					problems.append(f"{entry['name']}: {second}")
					continue
				if gear :
					problems.append(f"{entry['name']}: added without its gear ({e} Import the gear pack first).")
			record = transactions.add(guild_id, entry["name"].strip(), creator_uid=creator_uid, **values)
			if record is None :
				skipped.append(entry["name"])
				continue
			if entry.get("loot") :
				# Loot items the catalog doesn't have are left out (classes/economy/Loot.py).
				from database.transactions.GearItemTransactions import GearItemTransactions

				loot = dict(entry["loot"])
				loot["items"] = [drop for drop in loot.get("items") or []
				                 if GearItemTransactions().find(guild_id, drop.get("name", "")) is not None]
				record = transactions.update(record.id, loot=loot) or record
			added.append(record)
		return added, skipped, problems

	# ============================================================
	@staticmethod
	def convert_legacy(row: dict) -> dict :
		"""An old npcs or monsters row as bestiary values: HP scaled to the new rules, the to-hit bonus read from its
		attack (`1d20+3` gives +3) and the dice from its damage."""
		hp = max(LEGACY_HP_MIN, round(int(row.get("hp") or 0) * LEGACY_HP_SCALE))
		ac = max(1, min(30, int(row.get("ac") or 10)))
		attack = str(row.get("attack") or "")
		bonus = re.search(r"([+-])\s*(\d+)\s*$", attack)
		to_hit = (int(bonus.group(2)) * (1 if bonus.group(1) == "+" else -1)) if bonus else 0
		dice = Rules.DICE.search(str(row.get("damage") or "").lower())
		return {"preset" : CUSTOM, "hp" : hp, "ac" : ac, "dt" : 0, "to_hit" : max(-10, min(30, to_hit)),
		        "damage" : dice.group(0) if dice else "1d6", "ap" : 7, "sequence" : 10, "behavior" : "aggressive",
		        "attack_name" : "Attack", "ability_ids" : []}

	# ============================================================
	@staticmethod
	def import_legacy(guild_id: int, creator_uid: int | None) -> tuple[list[Bestiary], list[str]] :
		"""Copies the old global npcs and monsters into the server's bestiary, leaving out names it already has."""
		added, skipped = [], []
		transactions = BestiaryTransactions()
		for table in ("npcs", "monsters") :
			for row in Legacy.rows(table) :
				name = str(row.get("name") or "").strip()[:100]
				if not name :
					continue
				if transactions.find(guild_id, name) is not None :
					skipped.append(name)
					continue
				record = transactions.add(guild_id, name, creator_uid=creator_uid,
				                          description=f"Imported from the old {table} table.",
				                          **BestiaryFlow.convert_legacy(row))
				(added if record is not None else skipped).append(record if record is not None else name)
		return added, skipped
