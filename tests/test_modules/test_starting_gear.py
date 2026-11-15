import asyncio

from classes.characters.Access import EVENT, LEVEL, STAFF_ONLY
from classes.characters.Card import Card, FIELD_LIMIT
from classes.characters.Interview import CREATE, CREATED, Interview
from classes.gear.Gear import ARMOR, CREATION, Gear, WEAPON
from classes.kernel.ConfigData import ConfigData
from database.transactions.CharacterGearTransactions import CharacterGearTransactions
from database.transactions.CurrencyTransactions import BUY, CurrencyTransactions, START
from database.transactions.DraftTransactions import DraftTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from database.transactions.TagRuleTransactions import TagRuleTransactions
from resources.configs.ConfigMapping import ConfigMapping
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID

GUILD_NAME = "Test server"
FORUM = 888
TAG_VETERAN, TAG_EVENT, TAG_STAFF = 701, 702, 703


def say(text) :
	return asyncio.run(Interview.answer(DraftTransactions().get(USER_ID), text))


def step() :
	return DraftTransactions().get(USER_ID).step


# The catalog as a member without roles sees it: 1 Sword, 2 Lance (level 2), 3 Bow, 4 Crown (staff), 5 Leather, 6 Plate.
# The Relic is an event item and is not shown.
class StartingGearTestCase(DatabaseTestCase) :
	"""A server without sheet questions, with point-buy only and 1500 currency to start with."""

	def setUp(self) :
		super().setUp()
		self.add_server()
		ConfigData().add_key(GUILD_ID, ConfigMapping.STAT_METHOD, "point_buy", overwrite=True)
		ConfigData().add_key(GUILD_ID, ConfigMapping.STARTING_CURRENCY, 1500, overwrite=True)
		items = GearItemTransactions()
		self.sword = items.add(GUILD_ID, WEAPON, "Sword", price=100, requirements={"strength" : 4})
		self.lance = items.add(GUILD_ID, WEAPON, "Lance", price=300, tag_ids=[TAG_VETERAN])
		self.bow = items.add(GUILD_ID, WEAPON, "Bow", price=600)
		self.relic = items.add(GUILD_ID, WEAPON, "Relic", price=5, tag_ids=[TAG_EVENT])
		self.crown = items.add(GUILD_ID, ARMOR, "Crown", price=1, tag_ids=[TAG_STAFF])
		self.leather = items.add(GUILD_ID, ARMOR, "Leather", price=200)
		self.plate = items.add(GUILD_ID, ARMOR, "Plate", price=1000, requirements={"strength" : 8})
		TagRuleTransactions().set(GUILD_ID, FORUM, TAG_EVENT, EVENT, None)
		TagRuleTransactions().set(GUILD_ID, FORUM, TAG_VETERAN, LEVEL, 2)
		TagRuleTransactions().set(GUILD_ID, FORUM, TAG_STAFF, STAFF_ONLY, None)

	@staticmethod
	def start() :
		return Interview.start(USER_ID, GUILD_ID, GUILD_NAME, CREATE)

	def to_gear(self) :
		self.start()
		say("Aria")
		say("Aria: text")
		return say("5 5 5 5 5 5 5")


class TestGearStep(StartingGearTestCase) :

	def test_the_step_comes_after_the_stats(self) :
		draft, _ = self.start()
		self.assertEqual(draft.answers["queue"], ["name", "trigger", "stats", "gear", "summary"])
		say("Aria")
		say("Aria: text")
		text = say("5 5 5 5 5 5 5").text
		self.assertIn("Pick your starting gear", text)
		self.assertIn("Left to spend: **1500 currency**", text)
		self.assertIn("1. **Sword** (weapon) · 100 currency · needs Strength 4", text)
		self.assertIn("2. **Lance**", text)
		self.assertIn("unavailable: needs server level 2", text)
		self.assertNotIn("Relic", text)
		self.assertIn("nothing yet", text)
		# Back goes to the stats, as from any other step.
		self.assertIn("Set your SPECIAL stats", say("back").text)

	def test_no_step_without_a_catalog(self) :
		for item in GearItemTransactions().get_all(GUILD_ID) :
			GearItemTransactions().delete(item.id)
		draft, _ = self.start()
		self.assertNotIn("gear", draft.answers["queue"])
		say("Aria")
		say("Aria: text")
		reply = say("5 5 5 5 5 5 5")
		self.assertIn("**Summary**", reply.text)
		self.assertNotIn("Starting gear", reply.text)

	def test_adding_and_removing(self) :
		self.to_gear()
		reply = say("1")
		self.assertIn("Added **Sword**", reply.text)
		self.assertIn("In your bag: Sword (100 of 1500 currency)", reply.text)
		self.assertIn("already in your bag", say("sword").text)
		self.assertIn("Added **Plate**", say("plate").text)
		self.assertIn("Sword, Plate, Leather (1300 of 1500 currency)", say("5").text)
		self.assertIn("Took **Sword** out", say("remove 1").text)
		self.assertIn("not in your bag", say("remove sword").text)
		self.assertIn("· in your bag", Interview.prompt(DraftTransactions().get(USER_ID)))
		self.assertEqual(DraftTransactions().get(USER_ID).answers["gear"], [self.plate.id, self.leather.id])
		self.assertEqual(step(), "gear")

	def test_locked_unknown_and_too_expensive_items_are_refused(self) :
		self.to_gear()
		self.assertIn("Lance needs server level 2", say("lance").text)
		self.assertIn("only given out by staff", say("4").text)
		self.assertIn("Please pick an item", say("relic").text)
		self.assertIn("Please pick an item", say("99").text)
		say("plate")
		reply = say("bow")
		self.assertIn("Bow costs 600 currency, but you only have 500 currency left", reply.text)
		self.assertEqual(DraftTransactions().get(USER_ID).answers["gear"], [self.plate.id])

	def test_free_mode_has_no_budget(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.ECONOMY, "free", overwrite=True)
		text = self.to_gear().text
		self.assertIn("Gear is free", text)
		self.assertNotIn("Left to spend", text)
		self.assertIn("**Sword** (weapon) · free", text)
		for name in ("plate", "bow", "leather", "sword") :
			self.assertIn("Added", say(name).text)
		reply = say("done")
		self.assertIn("**Starting gear:** Plate, Bow, Leather, Sword (free)", reply.text)
		character = say("submit").character
		self.assertEqual(character.currency, 1500)
		self.assertEqual([row.reason for row in CurrencyTransactions().get_all(character.id)], [START])
		self.assertEqual({entry.price_paid for entry in CharacterGearTransactions().get_all(character.id)}, {0})
		worn, _ = Gear.equipped_armor(character.id)
		self.assertEqual(worn.name, "Plate")


class TestSummary(StartingGearTestCase) :

	def test_the_summary_shows_the_bag_and_returns_to_it(self) :
		self.to_gear()
		say("sword")
		say("leather")
		reply = say("done")
		# 1 name, 2 speaks with, 3 SPECIAL, 4 starting gear
		self.assertIn("4. **Starting gear:** Sword, Leather (300 of 1500 currency)", reply.text)
		self.assertNotIn("Still needed", reply.text)
		self.assertIn("Pick your starting gear", say("4").text)
		say("remove leather")
		self.assertIn("**Starting gear:** Sword (100 of 1500 currency)", say("done").text)

	def test_gear_is_optional(self) :
		self.to_gear()
		reply = say("skip")
		self.assertIn("**Starting gear:** none", reply.text)
		self.assertNotIn("Still needed", reply.text)
		character = say("submit").character
		self.assertEqual(character.currency, 1500)
		self.assertEqual(CharacterGearTransactions().get_all(character.id), [])


class TestSubmit(StartingGearTestCase) :

	def test_submit_buys_the_bag(self) :
		self.to_gear()
		for name in ("sword", "leather", "plate", "done") :
			say(name)
		reply = say("submit")
		self.assertEqual(reply.outcome, CREATED)
		self.assertNotIn("could be bought", reply.text)
		character = reply.character
		self.assertEqual(character.currency, 200)
		ledger = CurrencyTransactions().get_all(character.id)
		self.assertEqual([(row.amount, row.reason, row.note, row.actor_uid) for row in ledger],
		                 [(-1000, BUY, "Plate", USER_ID), (-200, BUY, "Leather", USER_ID),
		                  (-100, BUY, "Sword", USER_ID), (1500, START, None, None)])
		entries = {entry.name : entry for entry in CharacterGearTransactions().get_all(character.id)}
		self.assertEqual({entry.source for entry in entries.values()}, {CREATION})
		self.assertEqual({name : entry.equipped for name, entry in entries.items()},
		                 {"Sword" : False, "Leather" : False, "Plate" : True})

	def test_items_removed_or_locked_before_submit_are_dropped(self) :
		self.to_gear()
		for name in ("sword", "bow", "leather", "done") :
			say(name)
		GearItemTransactions().delete(self.leather.id)
		GearItemTransactions().update(self.bow.id, tag_ids=[TAG_VETERAN])
		reply = say("submit")
		self.assertEqual(reply.outcome, CREATED)
		self.assertIn("1 item in your bag is no longer sold.", reply.text)
		self.assertIn("Bow needs server level 2.", reply.text)
		self.assertEqual([entry.name for entry in CharacterGearTransactions().get_all(reply.character.id)], ["Sword"])
		self.assertEqual(reply.character.currency, 1400)
		self.assertIsNone(Gear.equipped_armor(reply.character.id))

	def test_a_bag_that_no_longer_fits_stops_the_submit(self) :
		self.to_gear()
		for name in ("leather", "plate", "done") :
			say(name)
		ConfigData().add_key(GUILD_ID, ConfigMapping.STARTING_CURRENCY, 1000, overwrite=True)
		reply = say("submit")
		self.assertFalse(reply.finished)
		self.assertIn("now costs 1200 currency, more than the 1000 currency you start with", reply.text)
		self.assertIn("Pick your starting gear", reply.text)
		self.assertEqual(step(), "gear")
		say("remove leather")
		self.assertIn("**Summary**", say("done").text)
		reply = say("submit")
		self.assertEqual((reply.outcome, reply.character.currency), (CREATED, 0))


class TestCard(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()
		items = GearItemTransactions()
		self.sword = items.add(GUILD_ID, WEAPON, "Sword", price=100, requirements={"strength" : 4})
		self.plate = items.add(GUILD_ID, ARMOR, "Plate", price=1000, requirements={"strength" : 8, "agility" : 6})
		self.leather = items.add(GUILD_ID, ARMOR, "Leather", price=200)
		self.character = self.add_character()

	def fields(self) :
		return {field.name : field.value for field in Card.embeds(self.character)[0].fields}

	def test_no_gear_no_field(self) :
		self.assertNotIn("Gear", self.fields())

	def test_the_gear_field(self) :
		Gear.grant(self.character, self.leather, 1)
		Gear.equip(Gear.grant(self.character, self.sword, 1))
		Gear.equip(Gear.grant(self.character, self.plate, 1))
		self.assertEqual(self.fields()["Gear"], "Sword (equipped)\nPlate (worn; needs Strength 8, Agility 6)\nLeather")

	def test_a_long_inventory_is_cut_short(self) :
		for number in range(60) :
			item = GearItemTransactions().add(GUILD_ID, WEAPON, f"Very long sword name number {number:02d}")
			Gear.grant(self.character, item, 1)
		value = self.fields()["Gear"]
		self.assertLessEqual(len(value), FIELD_LIMIT)
		shown = value.count("Very long sword")
		self.assertTrue(value.endswith(f"…and {60 - shown} more"))
