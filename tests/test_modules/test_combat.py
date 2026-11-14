import unittest
from unittest.mock import patch

from classes.combat.CombatCache import CombatCache
from classes.combat.CombatController import CombatController
from data.stats.combatcalculations import CombatCalculations
from database.transactions.ArmorTransactions import ArmorTransactions
from database.transactions.CombatInstanceTransactions import CombatInstanceTransactions
from database.transactions.WeaponTransactions import WeaponTransactions
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID

STATS = dict(strength=2, perception=4, endurance=2, charisma=2, intelligence=1, agility=1, prestige=0)


class TestArmorAndWeapons(DatabaseTestCase) :

	def test_armor_crud(self) :
		self.assertIsNotNone(ArmorTransactions().add("Leather", 75, 12, 1, "None"))
		self.assertIsNone(ArmorTransactions().add("leather", 75, 12))
		self.assertEqual(ArmorTransactions().update("LEATHER", ac=14).ac, 14)
		self.assertEqual(ArmorTransactions().get("leather").hp, 75)
		self.assertTrue(ArmorTransactions().delete("leather"))
		self.assertIsNone(ArmorTransactions().get("leather"))

	def test_weapon_defaults_hitmodifier_to_zero(self) :
		weapon = WeaponTransactions().add("Sword", "1D8", "damage:strength", None)
		self.assertEqual((weapon.name, weapon.dice, weapon.hitmodifier), ("sword", "1d8", 0))
		self.assertEqual(WeaponTransactions().update("sword", hitmodifier=2).hitmodifier, 2)
		self.assertTrue(WeaponTransactions().delete("sword"))


class TestCombatCache(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		CombatCache().create_armor("leather", 75, 12, 1, "none")
		CombatCache().create_weapon("sword", "1d8", "damage:strength", 1)

	def test_create_character_needs_existing_armor(self) :
		self.assertIsNone(CombatCache().create_character(USER_ID, GUILD_ID, "Ayla", "plate", **STATS))
		self.assertIsNotNone(CombatCache().create_character(USER_ID, GUILD_ID, "Ayla", "leather", **STATS))
		self.assertIn("ayla", CombatCache().characters[USER_ID])

	def test_duplicate_character_name_is_refused(self) :
		CombatCache().create_character(USER_ID, GUILD_ID, "Ayla", "leather", **STATS)
		self.assertIsNone(CombatCache().create_character(USER_ID, GUILD_ID, "ayla", "leather", **STATS))

	def test_reads_are_copies(self) :
		"""Showing a profile used to overwrite the cached armor id with its name, breaking later attacks."""
		CombatCache().create_character(USER_ID, GUILD_ID, "Ayla", "leather", **STATS)
		character = CombatCache().get_character(USER_ID, "ayla")
		character["armor"] = "leather"
		self.assertIsInstance(CombatCache().get_character(USER_ID, "ayla")["armor"], int)

	def test_update_character_keeps_unset_stats(self) :
		CombatCache().create_character(USER_ID, GUILD_ID, "Ayla", "leather", **STATS)
		CombatCache().update_character(USER_ID, "ayla", strength=5)
		character = CombatCache().get_character(USER_ID, "ayla")
		self.assertEqual((character["strength"], character["perception"]), (5, 4))

	def test_armor_in_use_is_not_removed(self) :
		CombatCache().create_character(USER_ID, GUILD_ID, "Ayla", "leather", **STATS)
		self.assertFalse(CombatCache().remove_armor("leather"))
		self.assertTrue(CombatCache().remove_character(USER_ID, "ayla"))
		self.assertTrue(CombatCache().remove_armor("leather"))

	def test_calculate_hit(self) :
		CombatCache().create_character(USER_ID, GUILD_ID, "Ayla", "leather", **STATS)
		character = CombatCache().get_character(USER_ID, "ayla")
		weapon = CombatCache().get_weapon("sword")
		# hit modifier: weapon 1 + manual 0 + armor 1 + ceil(perception 4 / 2) = 4
		with patch("classes.combat.CombatController.random.randint", return_value=10) :
			self.assertEqual(CombatController.calculate_hit(character, "sword", weapon, 0, "no", 14), (14, False, 10, 4))
			self.assertEqual(CombatController.calculate_hit(character, "sword", weapon, 0, "no", 15)[0], False)
		with patch("classes.combat.CombatController.random.randint", return_value=20) :
			self.assertTrue(CombatController.calculate_hit(character, "sword", weapon, 0, "yes", 30)[1])


class TestCombatInstances(DatabaseTestCase) :

	def test_create_loads_generated_guid(self) :
		record = CombatInstanceTransactions().create(channel_id=123)
		self.assertTrue(record.guid)
		self.assertEqual(CombatInstanceTransactions().get_channel_instance(123).guid, record.guid)


class TestCombatCalculations(unittest.TestCase) :

	def test_hp_and_modifiers(self) :
		self.assertEqual(CombatCalculations({"base_hp" : 75}).calculate_hp(3), 82)
		self.assertEqual(CombatCalculations().calculate_stat_modifier(5), 2)
