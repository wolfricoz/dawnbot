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
from modules.Armory import Armory
from test_modules.base import DatabaseTestCase, GUILD_ID

OTHER_GUILD = 1048433044253573121
GOOD_ITEM = {"kind" : WEAPON, "name" : "Test Blade", "description" : "A blade.", "price" : 100,
             "requirements" : {"strength" : 5}, "effect_met" : "+1 to hit", "effect_unmet" : "-1 to hit",
             "combat" : {"type" : "Slashing", "dice" : "1d8", "attack_stat" : "strength", "damage_stat" : "strength",
                         "hit_mod" : 0, "range" : "melee", "properties" : []}}


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
		self.assertTrue(14 <= len(weapons) <= 20, len(weapons))
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
		self.assertEqual((plate.combat["armor_class"], plate.combat["ac"], plate.combat["dt"]), ("heavy", 4, 3))
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
			pack_with(combat={"attack_stat" : "mana"}),
			pack_with(combat={"range" : "far"}),
			pack_with(combat={"properties" : ["huge"]}),
			pack_with(combat={"hit_mod" : 11}),
			pack_with(kind=ARMOR, combat={"armor_class" : "plate"}),
			pack_with(kind=ARMOR, combat={"dt" : 11}),
			{"items" : [GOOD_ITEM, GOOD_ITEM | {"name" : "test blade"}]},
		]
		for data in bad :
			with self.subTest(data=data), self.assertRaises(ValueError) :
				Packs.validate(copy.deepcopy(data), "test")

	def test_items_are_completed(self) :
		item = Packs.validate({"items" : [{"kind" : ARMOR, "name" : " Rags ", "combat" : {"ac" : 1}}]})["items"][0]
		self.assertEqual(item["name"], "Rags")
		self.assertEqual(item["price"], 0)
		self.assertEqual(item["requirements"], {})
		self.assertIsNone(item["effect"])
		self.assertEqual(item["combat"], ARMOR_COMBAT | {"ac" : 1})


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
		self.assertEqual(Packs.combat_for(WEAPON, None, {"dice" : "2D6", "attack_stat" : "agi", "damage_stat" : "none",
		                                                 "properties" : "light, Two handed", "ap" : 4}),
		                 WEAPON_COMBAT | {"dice" : "2d6", "attack_stat" : "agility", "damage_stat" : None,
		                                  "properties" : ["light", "two_handed"], "ap" : 4})
		current = Packs.combat_for(WEAPON, None, {"type" : "Fire"})
		self.assertEqual(Packs.combat_for(WEAPON, current, {"type" : "none", "hit_mod" : None})["type"], None)
		self.assertEqual(Packs.combat_for(ARMOR, {"armor_class" : "light", "junk" : 1}, {"ac" : 2}),
		                 ARMOR_COMBAT | {"armor_class" : "light", "ac" : 2})

	def test_old_values_are_converted(self) :
		self.assertEqual(Packs.combat_for(WEAPON, None, {"dice" : "1d8", "modifier" : "damage:agility",
		                                                 "hitmodifier" : 1}),
		                 WEAPON_COMBAT | {"dice" : "1d8", "attack_stat" : "agility", "damage_stat" : "agility",
		                                  "hit_mod" : 1})
		self.assertEqual(Packs.combat_for(ARMOR, {"hp" : 120, "ac" : 18}, {}),
		                 ARMOR_COMBAT | {"armor_class" : "heavy", "ac" : 3, "dt" : 3})
		self.assertEqual(Packs.combat_for(ARMOR, {"hp" : 120, "ac" : 18}, {"dt" : 2})["dt"], 2)

	def test_values_of_the_other_kind_are_refused(self) :
		with self.assertRaises(ValueError) as caught :
			Packs.combat_for(ARMOR, None, {"dice" : "1d6"})
		self.assertIn("only for weapons", str(caught.exception))
		with self.assertRaises(ValueError) as caught :
			Packs.combat_for(WEAPON, None, {"dt" : 2})
		self.assertIn("only for armor", str(caught.exception))

	def test_refresh_rewrites_pack_items(self) :
		self.add_server()
		Packs.import_into(GUILD_ID, "fantasy")
		sword = GearItemTransactions().find(GUILD_ID, "Arming Sword")
		GearItemTransactions().update(sword.id, combat={"dice" : "1d8", "modifier" : "damage:strength"}, price=7)
		GearItemTransactions().add(GUILD_ID, WEAPON, "Homemade", combat={"dice" : "1d4"})
		updated = Packs.refresh_into(GUILD_ID, "fantasy")
		self.assertEqual([item.name for item in updated], ["Arming Sword"])
		sword = GearItemTransactions().find(GUILD_ID, "Arming Sword")
		self.assertEqual((sword.combat["dice"], sword.combat["type"], sword.price), ("2d6", "Slashing", 7))

	def test_combat_text(self) :
		weapon = SimpleNamespace(kind=WEAPON, combat={"type" : "Slashing", "dice" : "2d6", "attack_stat" : "strength",
		                                              "damage_stat" : "strength", "hit_mod" : 1, "range" : "melee",
		                                              "properties" : ["two_handed"]})
		self.assertEqual(GearPost.combat_text(weapon), "2d6 + STR · Slashing · STR to hit, +1 · melee · 4 AP · two handed")
		old = SimpleNamespace(kind=WEAPON, combat={"dice" : "1d8", "modifier" : "", "hitmodifier" : 0})
		self.assertEqual(GearPost.combat_text(old), "1d8 · PER to hit · ranged · 3 AP")
		armor = SimpleNamespace(kind=ARMOR, combat={"armor_class" : "medium", "ac" : 2, "dt" : 2, "hit_mod" : 0,
		                                            "ability_hit_mod" : 1})
		self.assertEqual(GearPost.combat_text(armor), "Medium armor · AC +2 · DT 2 · +1 to hit with abilities")
		self.assertEqual(GearPost.combat_text(SimpleNamespace(kind=ARMOR, combat={})), "")


class TestArmoryHelpers(DatabaseTestCase) :

	def test_text_update(self) :
		self.assertEqual(Armory.text_update(None), (False, None))
		self.assertEqual(Armory.text_update("-"), (True, None))
		self.assertEqual(Armory.text_update(" Glows. "), (True, "Glows."))

	def test_combat_changes(self) :
		choice = discord.app_commands.Choice(name="None", value="none")
		self.assertEqual(Armory.combat_changes(dice="1d6", damage_stat=choice, ac=None),
		                 {"dice" : "1d6", "damage_stat" : "none"})
		self.assertEqual(Armory.combat_changes(dt=0, ap_cost=4), {"dt" : 0, "ap" : 4})

	def test_damage_types_are_checked(self) :
		self.add_server()
		changes = {"type" : "fire"}
		Armory.check_type(GUILD_ID, changes)
		self.assertEqual(changes["type"], "Fire")
		with self.assertRaises(ValueError) :
			Armory.check_type(GUILD_ID, {"type" : "Plasma"})
		Armory.check_type(GUILD_ID, {"type" : "none"})

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
