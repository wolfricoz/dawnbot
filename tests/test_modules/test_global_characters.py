from types import SimpleNamespace

from classes.characters.GlobalCharacters import GlobalCharacters, SMALL_SERVER_LIMIT
from database.transactions.CharacterTransactions import CharacterTransactions, PENDING, RETIRED
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID

HOME = 396757854637260811


def guild(humans: int, bots: int = 1, guild_id: int = GUILD_ID) :
	"""Just enough of a discord.Guild: its id and members."""
	members = [SimpleNamespace(bot=False) for _ in range(humans)] + [SimpleNamespace(bot=True) for _ in range(bots)]
	return SimpleNamespace(id=guild_id, members=members, member_count=len(members))


class TestGlobalCharacters(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.aria = self.add_character("Aria", guild_id=HOME, is_global=True)
		self.add_character("Bryn", guild_id=HOME)
		self.add_character("Cass", guild_id=HOME, is_global=True, state=PENDING)
		self.add_character("Dana", guild_id=HOME, is_global=True, state=RETIRED)
		self.add_character("Here", is_global=True)

	def test_small_servers_have_fewer_than_ten_members(self) :
		self.assertTrue(GlobalCharacters.is_small(guild(SMALL_SERVER_LIMIT - 1, bots=5)))
		self.assertFalse(GlobalCharacters.is_small(guild(SMALL_SERVER_LIMIT)))

	def test_only_approved_global_characters_from_other_servers_show(self) :
		names = [character.name for character in GlobalCharacters.visible(guild(3), USER_ID)]
		self.assertEqual(names, ["Aria"])
		self.assertEqual(GlobalCharacters.visible(guild(10), USER_ID), [])
		self.assertEqual(GlobalCharacters.visible(guild(3), USER_ID + 1), [])

	def test_find_by_name(self) :
		self.assertEqual(GlobalCharacters.find(guild(3), USER_ID, "ARIA").id, self.aria.id)
		self.assertIsNone(GlobalCharacters.find(guild(3), USER_ID, "Bryn"))
		self.assertIsNone(GlobalCharacters.find(guild(12), USER_ID, "Aria"))

	def test_turning_it_off(self) :
		CharacterTransactions().update(self.aria.id, is_global=False)
		self.assertEqual(GlobalCharacters.visible(guild(3), USER_ID), [])

	def test_characters_are_not_global_by_default(self) :
		self.assertFalse(CharacterTransactions().add(USER_ID, GUILD_ID, "Eve").is_global)
