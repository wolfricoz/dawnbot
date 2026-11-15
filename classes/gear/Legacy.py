"""Reads the global tables from before the combat round (armors, weapons, npcs, monsters), so their rows can be copied
into a server's gear catalog and bestiary before migration 0015_drop_legacy_combat drops them.

The tables have no models any more; they are read with plain SQL, and only when they still exist.
"""
from sqlalchemy import inspect, text

from database.database import engine

TABLES = {"armors" : ["name", "hp", "ap", "ac", "hitchance"], "weapons" : ["name", "dice", "modifier", "hitmodifier"],
          "npcs" : ["name", "hp", "ac", "attack", "damage"], "monsters" : ["name", "hp", "ac", "attack", "damage"]}


class Legacy :

	# ============================================================
	@staticmethod
	def exists(table: str) -> bool :
		return inspect(engine).has_table(table)

	# ============================================================
	@staticmethod
	def rows(table: str) -> list[dict] :
		"""The rows of a legacy table as dicts (an empty list when the table is gone)."""
		if table not in TABLES or not Legacy.exists(table) :
			return []
		columns = ", ".join(TABLES[table])
		with engine.connect() as connection :
			result = connection.execute(text(f"SELECT {columns} FROM {table} ORDER BY name"))
			return [dict(row._mapping) for row in result]
