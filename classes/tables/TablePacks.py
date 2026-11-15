"""Table packs: ready-made roll tables in resources/data/tables (fantasy.json, ...), copied into a server with
/table import.

A pack is {"title": "...", "tables": [{"name", "description", "luck", "entries": ["01-05: ...", ...]}]}, each table's
entries written exactly as staff would paste them (see classes/tables/Tables.py).
"""
import json
import os
import re

from classes.tables import Tables
from database.database import RollTables
from database.transactions.BestiaryTransactions import BestiaryTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from database.transactions.RollTableTransactions import RollTableTransactions

PACK_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "resources",
                        "data", "tables")
PACK_NAME = re.compile(r"[a-z0-9_-]+")
NAME_LIMIT = 100


# ============================================================
def available() -> list[tuple[str, str]] :
	"""Every table pack as (name, title), sorted by name. Files that cannot be read are left out."""
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
def load(name: str) -> list[dict] :
	"""A pack's tables, each {"name", "description", "luck", "dice", "entries"} with its entries parsed. Raises
	ValueError, saying what is wrong, when the pack is missing or has a bad table."""
	if not isinstance(name, str) or not PACK_NAME.fullmatch(name) :
		raise ValueError(f"There is no table pack called {name}.")
	path = os.path.join(PACK_DIR, f"{name}.json")
	if not os.path.isfile(path) :
		raise ValueError(f"There is no table pack called {name}.")
	try :
		with open(path, encoding="utf-8") as file :
			data = json.load(file)
	except (OSError, ValueError) as e :
		raise ValueError(f"The {name} table pack can't be read: {e}")
	if not isinstance(data, dict) or not isinstance(data.get("tables"), list) :
		raise ValueError(f"The {name} table pack has no list of tables.")
	tables, seen = [], set()
	for number, table in enumerate(data["tables"], start=1) :
		if not isinstance(table, dict) or not isinstance(table.get("name"), str) or not table["name"].strip() :
			raise ValueError(f"Table {number} of the {name} pack has no name.")
		table_name = table["name"].strip()[:NAME_LIMIT]
		if table_name.lower() in seen :
			raise ValueError(f"The {name} pack has two tables called {table_name}.")
		seen.add(table_name.lower())
		lines = table.get("entries")
		if not isinstance(lines, list) or not all(isinstance(line, str) for line in lines) :
			raise ValueError(f"{table_name} in the {name} pack needs a list of entries.")
		parsed = Tables.parse("\n".join(lines))
		if parsed.errors :
			raise ValueError(f"{table_name} in the {name} pack: {'; '.join(parsed.errors[:3])}")
		tables.append({"name" : table_name, "description" : str(table.get("description") or "")[:1000] or None,
		               "luck" : bool(table.get("luck")), "dice" : parsed.dice, "entries" : parsed.entries})
	return tables


# ============================================================
def missing_references(guild_id: int, entries) -> list[str] :
	"""The catalog items and bestiary entries the entries' actions name but this server doesn't have."""
	missing = []
	for entry in entries :
		actions = entry.get("actions") if isinstance(entry, dict) else entry.actions
		for action in actions or [] :
			name = action.get("name")
			if action.get("kind") == Tables.ITEM and GearItemTransactions().find(guild_id, name) is None :
				missing.append(f"item {name}")
			elif action.get("kind") == Tables.NPC and BestiaryTransactions().find(guild_id, name) is None :
				missing.append(f"bestiary entry {name}")
	return sorted(set(missing))


# ============================================================
def import_into(guild_id: int, name: str, creator_uid: int | None = None) -> tuple[list[RollTables], list[str],
list[str]] :
	"""Copies a pack's tables into a server, skipping names it already has.

	@return: the tables added, the names skipped, and what their actions name that the server doesn't have.
	"""
	added, skipped, missing = [], [], set()
	for table in load(name) :
		if RollTableTransactions().find(guild_id, table["name"]) is not None :
			skipped.append(table["name"])
			continue
		record = RollTableTransactions().add(guild_id, table["name"], table["entries"], description=table["description"],
		                                     dice=table["dice"], luck=table["luck"], pack=name,
		                                     creator_uid=creator_uid)
		if record is None :
			skipped.append(table["name"])
			continue
		added.append(record)
		missing.update(missing_references(guild_id, table["entries"]))
	return added, skipped, sorted(missing)
