"""Genre packs, and the checks every catalog item passes.

A genre pack is a JSON file in resources/data/gear (fantasy.json, ...) with a ready-made list of weapons and armor.
/armory import copies a pack into a server's catalog. The same checks are used for items staff add by hand: SPECIAL
requirements, combat values and prices.
"""
import json
import os
import re

from classes.characters.Special import STATS
from classes.gear.Gear import ARMOR, KINDS, WEAPON
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

# The combat values per kind, and what combat uses when an item leaves one out.
WEAPON_COMBAT = {"dice" : "1d6", "modifier" : "", "hitmodifier" : 0}
# The same numbers combat uses for a character without armor (CombatCache.DEFAULT_ARMOR).
ARMOR_COMBAT = {"hp" : 75, "ap" : 25, "ac" : 12, "hitchance" : 0}
COMBAT_DEFAULTS = {WEAPON : WEAPON_COMBAT, ARMOR : ARMOR_COMBAT}
DICE = re.compile(r"([1-9]\d?)d([1-9]\d{0,2})")
MODIFIER_TYPES = ["damage", "dice"]
# What staff can pick as a weapon's modifier: none, or a stat added to the damage or turned into extra dice.
MODIFIERS = [""] + [f"{kind}:{stat}" for kind in MODIFIER_TYPES for stat in STATS]


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
	def combat_for(kind: str, current: dict | None, changes: dict) -> dict :
		"""An item's combat values: current (or the defaults for its kind) with changes applied. Changes set to None
		are left alone. Raises ValueError for values of the other kind, or of the wrong type.

		Weapons: dice like `1d8`, modifier `damage:<stat>` / `dice:<stat>` / empty, hitmodifier a whole number.
		Armor: hp, ap, ac and hitchance, whole numbers.
		"""
		defaults = COMBAT_DEFAULTS[kind]
		combat = dict(defaults) | {key : value for key, value in (current or {}).items() if key in defaults}
		for key, value in changes.items() :
			if value is None :
				continue
			if key not in defaults :
				other = WEAPON if kind == ARMOR else ARMOR
				if key in COMBAT_DEFAULTS[other] :
					raise ValueError(f"{key} is only for {'weapons' if other == WEAPON else 'armor'}, and this item "
					                 f"is {'a weapon' if kind == WEAPON else 'armor'}.")
				raise ValueError(f"{key} is not a combat value.")
			combat[key] = Packs._combat_value(key, value)
		return combat

	# ============================================================
	@staticmethod
	def _combat_value(key: str, value) :
		if key == "dice" :
			text = str(value).strip().lower() if isinstance(value, str) else None
			if text is None or not DICE.fullmatch(text) :
				raise ValueError(f"dice must look like 1d8 or 2d6, not {value!r}.")
			return text
		if key == "modifier" :
			if not isinstance(value, str) :
				raise ValueError("modifier must be text.")
			text = value.strip().lower()
			text = "" if text in ("none", "-") else text
			if text not in MODIFIERS :
				raise ValueError(f"modifier must be damage:<stat>, dice:<stat> or none, not {value!r}.")
			return text
		if not Packs._is_int(value) :
			raise ValueError(f"{key} must be a whole number, not {value!r}.")
		if key in ("hp", "ap", "ac") and value < 0 :
			raise ValueError(f"{key} cannot be below 0.")
		return value

	# ============================================================
	@staticmethod
	def _is_int(value) -> bool :
		return isinstance(value, int) and not isinstance(value, bool)
