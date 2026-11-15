import unittest
from types import SimpleNamespace

from classes.kernel.ConfigData import ConfigData
from database.database import clear_bot_database, create_bot_database
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.ServerTransactions import ServerTransactions

GUILD_ID = 1048433044253573120
USER_ID = 188647277181665280


class DatabaseTestCase(unittest.TestCase) :
	"""Starts every test with empty tables and empty in-memory caches."""

	def setUp(self) :
		create_bot_database()
		clear_bot_database()
		ConfigData().data = {}

	def tearDown(self) :
		clear_bot_database()

	@staticmethod
	def add_server(guild_id: int = GUILD_ID) :
		ServerTransactions().add(guild_id, "owner", "Test server", 10, "", owner_id=USER_ID)

	@staticmethod
	def add_character(name: str = "Ayla", state: str = APPROVED, user_id: int = USER_ID, guild_id: int = GUILD_ID,
	                  **fields) :
		"""A character with every stat at 5 unless fields say otherwise."""
		values = dict(strength=5, perception=5, endurance=5, charisma=5, intelligence=5, agility=5, luck=5,
		              prefix=f"{name.lower()}:", state=state) | fields
		return CharacterTransactions().add(user_id, guild_id, name, **values)


def fake_message(content: str, guild_id: int = GUILD_ID, author_id: int = USER_ID, manage_messages: bool = False,
                 mentions: list | None = None) :
	"""Just enough of a discord.Message for the progression code."""
	author = SimpleNamespace(id=author_id, bot=False,
	                         guild_permissions=SimpleNamespace(manage_messages=manage_messages))
	return SimpleNamespace(content=content, author=author, guild=SimpleNamespace(id=guild_id, name="Test server"),
	                       mentions=mentions or [])
