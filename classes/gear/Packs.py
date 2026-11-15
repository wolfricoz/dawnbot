"""Genre packs, and the checks every catalog item passes.

A genre pack is a JSON file in resources/data/gear (fantasy.json, ...) with a ready-made list of weapons and armor.
/armory import copies a pack into a server's catalog. The same checks are used for items staff add by hand: SPECIAL
requirements, combat values and prices.
"""
import json
import os
import re

from classes.characters.Special import STATS
from classes.combat import Conditions, Items, Rules
from classes.gear.Gear import ARMOR, CONSUMABLE, KINDS, WEAPON
from database.database import GearItems
from database.transactions.GearItemTransactions import GearItemTransactions

PACK_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "resources",
                        "data", "gear")
PACK_NAME = re.compile(r"[a-z0-9_-]+")

# A requirement is a SPECIAL minimum on this scale (species can raise a stat to 13).
REQUIREMENT_MIN = 1
REQUIREMENT_MAX = 13
NAME_LIMIT = 100
TEXT_FIELDS = ["description", "effect", "effect_met", "effect_unmet"]

# The combat values per kind (see design/combat.md), and what combat uses when an item leaves one out.
WEAPON_COMBAT = {"type" : None, "dice" : "1d6", "attack_stat" : "strength", "damage_stat" : "strength", "hit_mod" : 0,
                 "range" : Rules.MELEE, "properties" : []}
ARMOR_COMBAT = dict(Rules.ARMOR_DEFAULTS)
CONSUMABLE_COMBAT = dict(Items.DEFAULTS)
COMBAT_DEFAULTS = {WEAPON : WEAPON_COMBAT, ARMOR : ARMOR_COMBAT, CONSUMABLE : CONSUMABLE_COMBAT}
KIND_WORDS = {WEAPON : ("weapons", "a weapon"), ARMOR : ("armor", "armor"),
              CONSUMABLE : ("consumables", "a consumable")}
# Weapons may also set their own AP cost.
# Weapons may also set their own AP cost and their kind (which weapon techniques they allow).
OPTIONAL_KEYS = {WEAPON : {"ap", "kind"}, ARMOR : set(), CONSUMABLE : set()}
# Keys of the old shape (before the combat round); values in it are converted.
LEGACY_KEYS = {WEAPON : {"modifier", "hitmodifier"}, ARMOR : {"hp", "ap", "hitchance"}, CONSUMABLE : set()}
DICE = Rules.DICE
HIT_LIMIT = 10
AC_LIMIT = 10
AP_LIMIT = 10
# The pack name recorded on items imported from the old global armors and weapons tables.
LEGACY_PACK = "legacy"


class Packs :

	# == packs ==

	# ============================================================
	@staticmethod
	def available() -> list[tuple[str, str]] :
		"""Every pack in resources/data/gear as (name, title), sorted by name. Files that cannot be read are left
		out."""
		packs = []
		if not os.path.isdir(PACK_DIR) :
			return packs
		for filename in sorted(os.listdir(PACK_DIR)) :
			name, extension = os.path.splitext(filename)
			if extension != ".json" or not PACK_NAME.fullmatch(name) :
				continue
			try :
				with open(os.path.join(PACK_DIR, filename), encoding="utf-8") as file :
					data = json.load(file)
			except (OSError, ValueError) :
				continue
			title = data.get("title") if isinstance(data, dict) else None
			packs.append((name, title if isinstance(title, str) and title else name.capitalize()))
		return packs

	# ============================================================
	@staticmethod
	def load(name: str) -> dict :
		"""Reads and checks a pack. Raises ValueError, saying what is wrong, when it is missing or has bad data."""
		if not isinstance(name, str) or not PACK_NAME.fullmatch(name) :
			raise ValueError(f"There is no gear pack called {name}.")
		path = os.path.join(PACK_DIR, f"{name}.json")
		if not os.path.isfile(path) :
			raise ValueError(f"There is no gear pack called {name}.")
		try :
			with open(path, encoding="utf-8") as file :
				data = json.load(file)
		except (OSError, ValueError) as e :
			raise ValueError(f"The gear pack {name} could not be read: {e}")
		return Packs.validate(data, name)

	# ============================================================
	@staticmethod
	def validate(data, source: str = "pack") -> dict :
		"""Checks a pack's data and returns it with every item complete: text fields present (or None), requirements
		and combat values filled in. Raises ValueError naming the first problem."""
		if not isinstance(data, dict) :
			raise ValueError(f"{source}: a pack must be a JSON object.")
		items = data.get("items")
		if not isinstance(items, list) or not items :
			raise ValueError(f"{source}: a pack needs a non-empty list of items.")
		starting = data.get("starting_currency", 0)
		if not Packs._is_int(starting) or starting < 0 :
			raise ValueError(f"{source}: starting_currency must be a whole number of 0 or more.")
		checked = []
		seen = set()
		for number, item in enumerate(items, start=1) :
			label = item.get("name") if isinstance(item, dict) and isinstance(item.get("name"), str) else f"#{number}"
			try :
				item = Packs.validate_item(item)
			except ValueError as e :
				raise ValueError(f"{source}, item {label}: {e}")
			if item["name"].lower() in seen :
				raise ValueError(f"{source}: the name {item['name']} is used twice.")
			seen.add(item["name"].lower())
			checked.append(item)
		return data | {"name" : data.get("name") or source, "title" : data.get("title") or source.capitalize(),
		               "starting_currency" : starting, "items" : checked}

	# ============================================================
	@staticmethod
	def validate_item(item) -> dict :
		"""Checks one item and returns a complete copy. Raises ValueError saying what is wrong."""
		if not isinstance(item, dict) :
			raise ValueError("an item must be a JSON object.")
		kind = item.get("kind")
		if kind not in KINDS :
			raise ValueError(f"kind must be one of {', '.join(KINDS)}, not {kind!r}.")
		name = item.get("name")
		if not isinstance(name, str) or not name.strip() or len(name.strip()) > NAME_LIMIT :
			raise ValueError(f"name must be text of 1 to {NAME_LIMIT} characters.")
		price = item.get("price", 0)
		if not Packs._is_int(price) or price < 0 :
			raise ValueError(f"price must be a whole number of 0 or more, not {price!r}.")
		checked = {"kind" : kind, "name" : name.strip(), "price" : price}
		for field in TEXT_FIELDS :
			value = item.get(field)
			if value is not None and not isinstance(value, str) :
				raise ValueError(f"{field} must be text.")
			checked[field] = (value.strip() or None) if value is not None else None
		checked["requirements"] = Packs.validate_requirements(item.get("requirements") or {})
		combat = item.get("combat") or {}
		if not isinstance(combat, dict) :
			raise ValueError("combat must be a JSON object.")
		if kind == WEAPON and "damage_stat" in combat and combat["damage_stat"] is None :
			# In a pack, null means no damage stat (bows, crossbows); combat_for would read it as "not given".
			combat = combat | {"damage_stat" : "none"}
		checked["combat"] = Packs.combat_for(kind, None, combat)
		return checked

	# ============================================================
	@staticmethod
	def import_into(guild_id: int, name: str) -> tuple[list[GearItems], list[str]] :
		"""Copies a pack into a server's catalog, leaving out items whose name the catalog already has.

		@return: the items added, and the names of the ones skipped.
		"""
		pack = Packs.load(name)
		added, skipped = [], []
		transactions = GearItemTransactions()
		for item in pack["items"] :
			fields = {key : value for key, value in item.items() if key not in ("kind", "name")}
			created = transactions.add(guild_id, item["kind"], item["name"], pack=name, **fields)
			if created is None :
				skipped.append(item["name"])
			else :
				added.append(created)
		return added, skipped

	# ============================================================
	@staticmethod
	def legacy_items() -> tuple[list[dict], list[str]] :
		"""The old global armors and weapons as checked catalog items (combat values converted, price 0), and the
		rows that could not be converted."""
		from classes.gear.Legacy import Legacy

		items, problems = [], []
		for table, kind, keys in (("weapons", WEAPON, ("dice", "modifier", "hitmodifier")),
		                          ("armors", ARMOR, ("hp", "ap", "ac", "hitchance"))) :
			for row in Legacy.rows(table) :
				name = str(row.get("name") or "").strip()[:NAME_LIMIT]
				combat = {key : row[key] for key in keys if row.get(key) is not None}
				try :
					items.append(Packs.validate_item({"kind" : kind, "name" : name, "price" : 0, "combat" : combat,
					                                  "description" : f"Imported from the old {table} table."}))
				except ValueError as e :
					problems.append(f"{name or '(no name)'}: {e}")
		return items, problems

	# ============================================================
	@staticmethod
	def import_legacy(guild_id: int) -> tuple[list[GearItems], list[str], list[str]] :
		"""Copies the old armors and weapons into a server's catalog, leaving out names it already has.

		@return: the items added, the names skipped, and the rows that could not be converted.
		"""
		items, problems = Packs.legacy_items()
		added, skipped = [], []
		transactions = GearItemTransactions()
		for item in items :
			fields = {key : value for key, value in item.items() if key not in ("kind", "name")}
			created = transactions.add(guild_id, item["kind"], item["name"], pack=LEGACY_PACK, **fields)
			(added if created is not None else skipped).append(created if created is not None else item["name"])
		return added, skipped, problems

	# == requirements ==

	# ============================================================
	@staticmethod
	def validate_requirements(requirements) -> dict[str, int] :
		"""Checks {stat: minimum}: stats from SPECIAL, minimums whole numbers from 1 to 13."""
		if not isinstance(requirements, dict) :
			raise ValueError("requirements must be a JSON object like {\"strength\": 8}.")
		checked = {}
		for stat, minimum in requirements.items() :
			if stat not in STATS :
				raise ValueError(f"{stat!r} is not a SPECIAL stat; use {', '.join(STATS)}.")
			if not Packs._is_int(minimum) or not REQUIREMENT_MIN <= minimum <= REQUIREMENT_MAX :
				raise ValueError(f"the {stat} requirement must be a whole number from {REQUIREMENT_MIN} to "
				                 f"{REQUIREMENT_MAX}, not {minimum!r}.")
			checked[stat] = minimum
		return checked

	# ============================================================
	@staticmethod
	def stat(word: str) -> str | None :
		"""The SPECIAL stat a word names: the full name, or the start of one with at least three letters (str, agi)."""
		word = word.strip().lower()
		if word in STATS :
			return word
		if len(word) < 3 :
			return None
		matches = [stat for stat in STATS if stat.startswith(word)]
		return matches[0] if len(matches) == 1 else None

	# ============================================================
	@staticmethod
	def parse_requirements(text: str | None) -> dict[str, int] :
		"""Reads requirements written like `strength 8, agility 4` (also `Str: 8; agi 4`). Empty text or `none`
		means no requirements. Raises ValueError with a message for staff when a part cannot be read."""
		text = (text or "").strip()
		if not text or text.lower() in ("none", "-") :
			return {}
		requirements = {}
		for part in re.split(r"[,;\n]+", text) :
			part = part.strip()
			if not part :
				continue
			match = re.fullmatch(r"([A-Za-z]+)\s*[:=]?\s*(-?\d+)", part)
			if match is None :
				raise ValueError(f"I could not read `{part}`. Write requirements like `strength 8, agility 4`.")
			stat = Packs.stat(match.group(1))
			if stat is None :
				raise ValueError(f"`{match.group(1)}` is not a SPECIAL stat. Use {', '.join(STATS)}.")
			if stat in requirements :
				raise ValueError(f"{stat.capitalize()} is listed twice.")
			minimum = int(match.group(2))
			if not REQUIREMENT_MIN <= minimum <= REQUIREMENT_MAX :
				raise ValueError(f"{stat.capitalize()} needs a number from {REQUIREMENT_MIN} to {REQUIREMENT_MAX}, "
				                 f"not {minimum}.")
			requirements[stat] = minimum
		return requirements

	# == combat values ==

	# ============================================================
	@staticmethod
	def normalise(kind: str, combat: dict | None) -> dict :
		"""An item's combat values in the current shape, with old values converted."""
		if kind == WEAPON :
			weapon = Rules.normalise_weapon(combat)
			values = {key : weapon[key] for key in WEAPON_COMBAT}
			if weapon.get("ap") :
				values["ap"] = weapon["ap"]
			if weapon.get("kind") :
				values["kind"] = weapon["kind"]
			return values
		if kind == CONSUMABLE :
			return Items.normalise(combat)
		return {key : value for key, value in Rules.normalise_armor(combat).items() if key in ARMOR_COMBAT}

	# ============================================================
	@staticmethod
	def combat_for(kind: str, current: dict | None, changes: dict) -> dict :
		"""An item's combat values: current (converted to the current shape, or the defaults) with changes applied.
		Changes set to None are left alone. Changes in the old shape are converted as a whole. Raises ValueError for
		values of the other kind, or of the wrong type.

		Weapons: type (a damage type's name), dice like `1d8`, attack_stat, damage_stat (a stat or none), hit_mod,
		range (melee or ranged), properties and optionally ap. Armor: armor_class, ac, dt, hit_mod, ability_hit_mod.
		Consumables: use (heal, cure, boost or none), dice, condition and turns.
		"""
		defaults = COMBAT_DEFAULTS[kind]
		combat = Packs.normalise(kind, current) if current else dict(defaults)
		changes = dict(changes or {})
		allowed = set(defaults) | OPTIONAL_KEYS[kind]
		legacy = LEGACY_KEYS[kind]
		if changes and legacy & changes.keys() and not (allowed - {"dice", "ac", "ap"}) & changes.keys() :
			for key in changes :
				if key not in allowed | legacy :
					raise ValueError(f"{key} is not a combat value.")
			Packs._legacy_check(changes)
			changes = Packs.normalise(kind, changes)
		for key, value in changes.items() :
			if value is None :
				continue
			if key not in allowed :
				for other in KINDS :
					if other != kind and (key in COMBAT_DEFAULTS[other] or key in OPTIONAL_KEYS[other]
					                      or key in LEGACY_KEYS[other]) :
						raise ValueError(f"{key} is only for {KIND_WORDS[other][0]}, and this item is "
						                 f"{KIND_WORDS[kind][1]}.")
				raise ValueError(f"{key} is not a combat value.")
			combat[key] = Packs._combat_value(key, value)
		if kind == WEAPON and combat.get("ap") is None :
			combat.pop("ap", None)
		if kind == WEAPON and not combat.get("kind") :
			combat.pop("kind", None)
		if kind == CONSUMABLE :
			problem = Items.check(combat)
			if problem :
				raise ValueError(problem)
		return combat

	# ============================================================
	@staticmethod
	def _legacy_check(changes: dict) -> None :
		"""Checks values in the old shape before they are converted."""
		if changes.get("dice") is not None :
			Packs._combat_value("dice", changes["dice"])
		modifier = changes.get("modifier")
		if modifier is not None :
			if not isinstance(modifier, str) :
				raise ValueError("modifier must be text.")
			text = modifier.strip().lower()
			if text not in ("", "none", "-") and (":" not in text or text.split(":", 1)[0] not in ("damage", "dice")
			                                      or text.split(":", 1)[1] not in STATS) :
				raise ValueError(f"modifier must be damage:<stat>, dice:<stat> or none, not {modifier!r}.")
		for key in ("hitmodifier", "hp", "ap", "ac", "hitchance") :
			value = changes.get(key)
			if value is None :
				continue
			if not Packs._is_int(value) :
				raise ValueError(f"{key} must be a whole number, not {value!r}.")
			if key in ("hp", "ap", "ac") and value < 0 :
				raise ValueError(f"{key} cannot be below 0.")

	# ============================================================
	@staticmethod
	def parse_properties(value) -> list[str] :
		"""Properties from a list or from text like `light, thrown`. Raises ValueError for unknown ones."""
		if isinstance(value, str) :
			parts = [part.strip().lower().replace(" ", "_").replace("-", "_") for part in re.split(r"[,;]", value)]
			value = [part for part in parts if part and part != "none"]
		if not isinstance(value, list) :
			raise ValueError("properties must be a list, like light, thrown.")
		unknown = [str(part) for part in value if part not in Rules.PROPERTIES]
		if unknown :
			raise ValueError(f"Unknown properties: {', '.join(unknown)}. Use {', '.join(Rules.PROPERTIES)}.")
		return list(dict.fromkeys(value))

	# ============================================================
	@staticmethod
	def _combat_value(key: str, value) :
		if key == "dice" :
			text = str(value).strip().lower() if isinstance(value, str) else None
			if text is None or not DICE.fullmatch(text) :
				raise ValueError(f"dice must look like 1d8 or 2d6, not {value!r}.")
			return text
		if key == "type" :
			if value is None or (isinstance(value, str) and value.strip().lower() in ("", "none", "-")) :
				return None
			if not isinstance(value, str) or len(value.strip()) > 50 :
				raise ValueError("type must be the name of a damage type.")
			return value.strip()
		if key in ("attack_stat", "damage_stat") :
			text = value.strip().lower() if isinstance(value, str) else ""
			if key == "damage_stat" and (value is None or text in ("", "none", "-")) :
				return None
			stat = Packs.stat(text)
			if stat is None :
				raise ValueError(f"{key} must be a SPECIAL stat, not {value!r}.")
			return stat
		if key == "kind" :
			text = value.strip().lower() if isinstance(value, str) else None
			if text in (None, "", "none", "-") :
				return None
			if text not in Rules.WEAPON_KINDS :
				raise ValueError(f"kind must be one of {', '.join(Rules.WEAPON_KINDS)}, not {value!r}.")
			return text
		if key == "range" :
			if value not in Rules.RANGES :
				raise ValueError(f"range must be {' or '.join(Rules.RANGES)}, not {value!r}.")
			return value
		if key == "properties" :
			return Packs.parse_properties(value)
		if key == "use" :
			if value not in Items.USES :
				raise ValueError(f"use must be one of {', '.join(Items.USES)}, not {value!r}.")
			return value
		if key == "condition" :
			if value is None or (isinstance(value, str) and value.strip().lower() in ("", "none", "-")) :
				return None
			text = value.strip().lower() if isinstance(value, str) else ""
			if text not in Conditions.DEFINITIONS :
				raise ValueError(f"condition must be one of {', '.join(Conditions.DEFINITIONS)}, not {value!r}.")
			return text
		if key == "armor_class" :
			if value not in Rules.ARMOR_CLASSES :
				raise ValueError(f"armor_class must be one of {', '.join(Rules.ARMOR_CLASSES)}, not {value!r}.")
			return value
		if not Packs._is_int(value) :
			raise ValueError(f"{key} must be a whole number, not {value!r}.")
		if key in ("hit_mod", "ability_hit_mod") and not -HIT_LIMIT <= value <= HIT_LIMIT :
			raise ValueError(f"{key} must be between -{HIT_LIMIT} and {HIT_LIMIT}.")
		if key in ("ac", "dt") and not 0 <= value <= AC_LIMIT :
			raise ValueError(f"{key} must be between 0 and {AC_LIMIT}.")
		if key == "ap" and not 1 <= value <= AP_LIMIT :
			raise ValueError(f"ap must be between 1 and {AP_LIMIT}.")
		return value

	# ============================================================
	@staticmethod
	def refresh_into(guild_id: int, name: str) -> list[GearItems] :
		"""Rewrites the combat values of the server's items that came from a pack with the pack's current values (for
		catalogs imported before the combat round). Other fields, and items renamed since, are left alone.

		@return: the items updated.
		"""
		pack = Packs.load(name)
		values = {item["name"].lower() : item for item in pack["items"]}
		updated = []
		transactions = GearItemTransactions()
		for item in transactions.get_all(guild_id) :
			source = values.get(item.name.lower())
			if source is None or item.pack != name or source["kind"] != item.kind :
				continue
			if item.combat != source["combat"] :
				updated.append(transactions.update(item.id, combat=source["combat"]))
		return updated

	# ============================================================
	@staticmethod
	def _is_int(value) -> bool :
		return isinstance(value, int) and not isinstance(value, bool)
