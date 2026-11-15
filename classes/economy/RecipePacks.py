"""Recipe packs: materials, recipes and salvage lists in resources/data/recipes (fantasy.json, ...), copied into a
server with /craft recipe import. Materials are added to the gear catalog as kind `material`; recipes and salvage
lists name catalog items, so import the matching gear pack first.

A pack is {"title", "materials": [{"name", "price", "description"}], "recipes": [{"name", "result", "amount",
"ingredients": {name: amount}, "tool", "stat", "dc", "days"}], "salvage": {item name: {material name: amount}}}.
"""
import json
import os
import re

from classes.characters.Special import STATS
from database.transactions.CharacterGearTransactions import MATERIAL
from database.transactions.EconomyTransactions import EconomyTransactions
from database.transactions.GearItemTransactions import GearItemTransactions

PACK_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "resources",
                        "data", "recipes")
PACK_NAME = re.compile(r"[a-z0-9_-]+")


# ============================================================
def available() -> list[tuple[str, str]] :
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
		packs.append((name, data.get("title") or name.capitalize() if isinstance(data, dict) else name))
	return packs


# ============================================================
def load(name: str) -> dict :
	"""Reads and checks a pack. Raises ValueError, saying what is wrong."""
	if not isinstance(name, str) or not PACK_NAME.fullmatch(name) :
		raise ValueError(f"There is no recipe pack called {name}.")
	path = os.path.join(PACK_DIR, f"{name}.json")
	if not os.path.isfile(path) :
		raise ValueError(f"There is no recipe pack called {name}.")
	with open(path, encoding="utf-8") as file :
		data = json.load(file)
	materials = {material["name"].lower() for material in data.get("materials", [])}
	for recipe in data.get("recipes", []) :
		if not recipe.get("name") or not recipe.get("result") or not recipe.get("ingredients") :
			raise ValueError(f"A recipe in the {name} pack needs a name, a result and ingredients.")
		if recipe.get("stat", "intelligence") not in STATS :
			raise ValueError(f"{recipe['name']}: {recipe.get('stat')} is not a SPECIAL stat.")
		if not 1 <= int(recipe.get("dc", 12)) <= 40 :
			raise ValueError(f"{recipe['name']}: the DC is 1 to 40.")
	for item, parts in (data.get("salvage") or {}).items() :
		unknown = [part for part in parts if part.lower() not in materials]
		if unknown :
			raise ValueError(f"Salvage for {item} names materials the pack doesn't have: {', '.join(unknown)}.")
	return data


# ============================================================
def import_into(guild_id: int, name: str) -> tuple[list[str], list[str], list[str]] :
	"""Copies a pack into a server. Returns what was added, what was skipped (already there) and what couldn't be
	added because the catalog lacks an item it names."""
	data = load(name)
	added, skipped, missing = [], [], []
	for material in data.get("materials", []) :
		if GearItemTransactions().find(guild_id, material["name"]) is not None :
			skipped.append(material["name"])
			continue
		GearItemTransactions().add(guild_id, MATERIAL, material["name"], price=int(material.get("price") or 0),
		                           description=material.get("description"), requirements={}, combat={}, pack=name)
		added.append(material["name"])
	for recipe in data.get("recipes", []) :
		if EconomyTransactions().find_recipe(guild_id, recipe["name"]) is not None :
			skipped.append(recipe["name"])
			continue
		result = GearItemTransactions().find(guild_id, recipe["result"])
		tool = GearItemTransactions().find(guild_id, recipe["tool"]) if recipe.get("tool") else None
		ingredients, lacking = [], []
		for ingredient, amount in recipe["ingredients"].items() :
			item = GearItemTransactions().find(guild_id, ingredient)
			if item is None :
				lacking.append(ingredient)
			else :
				ingredients.append({"item_id" : item.id, "amount" : int(amount)})
		if result is None :
			lacking.insert(0, recipe["result"])
		if recipe.get("tool") and tool is None :
			lacking.append(recipe["tool"])
		if lacking :
			missing.append(f"{recipe['name']} (needs {', '.join(lacking)})")
			continue
		EconomyTransactions().add_recipe(guild_id, recipe["name"], result_item_id=result.id,
		                                 result_amount=int(recipe.get("amount") or 1), ingredients=ingredients,
		                                 tool_item_id=tool.id if tool else None,
		                                 stat=recipe.get("stat", "intelligence"), dc=int(recipe.get("dc", 12)),
		                                 days=int(recipe.get("days") or 0), pack=name)
		added.append(recipe["name"])
	for item_name, parts in (data.get("salvage") or {}).items() :
		item = GearItemTransactions().find(guild_id, item_name)
		if item is not None and not item.salvage :
			GearItemTransactions().update(item.id, salvage={part : int(amount) for part, amount in parts.items()})
	return added, skipped, missing
