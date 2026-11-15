"""Consumables and Use item, SPECIAL-based bestiary entries, pack and legacy imports, and dead characters."""
import unittest

from sqlalchemy import text

from classes.characters.Death import Death
from classes.combat import Conditions as C, Items
from classes.combat.Autopilot import Autopilot
from classes.combat.BestiaryFlow import BestiaryFlow
from classes.combat.CombatFlow import CombatFlow
from classes.combat.Engine import CombatError, SUPPORT
from classes.combat.Loadout import Loadout
from classes.combat.State import DOWNED
from classes.gear.Gear import CONSUMABLE, Gear, WEAPON
from classes.gear.Legacy import Legacy
from classes.gear.Packs import Packs
from database.database import engine as db_engine
from database.transactions.BestiaryTransactions import BestiaryTransactions
from database.transactions.CharacterGearTransactions import CharacterGearTransactions, OWNED, USED
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions, DEAD
from database.transactions.GearItemTransactions import GearItemTransactions
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID
from test_modules.test_combat import duel, engine, fighter

DRAUGHT = Items.snapshot(41, "Healing Draught", {"use" : "heal", "dice" : "2d4"})
SALVE = Items.snapshot(42, "Burn Salve", {"use" : "cure", "condition" : "burning"})
WARD = Items.snapshot(43, "Ward Charm", {"use" : "boost", "condition" : "shielded", "dice" : "1d6", "turns" : 2})


class TestItemRules(unittest.TestCase) :

	def test_checks_and_text(self) :
		self.assertIsNone(Items.check(Items.normalise({"use" : "heal", "dice" : "2d4"})))
		self.assertIsNotNone(Items.check(Items.normalise({"use" : "boost"})))
		self.assertIsNotNone(Items.check(Items.normalise({"use" : "cure", "condition" : "inspired"})))
		self.assertIsNotNone(Items.check(Items.normalise({"use" : "heal", "dice" : "lots"})))
		self.assertEqual(Items.describe({"use" : "heal", "dice" : "2d4"}), "Heals 2d4 (revives a downed ally)")
		self.assertEqual(Items.describe({"use" : "cure"}), "Cures one harmful condition")
		self.assertEqual(Items.describe({"use" : "boost", "condition" : "inspired", "turns" : 1}), "Inspired for 1 turn")

	def test_packs_check_consumables(self) :
		item = Packs.validate_item({"kind" : CONSUMABLE, "name" : "Tonic", "combat" : {"use" : "boost",
		                                                                              "condition" : "Inspired"}})
		self.assertEqual(item["combat"]["condition"], "inspired")
		with self.assertRaises(ValueError) :
			Packs.validate_item({"kind" : CONSUMABLE, "name" : "Odd", "combat" : {"use" : "explode"}})
		with self.assertRaises(ValueError) :
			Packs.validate_item({"kind" : CONSUMABLE, "name" : "Odd", "combat" : {"armor_class" : "light"}})

	def test_fantasy_pack(self) :
		pack = Packs.load("fantasy")
		bows = [item for item in pack["items"] if item["name"] in ("Hunting Bow", "Windlass Crossbow")]
		# null in a pack means no damage stat, not the default Strength.
		self.assertEqual([bow["combat"]["damage_stat"] for bow in bows], [None, None])
		self.assertGreaterEqual(len([item for item in pack["items"] if item["kind"] == CONSUMABLE]), 5)
		self.assertGreaterEqual(len(BestiaryFlow.pack_entries("fantasy")), 5)


class TestUseItem(unittest.TestCase) :

	def setUp(self) :
		self.fight = duel()
		self.fight.combatants.append(fighter(3, 1, "Rook"))
		self.ayla = self.fight.combatant(1)
		self.ayla.stats["items"] = [dict(DRAUGHT), dict(SALVE), dict(WARD)]

	def test_heal_spends_the_item_and_two_ap(self) :
		run = engine(self.fight, 3, 4)
		run.start()
		self.ayla.hp = 10
		outcome = run.use_item(self.ayla, DRAUGHT["key"], 1)
		self.assertEqual((self.ayla.hp, self.ayla.ap, outcome.used_items), (17, 5, [41]))
		self.assertIsNone(self.ayla.item(DRAUGHT["key"]))
		with self.assertRaises(CombatError) :
			engine(self.fight).use_item(self.ayla, DRAUGHT["key"], 1)

	def test_healing_item_revives_a_downed_ally(self) :
		rook = self.fight.combatant(3)
		rook.state, rook.hp = DOWNED, 0
		run = engine(self.fight, 2, 2)
		run.start()
		with self.assertRaises(CombatError) :
			run.use_item(self.ayla, SALVE["key"], 3)
		run.use_item(self.ayla, DRAUGHT["key"], 3)
		self.assertEqual((rook.state, rook.hp), ("active", 4))

	def test_cure_and_boost(self) :
		run = engine(self.fight, 5)
		run.start()
		C.add(self.ayla.conditions, C.BURNING, turns=2)
		run.use_item(self.ayla, SALVE["key"], None)
		self.assertFalse(C.has(self.ayla.conditions, C.BURNING))
		run.use_item(self.ayla, WARD["key"], 3)
		self.assertEqual(C.amount(self.fight.combatant(3).conditions, C.SHIELDED), 5)

	def test_dim_characters_revive_with_items_on_autopilot(self) :
		self.ayla.stats["special"]["intelligence"] = 0
		self.ayla.behavior = SUPPORT
		rook = self.fight.combatant(3)
		rook.state, rook.hp = DOWNED, 0
		run = engine(self.fight, 6, 6)
		run.start()
		with self.assertRaises(CombatError) as error :
			run.revive(self.ayla, 3)
		self.assertIn("healing item", str(error.exception))
		self.assertTrue(Autopilot(run)._support(self.ayla))
		self.assertEqual((rook.state, run.outcome.used_items), ("active", [41]))


class TestConsumableGear(DatabaseTestCase) :

	def test_consumables_are_carried_into_fights_and_used_up(self) :
		self.add_server()
		character = self.add_character()
		item = GearItemTransactions().add(GUILD_ID, CONSUMABLE, "Healing Draught", price=10,
		                                  combat={"use" : "heal", "dice" : "2d4"})
		entry = Gear.grant(character, item, USER_ID)
		self.assertIsNone(Gear.equip(entry)[0])
		combatant = Loadout.for_character(character, 1)
		self.assertEqual([carried["entry_id"] for carried in combatant.items], [entry.id])
		CombatFlow.use_up([entry.id])
		self.assertEqual(CharacterGearTransactions().get(entry.id).status, USED)
		self.assertEqual(Loadout.for_character(character, 1).items, [])
		CombatFlow.give_back({entry.id})
		self.assertEqual(CharacterGearTransactions().get(entry.id).status, OWNED)


class TestBestiaryBuild(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()

	def test_parse_special(self) :
		self.assertEqual(BestiaryFlow.parse_special("6 5 5 4 4 7 5")["agility"], 7)
		self.assertEqual(BestiaryFlow.parse_special("str 8, lck 3")["luck"], 3)
		self.assertIsNone(BestiaryFlow.parse_special("none"))
		with self.assertRaises(ValueError) :
			BestiaryFlow.parse_special("str 40")
		with self.assertRaises(ValueError) :
			BestiaryFlow.parse_special("speed 4")

	def test_special_entries_are_derived_like_characters(self) :
		Packs.import_into(GUILD_ID, "fantasy")
		values = BestiaryFlow.values(GUILD_ID, BestiaryFlow.preset_values("elite"), special="str 8, end 7, agi 5",
		                             level=4, weapons="Arming Sword, Oak Round Shield", armor="Chain Hauberk")
		entry = BestiaryTransactions().add(GUILD_ID, "Captain", **values)
		combatant = Loadout.for_bestiary(entry, 2)
		# 15 + 8 + 2 * 7 = 37, plus 3 levels of 2 + END modifier 2.
		self.assertEqual((combatant.hp, combatant.ac, combatant.dt, combatant.ap), (49, 14, 2, 7))
		self.assertEqual([weapon["name"] for weapon in combatant.weapons],
		                 ["Arming Sword", "Oak Round Shield", "Unarmed"])
		self.assertEqual(combatant.weapon_key, combatant.weapons[0]["key"])
		with self.assertRaises(ValueError) :
			BestiaryFlow.values(GUILD_ID, {}, weapons="Chain Hauberk")

	def test_pack_import_needs_the_gear_first(self) :
		added, skipped, problems = BestiaryFlow.import_pack(GUILD_ID, "fantasy", USER_ID)
		self.assertEqual(len(added), len(BestiaryFlow.pack_entries("fantasy")))
		self.assertTrue(problems)
		BestiaryTransactions().delete(BestiaryTransactions().find(GUILD_ID, "Road Bandit").id)
		Packs.import_into(GUILD_ID, "fantasy")
		added, skipped, problems = BestiaryFlow.import_pack(GUILD_ID, "fantasy", USER_ID)
		self.assertEqual(([entry.name for entry in added], problems), (["Road Bandit"], []))
		self.assertTrue(BestiaryTransactions().find(GUILD_ID, "Road Bandit").weapon_ids)

	def test_legacy_conversion(self) :
		values = BestiaryFlow.convert_legacy({"name" : "Ogre", "hp" : 150, "ac" : 14, "attack" : "1d20+4",
		                                      "damage" : "2d10+3"})
		self.assertEqual((values["hp"], values["ac"], values["to_hit"], values["damage"]), (45, 14, 4, "2d10"))


class TestLegacyImports(DatabaseTestCase) :
	"""The old global tables, recreated for the test the way the baseline migration made them."""

	def setUp(self) :
		super().setUp()
		self.add_server()
		with db_engine.begin() as connection :
			connection.execute(text("CREATE TABLE IF NOT EXISTS npcs (id serial primary key, name varchar(255), "
			                        "hp bigint, ac bigint, attack varchar(1024), damage varchar(1024))"))
			connection.execute(text("CREATE TABLE IF NOT EXISTS weapons (name varchar(255) primary key, "
			                        "dice varchar(255), modifier varchar(255), hitmodifier bigint)"))
			connection.execute(text("CREATE TABLE IF NOT EXISTS armors (id serial primary key, name varchar(255), "
			                        "hp bigint, ap bigint, ac bigint, hitchance bigint)"))
			connection.execute(text("INSERT INTO npcs (name, hp, ac, attack, damage) VALUES "
			                        "('Guard', 100, 13, '1d20+2', '1d8')"))
			connection.execute(text("INSERT INTO weapons VALUES ('Old Sword', '1d8', 'damage:strength', 1), "
			                        "('Broken', 'lots', 'nonsense', 0)"))
			connection.execute(text("INSERT INTO armors (name, hp, ap, ac, hitchance) VALUES "
			                        "('Old Mail', 100, 25, 16, -1)"))

	def tearDown(self) :
		with db_engine.begin() as connection :
			for table in ("npcs", "weapons", "armors") :
				connection.execute(text(f"DROP TABLE IF EXISTS {table}"))
		super().tearDown()

	def test_imports(self) :
		self.assertTrue(Legacy.exists("npcs"))
		self.assertFalse(Legacy.exists("monsters"))
		added, skipped = BestiaryFlow.import_legacy(GUILD_ID, USER_ID)
		self.assertEqual([(entry.name, entry.hp, entry.to_hit) for entry in added], [("Guard", 30, 2)])
		self.assertEqual(BestiaryFlow.import_legacy(GUILD_ID, USER_ID), ([], ["Guard"]))
		added, skipped, problems = Packs.import_legacy(GUILD_ID)
		self.assertEqual(sorted(item.name for item in added), ["Old Mail", "Old Sword"])
		self.assertEqual(len(problems), 1)
		sword = GearItemTransactions().find(GUILD_ID, "Old Sword")
		self.assertEqual((sword.kind, sword.price, sword.combat["damage_stat"]), (WEAPON, 0, "strength"))


class TestDeath(DatabaseTestCase) :

	def test_die_and_resurrect(self) :
		self.add_server()
		character = self.add_character()
		self.assertEqual(CharacterTransactions().count_active(USER_ID, GUILD_ID), 1)
		dead, problem = Death.die(character)
		self.assertEqual((dead.state, problem), (DEAD, None))
		self.assertEqual(CharacterTransactions().count_active(USER_ID, GUILD_ID), 0)
		self.assertIsNone(Death.die(dead)[0])
		self.assertEqual(Death.resurrect(dead)[0].state, APPROVED)
		self.assertIsNone(Death.resurrect(CharacterTransactions().get_by_id(character.id))[0])

	def test_injury_text(self) :
		self.assertEqual(CombatFlow.injury_text(None, "Ambush", "Cut arm"), "Cut arm (Ambush)")
		self.assertEqual(CombatFlow.injury_text("Old scar (Raid)", "Ambush", "Cut arm"),
		                 "Old scar (Raid)\nCut arm (Ambush)")
