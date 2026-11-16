"""Phase 2 of design/economy.md: slots, condition, wear, repairs, carry weight and ammunition."""
from types import SimpleNamespace

from classes.characters.Access import Access
from classes.combat.Loadout import Loadout
from classes.gear import Carry, Condition, Slots
from classes.gear.Gear import ACCESSORY, ARMOR, CURSED, Gear, MASTERWORK, WEAPON
from classes.gear.Packs import Packs
from classes.kernel.ConfigData import ConfigData
from database.transactions.CharacterGearTransactions import BROKEN, CharacterGearTransactions, OWNED
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from database.transactions.OccupationTransactions import OccupationTransactions
from modules.Gear import inventory_lines
from resources.configs.ConfigMapping import ConfigMapping
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID


class FixedRng :
	"""randint returns the given numbers in order, then the last one again."""

	def __init__(self, *numbers) :
		self.numbers = list(numbers)

	def randint(self, low, high) :
		value = self.numbers.pop(0) if len(self.numbers) > 1 else self.numbers[0]
		return max(low, min(high, value))


class EquipmentTestCase(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()
		items = GearItemTransactions()
		weapon = lambda **combat : Packs.combat_for(WEAPON, None, combat)
		self.sword = items.add(GUILD_ID, WEAPON, "Sword", price=200, combat=weapon(dice="2d6"), weight=1.5,
		                       salvage={"Steel Ingot" : 2})
		self.dagger = items.add(GUILD_ID, WEAPON, "Dagger", price=60, combat=weapon(dice="1d6", properties="light"))
		self.greatblade = items.add(GUILD_ID, WEAPON, "Greatblade", price=900,
		                            combat=weapon(dice="2d8", properties="two_handed"))
		self.shield = items.add(GUILD_ID, WEAPON, "Shield", price=150,
		                        combat=weapon(dice="1d4", properties="shield, light"))
		self.bow = items.add(GUILD_ID, WEAPON, "Bow", price=180,
		                     combat=weapon(dice="1d8", range="ranged", attack_stat="perception"))
		self.plate = items.add(GUILD_ID, ARMOR, "Plate", price=2000,
		                       combat=Packs.combat_for(ARMOR, None, {"armor_class" : "heavy", "ac" : 3, "dt" : 3}),
		                       weight=20)
		self.leather = items.add(GUILD_ID, ARMOR, "Leather", price=300,
		                         combat=Packs.combat_for(ARMOR, None, {"armor_class" : "light", "ac" : 1, "dt" : 1}))
		self.ring = items.add(GUILD_ID, ACCESSORY, "Ring", price=100, slot=Slots.RING)
		self.amulet = items.add(GUILD_ID, ACCESSORY, "Amulet", price=100, slot=Slots.NECK)
		self.ingot = items.add(GUILD_ID, "material", "Steel Ingot", price=60)
		self.character = self.add_character(currency=10000)

	def own(self, item) :
		return Gear.grant(self.character, item, USER_ID)

	def entry(self, entry) :
		return CharacterGearTransactions().get(entry.id)


class TestSlots(EquipmentTestCase) :

	def test_weapons_fill_main_hand_then_off_hand_then_readied(self) :
		sword, dagger, bow = self.own(self.sword), self.own(self.dagger), self.own(self.bow)
		self.assertEqual(Gear.equip(sword)[0].slot, Slots.MAIN_HAND)
		self.assertEqual(Gear.equip(dagger)[0].slot, Slots.OFF_HAND)
		self.assertEqual(Gear.equip(bow)[0].slot, Slots.READIED)

	def test_equipping_into_a_taken_slot_puts_the_old_item_away(self) :
		sword, dagger = self.own(self.sword), self.own(self.dagger)
		Gear.equip(sword)
		Gear.equip(dagger, Slots.MAIN_HAND)
		self.assertFalse(self.entry(sword).equipped)
		self.assertIsNone(self.entry(sword).slot)
		self.assertEqual(self.entry(dagger).slot, Slots.MAIN_HAND)

	def test_two_handed_weapons_take_both_hands(self) :
		dagger, shield, blade = self.own(self.dagger), self.own(self.shield), self.own(self.greatblade)
		Gear.equip(dagger)
		Gear.equip(shield)
		self.assertEqual(self.entry(shield).slot, Slots.OFF_HAND)
		Gear.equip(blade)
		self.assertEqual(self.entry(blade).slot, Slots.MAIN_HAND)
		self.assertFalse(self.entry(dagger).equipped)
		self.assertFalse(self.entry(shield).equipped)
		# A shield then puts the two-handed weapon away.
		Gear.equip(shield)
		self.assertFalse(self.entry(blade).equipped)
		_, problem = Gear.equip(blade, Slots.OFF_HAND)
		self.assertIn("main hand", problem)

	def test_armor_and_accessories(self) :
		plate, leather = self.own(self.plate), self.own(self.leather)
		Gear.equip(plate)
		Gear.equip(leather)
		self.assertEqual(self.entry(leather).slot, Slots.BODY)
		self.assertFalse(self.entry(plate).equipped)
		first, second, third = self.own(self.ring), self.own(self.ring), self.own(self.ring)
		self.assertEqual(Gear.equip(first)[0].slot, Slots.RING_1)
		self.assertEqual(Gear.equip(second)[0].slot, Slots.RING_2)
		# Both rings taken: the first ring slot is swapped.
		self.assertEqual(Gear.equip(third)[0].slot, Slots.RING_1)
		self.assertFalse(self.entry(first).equipped)
		self.assertEqual(Gear.equip(self.own(self.amulet))[0].slot, Slots.NECK)

	def test_cursed_armor_does_not_come_off(self) :
		plate, leather = self.own(self.plate), self.own(self.leather)
		Gear.equip(plate)
		CharacterGearTransactions().update(plate.id, quality=CURSED)
		_, problem = Gear.equip(leather)
		self.assertIn("cursed", problem)

	def test_accessory_without_a_slot(self) :
		bauble = GearItemTransactions().add(GUILD_ID, ACCESSORY, "Bauble", price=5)
		_, problem = Gear.equip(self.own(bauble))
		self.assertIn("no slot", problem)

	def test_main_hand_weapon_starts_the_fight(self) :
		dagger, sword = self.own(self.dagger), self.own(self.sword)
		Gear.equip(dagger, Slots.READIED)
		Gear.equip(sword)
		combatant = Loadout.for_character(self.character, side_id=1)
		self.assertEqual(combatant.weapon_key, f"gear:{sword.id}")
		# Every owned weapon can still be used.
		self.assertEqual({weapon["name"] for weapon in combatant.stats["weapons"]} - {"Unarmed"},
		                 {"Dagger", "Sword"})

	def test_packs_check_accessories_and_weights(self) :
		item = Packs.validate_item({"kind" : ACCESSORY, "name" : "Cloak", "slot" : "back", "weight" : 1.5})
		self.assertEqual((item["slot"], item["weight"], item["combat"]), ("back", 1.5, {}))
		with self.assertRaises(ValueError) :
			Packs.validate_item({"kind" : ACCESSORY, "name" : "Cloak"})
		with self.assertRaises(ValueError) :
			Packs.validate_item({"kind" : WEAPON, "name" : "Rock", "weight" : -1})


class TestCondition(EquipmentTestCase) :

	def test_broken_is_a_condition_now(self) :
		sword = self.own(self.sword)
		updated, problem = Gear.set_status(sword, BROKEN, USER_ID)
		self.assertIsNone(problem)
		self.assertEqual((updated.status, updated.condition), (OWNED, Condition.BROKEN))
		_, problem = Gear.set_status(updated, BROKEN, USER_ID)
		self.assertIn("already broken", problem)

	def test_condition_in_fights(self) :
		sword, plate = self.own(self.sword), self.own(self.plate)
		Gear.equip(plate)
		CharacterGearTransactions().update(sword.id, condition=Condition.DAMAGED)
		CharacterGearTransactions().update(plate.id, condition=Condition.DAMAGED)
		stats = Loadout.character_stats(self.character)
		weapon = next(weapon for weapon in stats["weapons"] if weapon["name"] == "Sword")
		self.assertEqual(weapon["hit_mod"], -1)
		self.assertEqual((stats["armor"]["dt"], stats["armor"]["entry_id"]), (2, plate.id))
		CharacterGearTransactions().update(sword.id, condition=Condition.BROKEN)
		CharacterGearTransactions().update(plate.id, condition=Condition.BROKEN)
		stats = Loadout.character_stats(self.character)
		self.assertNotIn("Sword", [weapon["name"] for weapon in stats["weapons"]])
		self.assertEqual(stats["armor"]["name"], "No armor")

	def test_wear_drops_a_step_on_a_one(self) :
		sword, dagger = self.own(self.sword), self.own(self.dagger)
		worn = Condition.wear([sword.id, dagger.id], FixedRng(1, 2))
		self.assertEqual([(entry.id, condition) for entry, condition in worn], [(sword.id, Condition.WORN)])
		self.assertEqual(self.entry(dagger).condition, Condition.GOOD)

	def test_masterwork_wears_half_as_often(self) :
		sword = self.own(self.sword)
		CharacterGearTransactions().update(sword.id, quality=MASTERWORK)
		rng = SimpleNamespace(randint=lambda low, high : high)
		self.assertFalse(Condition.wear_roll(self.entry(sword), rng))
		calls = []
		Condition.wear_roll(self.entry(sword), SimpleNamespace(randint=lambda low, high : calls.append(high) or 5))
		self.assertEqual(calls, [40])

	def test_after_fight(self) :
		sword, plate = self.own(self.sword), self.own(self.plate)
		combatant = SimpleNamespace(character_id=self.character.id, state="active", weapon_key=f"gear:{sword.id}",
		                            stats={"armor" : {"entry_id" : plate.id}})
		fight = SimpleNamespace(guild_id=GUILD_ID, combatants=[combatant])
		lines = Condition.after_fight(fight, FixedRng(1))
		self.assertEqual(len(lines), 2)
		self.assertIn("now worn", lines[0])
		ConfigData().add_key(GUILD_ID, ConfigMapping.GEAR_WEAR, "DISABLED", overwrite=True)
		self.assertEqual(Condition.after_fight(fight, FixedRng(1)), [])

	def test_inventory_lines_show_slots_and_condition(self) :
		sword = self.own(self.sword)
		Gear.equip(sword)
		CharacterGearTransactions().update(sword.id, condition=Condition.DAMAGED)
		lines = inventory_lines(self.character, Gear.inventory(self.character.id))
		self.assertIn("main hand", lines[0])
		self.assertIn("damaged", lines[0])


class TestRepairs(EquipmentTestCase) :

	def test_shop_price(self) :
		plate = self.own(self.plate)
		CharacterGearTransactions().update(plate.id, condition=Condition.BROKEN)
		self.assertEqual(Condition.shop_price(self.entry(plate), self.plate, self.character), 800)
		CharacterGearTransactions().update(plate.id, condition=Condition.WORN)
		self.assertEqual(Condition.shop_price(self.entry(plate), self.plate, self.character), 100)

	def test_repair_problems(self) :
		sword = self.own(self.sword)
		self.assertIn("good condition", Condition.repair_problem(sword))
		CharacterGearTransactions().update(sword.id, condition=Condition.WORN, quality=CURSED)
		self.assertIn("curse", Condition.repair_problem(self.entry(sword)))

	def test_repair_by_hand_needs_a_repairing_occupation_and_a_material(self) :
		owner = self.add_character("Bryn")
		sword = Gear.grant(owner, self.sword, USER_ID)
		CharacterGearTransactions().update(sword.id, condition=Condition.DAMAGED)
		outcome, lines = Condition.repair_by_hand(self.character, self.entry(sword), self.sword, owner)
		self.assertIsNone(outcome)
		self.assertIn("can't repair weapon", lines[0])
		smith = OccupationTransactions().add(GUILD_ID, "Blacksmith", repairs=["weapon", "heavy"])
		CharacterTransactions().update(self.character.id, occupation_id=smith.id)
		repairer = CharacterTransactions().get_by_id(self.character.id)
		outcome, lines = Condition.repair_by_hand(repairer, self.entry(sword), self.sword, owner)
		self.assertIsNone(outcome)
		self.assertIn("Steel Ingot", lines[0])
		ingots = Gear.grant(repairer, self.ingot, USER_ID)
		CharacterGearTransactions().update(ingots.id, quantity=2)
		outcome, lines = Condition.repair_by_hand(repairer, self.entry(sword), self.sword, owner, FixedRng(19))
		self.assertIsNotNone(outcome)
		self.assertEqual(self.entry(sword).condition, Condition.GOOD)
		self.assertEqual(self.entry(ingots).quantity, 1)
		self.assertIn("Bryn's", lines[0])

	def test_a_failed_repair_keeps_the_material(self) :
		smith = OccupationTransactions().add(GUILD_ID, "Smith", repairs=["weapon"])
		CharacterTransactions().update(self.character.id, occupation_id=smith.id)
		repairer = CharacterTransactions().get_by_id(self.character.id)
		sword = self.own(self.sword)
		CharacterGearTransactions().update(sword.id, condition=Condition.BROKEN)
		ingot = Gear.grant(repairer, self.ingot, USER_ID)
		# 12 + 0 against 16 fails by 4: nothing fixed, nothing used.
		outcome, _ = Condition.repair_by_hand(repairer, self.entry(sword), self.sword, repairer, FixedRng(12))
		self.assertEqual(self.entry(sword).condition, Condition.BROKEN)
		self.assertEqual(self.entry(ingot).status, OWNED)

	def test_repair_kind_follows_armor_class(self) :
		plate = self.own(self.plate)
		self.assertEqual(Condition.repair_kind(plate, self.plate), "heavy")
		self.assertEqual(Condition.repair_kind(self.own(self.ring), self.ring), ACCESSORY)


class TestCarryWeight(EquipmentTestCase) :

	def test_off_by_default(self) :
		self.assertEqual(Carry.unit(GUILD_ID), Carry.OFF)
		self.assertEqual(Carry.load_text(self.character), "")
		self.assertFalse(Carry.overloaded(self.character))

	def test_capacity_load_and_limits(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.CARRY_WEIGHT, "kg", overwrite=True)
		# Strength 5: 66 kg.
		self.assertEqual(Carry.capacity_kg(self.character), 66)
		for _ in range(4) :
			self.own(self.plate)
		self.assertTrue(Carry.overloaded(self.character))
		self.assertIn("overloaded", Carry.load_text(self.character))
		combatant = Loadout.for_character(self.character, side_id=1)
		normal = Loadout.for_character(self.add_character("Light"), side_id=1)
		self.assertEqual(combatant.ap_max, normal.ap_max - Carry.OVERLOAD_AP)
		self.assertEqual(Carry.travel_factor(self.character), Carry.TRAVEL_SLOWDOWN)
		# 80 kg carried; another 20 kg would pass 99 kg (150%).
		entry, problem = Gear.buy(self.character, self.plate, Access(), USER_ID)
		self.assertIsNone(entry)
		self.assertIn("can't carry", problem)

	def test_pounds(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.CARRY_WEIGHT, "lb", overwrite=True)
		self.assertEqual(Carry.show(GUILD_ID, 10), "22 lb")


class TestAmmo(EquipmentTestCase) :

	def test_dice_step_down_and_run_out(self) :
		self.assertEqual(Carry.roll_die("d12", FixedRng(2)), "d10")
		self.assertEqual(Carry.roll_die("d12", FixedRng(3)), "d12")
		self.assertEqual(Carry.roll_die("d4", FixedRng(1)), Carry.EMPTY)
		self.assertTrue(Carry.uses_ammo(self.bow.combat))
		self.assertFalse(Carry.uses_ammo(self.sword.combat))

	def test_off_by_default(self) :
		bow = self.own(self.bow)
		combatant = SimpleNamespace(weapon_key=f"gear:{bow.id}")
		self.assertEqual(Carry.use_ammo(GUILD_ID, combatant, FixedRng(1)), [])

	def test_running_out_keeps_the_bow_out_of_fights_until_refilled(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.AMMO, "die", overwrite=True)
		bow = self.own(self.bow)
		CharacterGearTransactions().update(bow.id, ammo_die="d4")
		combatant = SimpleNamespace(weapon_key=f"gear:{bow.id}")
		lines = Carry.use_ammo(GUILD_ID, combatant, FixedRng(1))
		self.assertIn("out of ammunition", lines[0])
		names = [weapon["name"] for weapon in Loadout.character_stats(self.character)["weapons"]]
		self.assertNotIn("Bow", names)
		self.assertEqual(Carry.refill_price(self.entry(bow), GUILD_ID), 100)
		CharacterGearTransactions().update(bow.id, ammo_die=None)
		self.assertEqual(Carry.refill_steps(self.entry(bow)), 0)


class TestMigration(EquipmentTestCase) :
	"""The data statements of migration 0024_economy_equipment, run against the test database."""

	def test_data_statements(self) :
		import importlib.util
		import os

		from sqlalchemy import text

		from database.database import engine

		path = os.path.join(os.path.dirname(__file__), "..", "..", "alembic", "versions", "0024_economy_equipment.py")
		spec = importlib.util.spec_from_file_location("migration_0024", path)
		migration = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(migration)
		transactions = CharacterGearTransactions()
		sword, dagger, shield = self.own(self.sword), self.own(self.dagger), self.own(self.shield)
		plate, broken = self.own(self.plate), self.own(self.leather)
		for entry in (sword, dagger, shield, plate) :
			transactions.update(entry.id, equipped=True)
		transactions.update(broken.id, status=BROKEN)
		with engine.begin() as connection :
			for statement in migration.DATA_STATEMENTS :
				connection.execute(text(statement))
		self.assertEqual((self.entry(sword).slot, self.entry(sword).equipped), (Slots.MAIN_HAND, True))
		self.assertEqual((self.entry(dagger).slot, self.entry(dagger).equipped), (None, False))
		self.assertEqual(self.entry(shield).slot, Slots.OFF_HAND)
		self.assertEqual(self.entry(plate).slot, Slots.BODY)
		self.assertEqual((self.entry(broken).status, self.entry(broken).condition), (OWNED, Condition.BROKEN))
