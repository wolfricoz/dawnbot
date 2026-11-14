import unittest
from types import SimpleNamespace

from classes.combat.CombatCache import CombatCache
from classes.kernel.ConfigData import ConfigData
from database.database import clear_bot_database, create_bot_database
from database.transactions.ServerTransactions import ServerTransactions

GUILD_ID = 1048433044253573120
USER_ID = 188647277181665280


class DatabaseTestCase(unittest.TestCase) :
	"""Starts every test with empty tables and empty in-memory caches."""

	def setUp(self) :
		create_bot_database()
		clear_bot_database()
		ConfigData().data = {}
		CombatCache().load_all()

	def tearDown(self) :
		clear_bot_database()

	@staticmethod
	def add_server(guild_id: int = GUILD_ID) :
		ServerTransactions().add(guild_id, "owner", "Test server", 10, "", owner_id=USER_ID)


def fake_message(content: str, guild_id: int = GUILD_ID, author_id: int = USER_ID, manage_messages: bool = False,
                 mentions: list | None = None) :
	"""Just enough of a discord.Message for the progression code."""
	author = SimpleNamespace(id=author_id, bot=False,
	                         guild_permissions=SimpleNamespace(manage_messages=manage_messages))
	return SimpleNamespace(content=content, author=author, guild=SimpleNamespace(id=guild_id, name="Test server"),
	                       mentions=mentions or [])
