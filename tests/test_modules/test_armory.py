import asyncio
import copy
from types import SimpleNamespace

import discord

from classes.characters.Special import STATS
from classes.gear.Gear import ARMOR, KINDS, WEAPON
from classes.gear.GearPost import GearPost
from classes.gear.Packs import ARMOR_COMBAT, Packs, WEAPON_COMBAT
from database.transactions.GearItemTransactions import GearItemTransactions
from listeners.GearListener import GearListener
from modules.Armory import Armory, MODIFIER_CHOICES
from test_modules.base import DatabaseTestCase, GUILD_ID

OTHER_GUILD = 1048433044253573121
GOOD_ITEM = {"kind" : WEAPON, "name" : "Test Blade", "description" : "A blade.", "price" : 100,
             "requirements" : {"strength" : 5}, "effect_met" : "+1 to hit", "effect_unmet" : "-1 to hit",
             "combat" : {"dice" : "1d8", "modifier" : "damage:strength", "hitmodifier" : 0}}


def pack_with(**changes) :
	"""A one-item pack whose item has the changes applied."""
	return {"name" : "test", "title" : "Test", "items" : [GOOD_ITEM | changes]}


class TestPacks(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()

	def test_fantasy_is_available_and_loads(self) :
		self.assertIn(("fantasy", "Fantasy"), Packs.available())
		pack = Packs.load("fantasy")
		self.assertEqual(pack["name"], "fantasy")
		self.assertEqual(pack["starting_currency"], 3000)
		weapons = [item for item in pack["items"] if item["kind"] == WEAPON]
		armor = [item for item in pack["items"] if item["kind"] == ARMOR]
		self.assertTrue(14 <= len(weapons) <= 18, len(weapons))
		self.assertTrue(8 <= len(armor) <= 12, len(armor))

	def test_every_fantasy_item_is_valid_and_sensible(self) :
		names = set()
		for item in Packs.load("fantasy")["items"] :
			with self.subTest(item=item["name"]) :
				self.assertEqual(Packs.validate_item(item), item)
				self.assertIn(item["kind"], KINDS)
				self.assertNotIn(item["name"].lower(), names)
				names.add(item["name"].lower())
				self.assertTrue(item["description"])
				self.assertLessEqual(item["price"], 3000)
				if item["requirements"] :
					self.assertTrue(item["effect_met"])
					self.assertTrue(item["effect_unmet"])
				for minimum in item["requirements"].values() :
					self.assertTrue(1 <= minimum <= 10)
				expected = WEAPON_COMBAT if item["kind"] == WEAPON else ARMOR_COMBAT
				self.assertEqual(set(item["combat"]), set(expected))

	def test_import_adds_everything_then_skips_everything(self) :
		count = len(Packs.load("fantasy")["items"])
		added, skipped = Packs.import_into(GUILD_ID, "fantasy")
		self.assertEqual((len(added), skipped), (count, []))
		catalog = GearItemTransactions().get_all(GUILD_ID)
		self.assertEqual(len(catalog), count)
		self.assertTrue(all(item.pack == "fantasy" for item in catalog))
		plate = GearItemTransactions().find(GUILD_ID, "warden's full plate")
		self.assertEqual(plate.kind, ARMOR)
		self.assertEqual(plate.requirements, {"strength" : 8, "endurance" : 6})
		self.assertEqual(plate.combat["ac"], 19)
		added, skipped = Packs.import_into(GUILD_ID, "fantasy")
		self.assertEqual((added, len(skipped)), ([], count))
		self.assertEqual(len(GearItemTransactions().get_all(GUILD_ID)), count)
		# Another server gets its own copy.
		added, _ = Packs.import_into(OTHER_GUILD, "fantasy")
		self.assertEqual(len(added), count)

	def test_import_skips_names_the_catalog_has_and_keeps_changes(self) :
		GearItemTransactions().add(GUILD_ID, WEAPON, "arming sword", price=1)
		added, skipped = Packs.import_into(GUILD_ID, "fantasy")
		self.assertEqual(skipped, ["Arming Sword"])
		self.assertEqual(GearItemTransactions().find(GUILD_ID, "Arming Sword").price, 1)
		self.assertNotIn("Arming Sword", [item.name for item in added])

	def test_missing_packs_raise(self) :
		for name in ("nope", "../fantasy", "", "Fantasy.json") :
			with self.subTest(name=name), self.assertRaises(ValueError) :
				Packs.load(name)
		with self.assertRaises(ValueError) :
			Packs.import_into(GUILD_ID, "nope")

	def test_bad_pack_data_raises(self) :
		bad = [
			[],
			{"items" : []},
			{"items" : "sword"},
			{"items" : [GOOD_ITEM], "starting_currency" : -5},
			pack_with(kind="shield"),
			pack_with(name=""),
			pack_with(name="x" * 101),
			pack_with(price=-1),
			pack_with(price="100"),
			pack_with(price=1.5),
			pack_with(price=True),
			pack_with(description=5),
			pack_with(requirements={"strenght" : 5}),
			pack_with(requirements={"strength" : 0}),
			pack_with(requirements={"strength" : 14}),
			pack_with(requirements={"strength" : "5"}),
			pack_with(requirements=["strength"]),
			pack_with(combat={"dice" : "d8"}),
			pack_with(combat={"dice" : 8}),
			pack_with(combat={"modifier" : "damage:mana"}),
			pack_with(combat={"modifier" : "strength"}),
			pack_with(combat={"hitmodifier" : "1"}),
			pack_with(combat={"hp" : 100}),
			pack_with(combat={"speed" : 3}),
			pack_with(combat="1d8"),
			pack_with(kind=ARMOR, combat={"ac" : "high"}),
			pack_with(kind=ARMOR, combat={"ac" : -1}),
			pack_with(kind=ARMOR, combat={"dice" : "1d6"}),
			{"items" : [GOOD_ITEM, GOOD_ITEM | {"name" : "test blade"}]},
		]
		for data in bad :
			with self.subTest(data=data), self.assertRaises(ValueError) :
				Packs.validate(copy.deepcopy(data), "test")

	def test_items_are_completed(self) :
		item = Packs.validate({"items" : [{"kind" : ARMOR, "name" : " Rags ", "combat" : {"ac" : 11}}]})["items"][0]
		self.assertEqual(item["name"], "Rags")
		self.assertEqual(item["price"], 0)
		self.assertEqual(item["requirements"], {})
		self.assertIsNone(item["effect"])
		self.assertEqual(item["combat"], ARMOR_COMBAT | {"ac" : 11})


class TestRequirementText(DatabaseTestCase) :

	def test_reads_requirements(self) :
		self.assertEqual(Packs.parse_requirements("strength 8, agility 4"), {"strength" : 8, "agility" : 4})
		self.assertEqual(Packs.parse_requirements("Str: 8; AGI=4"), {"strength" : 8, "agility" : 4})
		self.assertEqual(Packs.parse_requirements("intel 6,luck 1"), {"intelligence" : 6, "luck" : 1})
		self.assertEqual(Packs.parse_requirements("endurance 13,"), {"endurance" : 13})
		for empty in (None, "", "  ", "none", "-") :
			self.assertEqual(Packs.parse_requirements(empty), {})

	def test_every_stat_and_its_short_name(self) :
		for stat in STATS :
			self.assertEqual(Packs.parse_requirements(f"{stat} 5"), {stat : 5})
			self.assertEqual(Packs.parse_requirements(f"{stat[:3]} 5"), {stat : 5})

	def test_bad_requirements_say_why(self) :
		cases = {
			"mana 5"               : "not a SPECIAL stat",
			"st 5"                 : "not a SPECIAL stat",
			"strength 0"           : "from 1 to 13",
			"strength 14"          : "from 1 to 13",
			"strength -2"          : "from 1 to 13",
			"strength"             : "could not read",
			"strength eight"       : "could not read",
			"strength 5, str 6"    : "twice",
			"strength 5 agility 4" : "could not read",
		}
		for text, message in cases.items() :
			with self.subTest(text=text) :
				with self.assertRaises(ValueError) as caught :
					Packs.parse_requirements(text)
				self.assertIn(message, str(caught.exception))


class TestCombatValues(DatabaseTestCase) :

	def test_defaults_and_changes(self) :
		self.assertEqual(Packs.combat_for(WEAPON, None, {}), WEAPON_COMBAT)
		self.assertEqual(Packs.combat_for(ARMOR, None, {}), ARMOR_COMBAT)
		self.assertEqual(Packs.combat_for(WEAPON, None, {"dice" : "2D6", "modifier" : "Dice:Agility"}),
		                 {"dice" : "2d6", "modifier" : "dice:agility", "hitmodifier" : 0})
		self.assertEqual(Packs.combat_for(WEAPON, {"dice" : "1d8", "modifier" : "damage:strength"},
		                                  {"modifier" : "none", "hitmodifier" : None}),
		                 {"dice" : "1d8", "modifier" : "", "hitmodifier" : 0})
		self.assertEqual(Packs.combat_for(ARMOR, {"hp" : 120, "junk" : 1}, {"ac" : 18}),
		                 ARMOR_COMBAT | {"hp" : 120, "ac" : 18})

	def test_values_of_the_other_kind_are_refused(self) :
		with self.assertRaises(ValueError) as caught :
			Packs.combat_for(ARMOR, None, {"dice" : "1d6"})
		self.assertIn("only for weapons", str(caught.exception))
		with self.assertRaises(ValueError) as caught :
			Packs.combat_for(WEAPON, None, {"ac" : 14})
		self.assertIn("only for armor", str(caught.exception))

	def test_every_modifier_choice_is_accepted(self) :
		for choice in MODIFIER_CHOICES :
			Packs.combat_for(WEAPON, None, {"modifier" : choice.value})

	def test_combat_text(self) :
		weapon = SimpleNamespace(kind=WEAPON, combat={"dice" : "1d8", "modifier" : "damage:strength",
		                                              "hitmodifier" : 1})
		self.assertEqual(GearPost.combat_text(weapon), "1d8 + Strength damage · +1 to hit")
		armor = SimpleNamespace(kind=ARMOR, combat={"hp" : 90, "ap" : 30, "ac" : 15, "hitchance" : -1})
		self.assertEqual(GearPost.combat_text(armor), "HP 90 · AP 30 · AC 15 · -1 to hit")
		self.assertEqual(GearPost.combat_text(SimpleNamespace(kind=ARMOR, combat={})), "")


class TestArmoryHelpers(DatabaseTestCase) :

	def test_text_update(self) :
		self.assertEqual(Armory.text_update(None), (False, None))
		self.assertEqual(Armory.text_update("-"), (True, None))
		self.assertEqual(Armory.text_update(" Glows. "), (True, "Glows."))

	def test_combat_changes(self) :
		choice = discord.app_commands.Choice(name="None", value="none")
		self.assertEqual(Armory.combat_changes(dice="1d6", modifier=choice, ac=None),
		                 {"dice" : "1d6", "modifier" : "none"})
		self.assertEqual(Armory.combat_changes(hitchance=0), {"hitchance" : 0})

	def test_long_lists_are_split(self) :
		lines = [f"**Item {number}** (weapon) · {number} caps · needs Strength 5" for number in range(300)]
		embeds = Armory.pages("Weapons", lines)
		self.assertGreater(len(embeds), 1)
		self.assertTrue(all(len(embed.description) <= 4000 for embed in embeds))
		self.assertEqual(embeds[1].title, "Weapons (continued)")
		self.assertEqual("\n".join(embed.description for embed in embeds), "\n".join(lines))
		batches = Armory.batches(embeds)
		self.assertEqual(sum(len(batch) for batch in batches), len(embeds))
		self.assertTrue(all(sum(len(embed) for embed in batch) <= 6000 and len(batch) <= 10 for batch in batches))
		self.assertEqual(Armory.pages("Armor", []), [])


class TestGearPostsAndListener(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()
		self.item = GearItemTransactions().add(GUILD_ID, WEAPON, "Sword", price=10, tag_ids=[5],
		                                       forum_thread_id=111, forum_message_id=111)

	def test_sync_without_a_gear_forum_does_nothing(self) :
		self.assertFalse(GearPost.configured(GUILD_ID))
		self.assertFalse(asyncio.run(GearPost.sync(None, self.item)))

	def test_thread_tags_are_stored(self) :
		listener = GearListener(None)
		asyncio.run(listener.on_raw_thread_update(SimpleNamespace(thread_id=111, data={"applied_tags" : ["9", "7"]})))
		self.assertEqual(GearItemTransactions().get(self.item.id).tag_ids, [7, 9])
		# Updates without tags, and posts that are not gear, change nothing.
		asyncio.run(listener.on_raw_thread_update(SimpleNamespace(thread_id=111, data={"name" : "Sword"})))
		asyncio.run(listener.on_raw_thread_update(SimpleNamespace(thread_id=222, data={"applied_tags" : []})))
		self.assertEqual(GearItemTransactions().get(self.item.id).tag_ids, [7, 9])
		asyncio.run(listener.on_raw_thread_update(SimpleNamespace(thread_id=111, data={"applied_tags" : []})))
		self.assertEqual(GearItemTransactions().get(self.item.id).tag_ids, [])

	def test_a_deleted_post_keeps_the_tags(self) :
		asyncio.run(GearListener(None).on_raw_thread_delete(SimpleNamespace(thread_id=111)))
		item = GearItemTransactions().get(self.item.id)
		self.assertIsNone(item.forum_thread_id)
		self.assertIsNone(item.forum_message_id)
		self.assertEqual(item.tag_ids, [5])
