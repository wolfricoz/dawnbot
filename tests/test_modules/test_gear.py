from classes.characters.Access import Access, EVENT, LEVEL, STAFF_ONLY
from classes.combat.Loadout import Loadout
from classes.gear.Gear import ARMOR, CREATION, Gear, GRANTED, SHOP, WEAPON
from classes.kernel.ConfigData import ConfigData
from database.transactions.CharacterGearTransactions import BROKEN, CharacterGearTransactions, LOST, OWNED, SOLD
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.CurrencyTransactions import BUY, CurrencyTransactions, GM_GIVE, GM_TAKE, SELL
from database.transactions.GearItemTransactions import GearItemTransactions
from database.transactions.TagRuleTransactions import TagRuleTransactions
from resources.configs.ConfigMapping import ConfigMapping
from test_modules.base import DatabaseTestCase, GUILD_ID

FORUM = 888
TAG_VETERAN, TAG_EVENT, TAG_STAFF = 701, 702, 703


class GearTestCase(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()
		items = GearItemTransactions()
		self.sword = items.add(GUILD_ID, WEAPON, "Sword", price=100, requirements={"strength" : 4},
		                       combat={"dice" : "1d8"})
		self.plate = items.add(GUILD_ID, ARMOR, "Plate", price=1000, requirements={"strength" : 8},
		                       combat={"hp" : 120, "ap" : 40, "ac" : 18})
		self.leather = items.add(GUILD_ID, ARMOR, "Leather", price=200, combat={"ac" : 13})
		self.relic = items.add(GUILD_ID, WEAPON, "Relic", price=5, tag_ids=[TAG_EVENT])
		self.lance = items.add(GUILD_ID, WEAPON, "Lance", price=300, tag_ids=[TAG_VETERAN])
		self.crown = items.add(GUILD_ID, ARMOR, "Crown", price=1, tag_ids=[TAG_STAFF])
		TagRuleTransactions().set(GUILD_ID, FORUM, TAG_EVENT, EVENT, None)
		TagRuleTransactions().set(GUILD_ID, FORUM, TAG_VETERAN, LEVEL, 2)
		TagRuleTransactions().set(GUILD_ID, FORUM, TAG_STAFF, STAFF_ONLY, None)
		self.character = self.add_character(currency=1500)


class TestCatalog(GearTestCase) :

	def test_names_are_unique_and_items_are_ordered(self) :
		self.assertIsNone(GearItemTransactions().add(GUILD_ID, WEAPON, "sword"))
		names = [item.name for item in GearItemTransactions().get_all(GUILD_ID)]
		self.assertEqual(names, ["Relic", "Sword", "Lance", "Crown", "Leather", "Plate"])
		self.assertEqual([item.name for item in GearItemTransactions().get_all(GUILD_ID, ARMOR)],
		                 ["Crown", "Leather", "Plate"])

	def test_the_shop_hides_event_items_and_marks_locked_ones(self) :
		shop = {entry.item.name : entry for entry in Gear.shop_items(GUILD_ID, Access(level=1))}
		self.assertNotIn("Relic", shop)
		self.assertIsNone(shop["Sword"].locked)
		self.assertIn("level 2", shop["Lance"].locked)
		self.assertIn("staff", shop["Crown"].locked)
		self.assertEqual(shop["Plate"].price, 1000)
		staff = {entry.item.name for entry in Gear.shop_items(GUILD_ID, Access(staff=True))}
		self.assertIn("Relic", staff)

	def test_requirements(self) :
		self.assertEqual(Gear.unmet_requirements(Gear.stats_of(self.character), self.plate), ["Strength 8"])
		self.assertEqual(Gear.unmet_requirements(Gear.stats_of(self.character), self.sword), [])


class TestBuyingAndSelling(GearTestCase) :

	def test_buy(self) :
		entry, problem = Gear.buy(self.character, self.sword, Access(), 1)
		self.assertIsNone(problem)
		self.assertEqual((entry.name, entry.kind, entry.source, entry.price_paid, entry.status),
		                 ("Sword", WEAPON, SHOP, 100, OWNED))
		self.assertEqual(CharacterTransactions().get_by_id(self.character.id).currency, 1400)
		ledger = CurrencyTransactions().get_all(self.character.id)
		self.assertEqual([(row.amount, row.reason, row.note) for row in ledger], [(-100, BUY, "Sword")])

	def test_buying_needs_enough_currency_and_access(self) :
		self.assertIsNotNone(Gear.buy(self.character, self.plate, Access(), 1)[0])
		entry, problem = Gear.buy(self.character, self.plate, Access(), 1)
		self.assertIsNone(entry)
		self.assertIn("500", problem)
		self.assertIn("level 2", Gear.buy(self.character, self.lance, Access(level=1), 1)[1])
		self.assertIn("staff", Gear.buy(self.character, self.relic, Access(staff=True), 1)[1])
		self.assertEqual(CharacterTransactions().get_by_id(self.character.id).currency, 500)

	def test_free_mode(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.ECONOMY, "free", overwrite=True)
		entry, _ = Gear.buy(self.character, self.plate, Access(), 1)
		self.assertEqual(entry.price_paid, 0)
		self.assertEqual(Gear.sell(entry, 1)[0], 0)
		self.assertEqual(CharacterTransactions().get_by_id(self.character.id).currency, 1500)
		self.assertEqual(CurrencyTransactions().get_all(self.character.id), [])

	def test_sell_returns_thirty_percent_of_what_was_paid(self) :
		entry, _ = Gear.buy(self.character, self.plate, Access(), 1)
		self.assertEqual(Gear.sell(entry, 1), (300, None))
		self.assertEqual(CharacterTransactions().get_by_id(self.character.id).currency, 800)
		entry = CharacterGearTransactions().get(entry.id)
		self.assertEqual(entry.status, SOLD)
		self.assertIn("sold", Gear.sell(entry, 1)[1])
		self.assertEqual([row.reason for row in CurrencyTransactions().get_all(self.character.id)], [SELL, BUY])

	def test_grant_lose_break_take(self) :
		relic = Gear.grant(self.character, self.relic, 1)
		self.assertEqual((relic.source, relic.price_paid), (GRANTED, 0))
		lost, _ = Gear.set_status(relic, LOST, 1)
		self.assertEqual(lost.status, LOST)
		self.assertIn("already lost", Gear.set_status(lost, BROKEN, 1)[1])
		self.assertEqual(Gear.inventory(self.character.id), [])
		self.assertEqual(len(Gear.inventory(self.character.id, include_gone=True)), 1)
		self.assertTrue(Gear.take(lost))
		self.assertEqual(Gear.inventory(self.character.id, include_gone=True), [])

	def test_gm_currency(self) :
		self.assertEqual(Gear.give_currency(self.character, 50, 9, "event")[0].currency, 1550)
		self.assertIsNotNone(Gear.take_currency(self.character, 2000, 9)[1])
		self.assertEqual(Gear.take_currency(self.character, 550, 9)[0].currency, 1000)
		self.assertEqual([(row.amount, row.reason) for row in CurrencyTransactions().get_all(self.character.id)],
		                 [(-550, GM_TAKE), (50, GM_GIVE)])

	def test_a_removed_catalog_item_stays_owned_by_name(self) :
		entry, _ = Gear.buy(self.character, self.sword, Access(), 1)
		GearItemTransactions().delete(self.sword.id)
		inventory = Gear.inventory(self.character.id)
		self.assertEqual([(owned.name, item) for owned, item in inventory], [("Sword", None)])


class TestEquipping(GearTestCase) :

	def test_one_armor_at_a_time(self) :
		plate = Gear.grant(self.character, self.plate, 1)
		leather = Gear.grant(self.character, self.leather, 1)
		sword = Gear.grant(self.character, self.sword, 1)
		self.assertIsNone(Gear.equipped_armor(self.character.id))
		Gear.equip(plate)
		Gear.equip(sword)
		Gear.equip(leather)
		worn, item = Gear.equipped_armor(self.character.id)
		self.assertEqual((worn.name, item.name), ("Leather", "Leather"))
		self.assertTrue(CharacterGearTransactions().get(sword.id).equipped)
		self.assertFalse(CharacterGearTransactions().get(plate.id).equipped)
		# Broken armor stays worn (it gives nothing in a fight until repaired).
		Gear.set_status(CharacterGearTransactions().get(leather.id), BROKEN, 1)
		worn, _ = Gear.equipped_armor(self.character.id)
		self.assertEqual((worn.name, worn.condition), ("Leather", BROKEN))

	def test_combat_uses_the_equipped_armor(self) :
		self.assertEqual(Loadout.character_stats(self.character)["armor"]["name"], "No armor")
		Gear.equip(Gear.grant(self.character, self.plate, 1))
		armor = Loadout.character_stats(self.character)["armor"]
		# Old-style values are converted by their AC: 18 is heavy armor, +3 AC, DT 3.
		self.assertEqual((armor["name"], armor["armor_class"], armor["ac"], armor["dt"]), ("Plate", "heavy", 3, 3))
		Gear.equip(Gear.grant(self.character, self.leather, 1))
		armor = Loadout.character_stats(self.character)["armor"]
		self.assertEqual((armor["armor_class"], armor["ac"], armor["dt"]), ("light", 1, 0))

	def test_creation_source_is_kept(self) :
		entry = CharacterGearTransactions().add(self.character.id, self.sword.id, "Sword", WEAPON, CREATION, 100)
		self.assertEqual(entry.source, CREATION)
