import json
import os
import tempfile

from classes.kernel.AccessControl import AccessControl
from classes.kernel.ConfigData import ConfigData
from classes.progression.Progression import Progression
from database.transactions.ExperienceTransactions import ExperienceTransactions
from database.transactions.ServerTransactions import ServerTransactions
from database.transactions.StaffTransactions import StaffTransactions
from resources.configs.ConfigMapping import ConfigMapping
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID, fake_message


class TestConfigData(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()

	def test_defaults_when_unset(self) :
		self.assertEqual(ConfigData().get_key(GUILD_ID, ConfigMapping.CURRENCY_NAME), "currency")
		self.assertEqual(ConfigData().get_int(GUILD_ID, ConfigMapping.XP_GAIN), 5)
		self.assertEqual(ConfigData().get_list(GUILD_ID, ConfigMapping.XP_CHANNELS), [])

	def test_single_values(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.CURRENCY_NAME, "caps", overwrite=True)
		ConfigData().add_key(GUILD_ID, ConfigMapping.XP_GAIN, 1, overwrite=True)
		ConfigData().add_key(GUILD_ID, ConfigMapping.XP_GAIN, 2, overwrite=True)
		self.assertEqual(ConfigData().get_key(GUILD_ID, ConfigMapping.CURRENCY_NAME), "caps")
		self.assertEqual(ConfigData().get_int(GUILD_ID, ConfigMapping.XP_GAIN), 2)

	def test_lists(self) :
		self.assertTrue(ConfigData().add_to_list(GUILD_ID, ConfigMapping.XP_CHANNELS, 111))
		self.assertTrue(ConfigData().add_to_list(GUILD_ID, ConfigMapping.XP_CHANNELS, 222))
		self.assertFalse(ConfigData().add_to_list(GUILD_ID, ConfigMapping.XP_CHANNELS, 111))
		self.assertEqual(sorted(ConfigData().get_list(GUILD_ID, ConfigMapping.XP_CHANNELS)), [111, 222])
		self.assertTrue(ConfigData().remove_from_list(GUILD_ID, ConfigMapping.XP_CHANNELS, 111))
		self.assertFalse(ConfigData().remove_from_list(GUILD_ID, ConfigMapping.XP_CHANNELS, 111))
		ConfigData().data = {}
		self.assertEqual(ConfigData().get_list(GUILD_ID, ConfigMapping.XP_CHANNELS), [222])

	def test_migrate_legacy_json(self) :
		new_guild = 1022307023527890974
		with tempfile.TemporaryDirectory() as directory :
			with open(os.path.join(directory, f"{new_guild}.json"), "w") as f :
				json.dump({"Name" : "RMR", "channels" : [1, 2], "announcement" : None, "xp_gain" : 7,
				           "currency_gain" : 30, "currency_name" : "caps", "timeline" : "", "character" : 55,
				           "modlog" : ""}, f)
			with open(os.path.join(directory, "template.json"), "w") as f :
				json.dump({"Name" : "template", "channels" : []}, f)

			self.assertEqual(ConfigData().migrate(directory), 1)
			self.assertEqual(sorted(os.listdir(directory)), [f"{new_guild}.json.imported", "template.json"])
			# A second run finds nothing left to import.
			self.assertEqual(ConfigData().migrate(directory), 0)

		ConfigData().data = {}
		self.assertTrue(ServerTransactions().exists(new_guild))
		self.assertEqual(sorted(ConfigData().get_list(new_guild, ConfigMapping.XP_CHANNELS)), [1, 2])
		self.assertEqual(ConfigData().get_int(new_guild, ConfigMapping.XP_GAIN), 7)
		self.assertEqual(ConfigData().get_key(new_guild, ConfigMapping.CURRENCY_NAME), "caps")
		self.assertEqual(ConfigData().get_int(new_guild, ConfigMapping.CHARACTER), 55)
		self.assertIsNone(ConfigData().get_int(new_guild, ConfigMapping.ANNOUNCEMENT))


class TestProgression(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()

	def test_check_size(self) :
		self.assertFalse(Progression.check_size(fake_message("x" * 300)))
		self.assertTrue(Progression.check_size(fake_message("x" * 301)))
		self.assertTrue(Progression.check_size(fake_message("x" * 10, manage_messages=True)))
		self.assertTrue(Progression.check_size(fake_message("hi", mentions=[object()])))

	def test_gains_follow_config(self) :
		self.assertEqual(Progression.xp_for(GUILD_ID, "x" * 400), 80)
		self.assertEqual(Progression.currency_for(GUILD_ID, "x" * 600), 20)
		self.assertEqual(Progression.xp_for(GUILD_ID, "x" * 50), 0)
		ConfigData().add_key(GUILD_ID, ConfigMapping.XP_GAIN, 10, overwrite=True)
		self.assertEqual(Progression.xp_for(GUILD_ID, "x" * 400), 40)

	def test_award(self) :
		record = Progression.award(fake_message("x" * 600))
		self.assertEqual((record.xp, record.currency, record.messages), (120, 20, 1))
		# Short messages earn currency but no XP, and are not counted.
		Progression.award(fake_message("x" * 30))
		record = ExperienceTransactions().get(USER_ID, GUILD_ID)
		self.assertEqual((record.xp, record.currency, record.messages), (120, 21, 1))


class TestAccessControl(DatabaseTestCase) :

	def test_staff_roles(self) :
		StaffTransactions().add(USER_ID, "Dev")
		self.assertIsNone(StaffTransactions().add(USER_ID, "rep"))
		AccessControl().reload()
		self.assertTrue(AccessControl().access_dev(USER_ID))
		self.assertTrue(AccessControl().access_all(USER_ID))
		StaffTransactions().delete(USER_ID)
		AccessControl().reload()
		self.assertFalse(AccessControl().access_dev(USER_ID))

	def test_server_sync_and_premium(self) :
		self.add_server()
		self.assertFalse(ServerTransactions().add(GUILD_ID, "o", "n", 1, ""))
		ServerTransactions().set_all_inactive()
		self.assertFalse(ServerTransactions().get(GUILD_ID).active)
		self.assertEqual(ServerTransactions().get_premium_ids(), [])
