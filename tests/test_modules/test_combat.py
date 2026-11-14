import unittest
from unittest.mock import patch

from classes.combat.CombatCache import CombatCache, DEFAULT_ARMOR
from classes.combat.CombatController import CombatController
from data.stats.combatcalculations import CombatCalculations
from database.transactions.ArmorTransactions import ArmorTransactions
from database.transactions.CombatInstanceTransactions import CombatInstanceTransactions
from database.transactions.WeaponTransactions import WeaponTransactions
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID

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

	def test_reads_are_copies(self) :
		"""Showing a profile used to overwrite cached armor, breaking later attacks."""
		armor = CombatCache().get_armor("leather")
		armor["hp"] = 1
		self.assertEqual(CombatCache().get_armor("leather")["hp"], 75)

	def test_armor_can_be_removed(self) :
		self.assertTrue(CombatCache().remove_armor("leather"))
		self.assertIsNone(CombatCache().get_armor("leather"))

	def test_combatant_fights_in_the_default_armor(self) :
		"""Until gear exists, every character uses the default armor; changing a combatant never changes it."""
		combatant = CombatCache.combatant(self.add_character(perception=4))
		self.assertEqual((combatant["name"], combatant["perception"], combatant["luck"]), ("Ayla", 4, 5))
		self.assertEqual(combatant["armor"], DEFAULT_ARMOR)
		combatant["armor"]["ac"] = 99
		self.assertEqual(DEFAULT_ARMOR["ac"], 12)

	def test_calculate_hit(self) :
		character = CombatCache.combatant(self.add_character(perception=4))
		weapon = CombatCache().get_weapon("sword")
		# hit modifier: weapon 1 + manual 0 + default armor 0 + ceil(perception 4 / 2) = 3
		with patch("classes.combat.CombatController.random.randint", return_value=10) :
			self.assertEqual(CombatController.calculate_hit(character, "sword", weapon, 0, "no", 13), (13, False, 10, 3))
			self.assertEqual(CombatController.calculate_hit(character, "sword", weapon, 0, "no", 14)[0], False)
		with patch("classes.combat.CombatController.random.randint", return_value=20) :
			self.assertTrue(CombatController.calculate_hit(character, "sword", weapon, 0, "yes", 30)[1])


class TestCombatInstances(DatabaseTestCase) :

	def test_create_loads_generated_guid(self) :
		record = CombatInstanceTransactions().create(channel_id=123)
		self.assertTrue(record.guid)
		self.assertEqual(CombatInstanceTransactions().get_channel_instance(123).guid, record.guid)

	def test_character_joins_with_the_default_armor(self) :
		record = CombatInstanceTransactions().create(channel_id=123)
		CombatInstanceTransactions().add_entity(record.id, self.add_character(endurance=4))
		entity = CombatInstanceTransactions().get_channel_instance(123).entities[0]
		# hp: default armor 75 + 2.5 per point of endurance
		self.assertEqual((entity.current_hp, entity.current_ap, entity.ac), (85, 25, 12))


class TestCombatCalculations(unittest.TestCase) :

	def test_hp_and_modifiers(self) :
		self.assertEqual(CombatCalculations({"base_hp" : 75}).calculate_hp(3), 82)
		self.assertEqual(CombatCalculations().calculate_stat_modifier(5), 2)
