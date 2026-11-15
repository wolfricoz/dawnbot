import random
import unittest
from types import SimpleNamespace

import discord

from classes.gear.Packs import Packs
from classes.tables import TablePacks, Tables
from database.transactions.RollTableTransactions import RollTableTransactions
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID
from views.tables.TableButtons import add_buttons


class FixedRng :
	"""randint returns the given numbers in order."""

	def __init__(self, *values) :
		self.values = list(values)

	def randint(self, low, high) :
		value = self.values.pop(0)
		assert low <= value <= high, f"{value} is not between {low} and {high}"
		return value


RANGED = """
# Loot
01-05: Nothing.
06-10: Some coins | currency: 2d6
11: A sword | item: Arming Sword
12. Wolves! | npc: 1d4 Grey Wolf | xp: 25
"""


class TestParsing(unittest.TestCase) :

	def test_ranges(self) :
		parsed = Tables.parse(RANGED)
		self.assertEqual(parsed.errors, [])
		self.assertEqual(parsed.dice, "1d12")
		self.assertEqual(len(parsed.entries), 4)
		self.assertEqual((parsed.entries[1]["low"], parsed.entries[1]["high"]), (6, 10))
		self.assertEqual(parsed.entries[1]["actions"], [{"kind" : "currency", "amount" : "2d6"}])
		self.assertEqual(parsed.entries[3]["actions"], [{"kind" : "npc", "name" : "Grey Wolf", "count" : "1d4"},
		                                               {"kind" : "xp", "amount" : "25"}])

	def test_weights(self) :
		parsed = Tables.parse("3x A goblin\nAn orc | npc: Orc\n2× A troll")
		self.assertEqual(parsed.errors, [])
		self.assertEqual(parsed.dice, Tables.WEIGHTS)
		self.assertEqual([entry["weight"] for entry in parsed.entries], [3, 1, 2])
		self.assertEqual(parsed.entries[1]["actions"], [{"kind" : "npc", "name" : "Orc", "count" : "1"}])

	def test_gaps_overlaps_and_mixing_are_errors(self) :
		self.assertIn("Nothing covers 4-5", Tables.parse("1-3: a\n6-8: b").errors)
		self.assertTrue(any("overlaps" in error for error in Tables.parse("1-3: a\n3-4: b").errors))
		self.assertTrue(any("mixed" in error for error in Tables.parse("1-3: a\nb").errors))
		self.assertTrue(Tables.parse("2-4: starts late").errors)

	def test_bad_lines(self) :
		errors = Tables.parse("A thing | gold: 5\nB | currency: lots\nC | npc: 1d99999 Rat\n0: zero").errors
		self.assertEqual(len(errors), 4)
		self.assertTrue(errors[0].startswith("Line 1"))
		self.assertTrue(Tables.parse("").errors)
		self.assertTrue(Tables.parse("# only a comment").errors)
		self.assertTrue(Tables.parse("200x Too heavy").errors)

	def test_export_reads_back(self) :
		for text in (RANGED, "3x A goblin | item: Club\nAn orc | npc: 2 Orc | currency: 1d6+2"):
			parsed = Tables.parse(text)
			again = Tables.parse(Tables.export(parsed.entries, parsed.dice))
			self.assertEqual(again.errors, [])
			self.assertEqual(again.entries, parsed.entries)
			self.assertEqual(again.dice, parsed.dice)
		self.assertTrue(Tables.export(Tables.parse(RANGED).entries, "1d12").startswith("01-05: Nothing."))


class TestRolling(unittest.TestCase) :

	def test_pick_ranges_and_weights(self) :
		parsed = Tables.parse(RANGED)
		entry, natural, rolled = Tables.pick(parsed.entries, parsed.dice, FixedRng(7))
		self.assertEqual((entry["text"], natural, rolled), ("Some coins", 7, 7))
		weighted = Tables.parse("3x A\nB\n2x C")
		self.assertEqual(Tables.pick(weighted.entries, weighted.dice, FixedRng(3))[0]["text"], "A")
		self.assertEqual(Tables.pick(weighted.entries, weighted.dice, FixedRng(4))[0]["text"], "B")
		self.assertEqual(Tables.pick(weighted.entries, weighted.dice, FixedRng(6))[0]["text"], "C")

	def test_luck_shift_stays_on_the_table(self) :
		parsed = Tables.parse(RANGED)
		entry, natural, rolled = Tables.pick(parsed.entries, parsed.dice, FixedRng(10), shift=4)
		self.assertEqual((natural, rolled, entry["text"]), (10, 12, "Wolves!"))
		self.assertEqual(Tables.pick(parsed.entries, parsed.dice, FixedRng(2), shift=-6)[2], 1)
		self.assertEqual(Tables.luck_shift(9), 8)
		self.assertEqual(Tables.luck_shift(3), -4)
		self.assertEqual(Tables.luck_shift(6, base=6), 0)

	def test_inline_dice(self) :
		text, actions, notes = Tables.fill("{2d6} goblins and {d4+1} wolves", lambda name : None, FixedRng(3, 4, 2))
		self.assertEqual(text, "**7** goblins and **3** wolves")
		self.assertEqual((actions, notes), ([], []))
		self.assertEqual(Tables.fill("{99d6} too many", lambda name : None)[0], "{99d6} too many")

	def test_nested_tables(self) :
		tables = {"colour" : ("weights", Tables.parse("Red | currency: 5").entries),
		          "loop" : ("weights", Tables.parse("again [[Loop]]").entries)}

		def lookup(name) :
			return tables.get(name.lower())

		text, actions, notes = Tables.fill("A [[Colour]] door, [[Missing]]", lookup, FixedRng(1))
		self.assertEqual(text, "A Red door, Missing")
		self.assertEqual(actions, [{"kind" : "currency", "amount" : "5"}])
		self.assertEqual(notes, ["There is no table called Missing."])
		text, _, notes = Tables.fill("[[Loop]]", lookup, FixedRng(1, 1, 1))
		self.assertEqual(text, "again again again Loop")
		self.assertTrue(any("deep" in note for note in notes))

	def test_roll_resolves_actions(self) :
		parsed = Tables.parse(RANGED)
		rolled = Tables.roll(parsed.entries, parsed.dice, lambda name : None, FixedRng(12, 3))
		self.assertEqual(rolled.text, "Wolves!")
		self.assertEqual(rolled.actions, [{"kind" : "npc", "name" : "Grey Wolf", "count" : 3},
		                                  {"kind" : "xp", "amount" : 25}])
		rewards, encounter = Tables.actions_summary(rolled.actions)
		self.assertEqual((rewards, encounter), (["25 XP"], ["3 × Grey Wolf"]))

	def test_amounts(self) :
		self.assertEqual(Tables.roll_amount("50"), 50)
		self.assertEqual(Tables.roll_amount("2d6+3", FixedRng(1, 1)), 5)
		self.assertEqual(Tables.roll_amount("1d4-9", FixedRng(2)), 0)
		self.assertEqual(Tables.resolve([{"kind" : "npc", "name" : "Rat", "count" : "40"}])[0]["count"],
		                 Tables.NPC_LIMIT)
		self.assertTrue(Tables.valid_amount("d6"))
		self.assertFalse(Tables.valid_amount("60d6"))

	def test_buttons_follow_the_actions(self) :
		view = discord.ui.View()
		record = SimpleNamespace(id=1, actions=[{"kind" : "item", "name" : "Sword"}, {"kind" : "npc", "name" : "Rat"}],
		                         granted_to=[], fight_id=None)
		self.assertTrue(add_buttons(view, record))
		self.assertEqual(len(view.children), 2)
		done = SimpleNamespace(id=1, actions=record.actions, granted_to=[5], fight_id=9)
		self.assertFalse(add_buttons(discord.ui.View(), done))


class TestTableRecords(DatabaseTestCase) :

	def test_fantasy_pack_loads(self) :
		tables = TablePacks.load("fantasy")
		names = [table["name"] for table in tables]
		self.assertIn("Loot (Minor)", names)
		self.assertIn(("fantasy", "Fantasy"), TablePacks.available())
		# Every nested table the pack rolls is in the pack.
		lower = {name.lower() for name in names}
		for table in tables :
			for entry in table["entries"] :
				for nested in Tables.NESTED.findall(entry["text"]) :
					self.assertIn(nested.lower(), lower, f"{table['name']} rolls a missing table {nested}")
		with self.assertRaises(ValueError) :
			TablePacks.load("../secrets")

	def test_fantasy_pack_names_the_fantasy_gear_and_bestiary(self) :
		gear = Packs.load("fantasy")
		items = {item["name"].lower() for item in gear["items"]}
		bestiary = {entry["name"].lower() for entry in gear.get("bestiary", [])}
		for table in TablePacks.load("fantasy") :
			for entry in table["entries"] :
				for action in entry["actions"] :
					if action["kind"] == Tables.ITEM :
						self.assertIn(action["name"].lower(), items, f"{table['name']}: {action['name']}")
					elif action["kind"] == Tables.NPC :
						self.assertIn(action["name"].lower(), bestiary, f"{table['name']}: {action['name']}")

	def test_import_and_reimport(self) :
		added, skipped, missing = TablePacks.import_into(GUILD_ID, "fantasy", USER_ID)
		self.assertEqual(len(added), len(TablePacks.load("fantasy")))
		self.assertEqual(skipped, [])
		# The catalog and bestiary are empty here, so the pack's actions name things the server doesn't have.
		self.assertIn("item Arming Sword", missing)
		self.assertIn("bestiary entry Grey Wolf", missing)
		added, skipped, _ = TablePacks.import_into(GUILD_ID, "fantasy", USER_ID)
		self.assertEqual(added, [])
		self.assertIn("Trinkets", skipped)
		loot = RollTableTransactions().find(GUILD_ID, "loot (minor)")
		self.assertTrue(loot.luck)
		self.assertEqual(loot.pack, "fantasy")

	def test_rolling_an_imported_table(self) :
		TablePacks.import_into(GUILD_ID, "fantasy", USER_ID)

		def lookup(name) :
			table = RollTableTransactions().find(GUILD_ID, name)
			return (table.dice, RollTableTransactions().entries(table.id)) if table else None

		names = RollTableTransactions().find(GUILD_ID, "Tavern Names")
		random.seed(1)
		rolled = Tables.roll(RollTableTransactions().entries(names.id), names.dice, lookup)
		self.assertTrue(rolled.text.startswith("The "))
		self.assertNotIn("[[", rolled.text)
		self.assertEqual(rolled.notes, [])

	def test_update_replaces_entries(self) :
		table = RollTableTransactions().add(GUILD_ID, "Weather", Tables.parse("Rain\nSun").entries, dice="weights")
		self.assertIsNone(RollTableTransactions().add(GUILD_ID, "weather", []))
		RollTableTransactions().update(table.id, entries=Tables.parse("1-2: Fog").entries, dice="1d2", luck=True)
		entries = RollTableTransactions().entries(table.id)
		self.assertEqual([entry.text for entry in entries], ["Fog"])
		updated = RollTableTransactions().get(table.id)
		self.assertEqual((updated.dice, updated.luck), ("1d2", True))
		self.assertTrue(RollTableTransactions().delete(table.id))
		self.assertEqual(RollTableTransactions().entries(table.id), [])

	def test_rolls_are_kept(self) :
		table = RollTableTransactions().add(GUILD_ID, "Loot", Tables.parse("Gold | currency: 5").entries)
		record = RollTableTransactions().add_roll(GUILD_ID, table, USER_ID, natural=1, rolled=1, text="Gold",
		                                          actions=[{"kind" : "currency", "amount" : 5}])
		self.assertEqual((record.table_name, record.granted_to, record.secret), ("Loot", [], False))
		RollTableTransactions().update_roll(record.id, granted_to=[3])
		self.assertEqual(RollTableTransactions().get_roll(record.id).granted_to, [3])
