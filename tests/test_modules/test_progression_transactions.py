from database.transactions.ExperienceTransactions import ExperienceTransactions
from database.transactions.LevelTransactions import LevelTransactions
from database.transactions.UserTransactions import UserTransactions
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID

OTHER_GUILD = 396757854637260811


class TestUserTransactions(DatabaseTestCase) :

	def test_get_registers_new_user(self) :
		record = UserTransactions().get(USER_ID, GUILD_ID)
		self.assertEqual((record.uid, record.guildid, record.xp, record.messages), (USER_ID, GUILD_ID, 0, 0))

	def test_add_is_idempotent(self) :
		first = UserTransactions().add(USER_ID, GUILD_ID)
		second = UserTransactions().add(USER_ID, GUILD_ID)
		self.assertEqual(first.id, second.id)

	def test_progression_is_per_guild(self) :
		UserTransactions().get(USER_ID, GUILD_ID)
		ExperienceTransactions().add_xp(USER_ID, GUILD_ID, 10)
		self.assertEqual(UserTransactions().get(USER_ID, OTHER_GUILD).xp, 0)

	def test_delete(self) :
		UserTransactions().get(USER_ID, GUILD_ID)
		self.assertTrue(UserTransactions().delete(USER_ID, GUILD_ID))
		self.assertFalse(UserTransactions().delete(USER_ID, GUILD_ID))

	def test_sync_guild_adds_only_missing(self) :
		UserTransactions().get(1, GUILD_ID)
		self.assertEqual(UserTransactions().sync_guild(GUILD_ID, [1, 2, 3, 3]), 2)
		self.assertEqual(UserTransactions().sync_guild(GUILD_ID, [1, 2, 3]), 0)


class TestExperienceTransactions(DatabaseTestCase) :

	def test_add_xp_registers_user_and_counts_message(self) :
		record = ExperienceTransactions().add_xp(USER_ID, GUILD_ID, 25)
		self.assertEqual((record.xp, record.messages), (25, 1))

	def test_manual_xp_does_not_count_messages(self) :
		ExperienceTransactions().add_xp(USER_ID, GUILD_ID, 25, count_message=False)
		record = ExperienceTransactions().set_xp(USER_ID, GUILD_ID, 100)
		record = ExperienceTransactions().remove_xp(USER_ID, GUILD_ID, 40) if record else None
		self.assertEqual((record.xp, record.messages), (60, 0))

	def test_members_have_no_currency(self) :
		# Currency belongs to characters now.
		self.assertFalse(hasattr(ExperienceTransactions(), "add_currency"))
		self.assertFalse(hasattr(ExperienceTransactions().get(USER_ID, GUILD_ID), "currency"))


class TestLevelTransactions(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		LevelTransactions().add(GUILD_ID, 300, 1000)
		LevelTransactions().add(GUILD_ID, 100, 0)
		LevelTransactions().add(GUILD_ID, 200, 500)

	def test_duplicate_role_is_refused(self) :
		self.assertIsNone(LevelTransactions().add(GUILD_ID, 100, 50))

	def test_levels_are_ordered_by_requirement(self) :
		self.assertEqual([level.role_id for level in LevelTransactions().get_all(GUILD_ID)], [100, 200, 300])

	def test_highest_reached(self) :
		self.assertEqual(LevelTransactions().highest_reached(GUILD_ID, 499), 100)
		self.assertEqual(LevelTransactions().highest_reached(GUILD_ID, 500), 200)
		self.assertIsNone(LevelTransactions().highest_reached(OTHER_GUILD, 5000))

	def test_next_level(self) :
		self.assertEqual(LevelTransactions().next_level(GUILD_ID, 600), (300, 1000))
		self.assertEqual(LevelTransactions().next_level(GUILD_ID, 5000), (300, None))
		self.assertEqual(LevelTransactions().next_level(OTHER_GUILD, 0), (None, None))

	def test_update_and_remove(self) :
		self.assertEqual(LevelTransactions().update(200, 750).xp_required, 750)
		self.assertIsNone(LevelTransactions().update(999, 1))
		self.assertTrue(LevelTransactions().remove(200))
		self.assertFalse(LevelTransactions().remove(200))
