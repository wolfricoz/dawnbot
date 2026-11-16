"""Phase 1 of design/economy.md: defaults, rarity, Charisma pricing, catalog-based selling, price hints and the
economy report."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from classes.characters.Access import Access
from classes.economy import FactionFlow, Report
from classes.economy.FactionFlow import IDOLIZED
from classes.gear import Pricing, Rarity
from classes.gear.Gear import ARMOR, CREATION, Gear, MASTERWORK, WEAPON
from classes.gear.Packs import Packs
from classes.kernel.ConfigData import ConfigData
from database.transactions.CharacterGearTransactions import CharacterGearTransactions
from database.transactions.CurrencyTransactions import BUY, CurrencyTransactions, ROLEPLAY
from database.transactions.EconomyTransactions import EconomyTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from resources.configs.ConfigMapping import ConfigMapping, defaults
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID


def member_access() :
	return Access()


class MoneyTestCase(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()
		items = GearItemTransactions()
		self.sword = items.add(GUILD_ID, WEAPON, "Sword", price=1000)
		self.plate = items.add(GUILD_ID, ARMOR, "Plate", price=2000)
		self.relic = items.add(GUILD_ID, WEAPON, "Relic", price=100, rarity=Rarity.LEGENDARY)


class TestDefaults(MoneyTestCase) :

	def test_new_defaults(self) :
		self.assertEqual(defaults[ConfigMapping.STARTING_CURRENCY], 1500)
		self.assertEqual(defaults[ConfigMapping.CURRENCY_GAIN], 8)
		self.assertEqual(defaults[ConfigMapping.WORK_PAY], 125)

	def test_a_server_setting_wins_over_the_default(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.STARTING_CURRENCY, 3000, overwrite=True)
		self.assertEqual(ConfigData().get_int(GUILD_ID, ConfigMapping.STARTING_CURRENCY), 3000)


class TestRarity(MoneyTestCase) :

	def test_price_bands(self) :
		self.assertEqual(Rarity.from_price(0), Rarity.COMMON)
		self.assertEqual(Rarity.from_price(1000), Rarity.COMMON)
		self.assertEqual(Rarity.from_price(1001), Rarity.UNCOMMON)
		self.assertEqual(Rarity.from_price(1500), Rarity.UNCOMMON)
		self.assertEqual(Rarity.from_price(3500), Rarity.RARE)
		self.assertEqual(Rarity.from_price(3501), Rarity.VERY_RARE)
		self.assertEqual(Rarity.from_price(15000), Rarity.VERY_RARE)

	def test_an_item_takes_its_rarity_from_the_price_unless_set(self) :
		self.assertEqual(Rarity.of(self.plate), Rarity.RARE)
		self.assertEqual(Rarity.of(self.relic), Rarity.LEGENDARY)

	def test_parse(self) :
		self.assertEqual(Rarity.parse("Very rare"), Rarity.VERY_RARE)
		self.assertEqual(Rarity.parse("very-rare"), Rarity.VERY_RARE)
		self.assertIsNone(Rarity.parse("auto"))
		self.assertIsNone(Rarity.parse(None))
		with self.assertRaises(ValueError) :
			Rarity.parse("mythic")

	def test_legendary_items_are_never_sold(self) :
		character = self.add_character(currency=5000)
		self.assertIsNotNone(Gear.lock_reason(self.relic, member_access()))
		entry, problem = Gear.buy(character, self.relic, member_access(), USER_ID)
		self.assertIsNone(entry)
		self.assertIn("legendary", problem)
		# A GM can still grant one.
		self.assertIsNotNone(Gear.grant(character, self.relic, USER_ID))

	def test_packs_read_a_rarity(self) :
		item = Packs.validate_item({"kind" : WEAPON, "name" : "Old Blade", "price" : 10, "rarity" : "rare"})
		self.assertEqual(item["rarity"], Rarity.RARE)
		with self.assertRaises(ValueError) :
			Packs.validate_item({"kind" : WEAPON, "name" : "Old Blade", "price" : 10, "rarity" : "shiny"})


class TestCharismaPricing(MoneyTestCase) :

	def test_buy_multiplier(self) :
		self.assertAlmostEqual(Pricing.buy_multiplier(self.add_character("Avg", charisma=5)), 1.0)
		self.assertAlmostEqual(Pricing.buy_multiplier(self.add_character("Smooth", charisma=8)), 0.91)
		# At most 15% off, however charming.
		self.assertAlmostEqual(Pricing.buy_multiplier(self.add_character("Silver", charisma=20)), 0.85)
		# No limit on the extra cost.
		self.assertAlmostEqual(Pricing.buy_multiplier(self.add_character("Rude", charisma=-2)), 1.21)

	def test_sell_rate(self) :
		self.assertAlmostEqual(Pricing.sell_rate(self.add_character("Avg", charisma=5)), 0.30)
		self.assertAlmostEqual(Pricing.sell_rate(self.add_character("Smooth", charisma=8)), 0.36)
		self.assertAlmostEqual(Pricing.sell_rate(self.add_character("Silver", charisma=20)), 0.40)
		self.assertAlmostEqual(Pricing.sell_rate(self.add_character("Rude", charisma=0)), 0.20)

	def test_buying_charges_the_charisma_price(self) :
		character = self.add_character(charisma=8, currency=5000)
		entry, problem = Gear.buy(character, self.sword, member_access(), USER_ID)
		self.assertIsNone(problem)
		self.assertEqual(entry.price_paid, 910)
		rows = CurrencyTransactions().get_all(character.id)
		self.assertEqual([(row.amount, row.reason) for row in rows], [(-910, BUY)])

	def test_starting_gear_costs_the_catalog_price(self) :
		character = self.add_character(charisma=1, currency=5000)
		entry, _ = Gear.buy(character, self.sword, member_access(), USER_ID, source=CREATION)
		self.assertEqual(entry.price_paid, 1000)

	def test_faction_discounts_stack_but_never_pass_35_percent(self) :
		faction = EconomyTransactions().add_faction(GUILD_ID, "Guild")
		GearItemTransactions().update(self.sword.id, faction_id=faction.id)
		sword = GearItemTransactions().get(self.sword.id)
		character = self.add_character(charisma=20, currency=5000)
		EconomyTransactions().set_standing(character.id, faction.id, 80, 80, "test", USER_ID)
		# 0.85 for Charisma × 0.8 for Idolized = 0.68.
		self.assertEqual(Pricing.buy_price(character, sword), 680)
		# A bigger faction discount still stops at 35% off in total.
		with patch.dict(FactionFlow.PRICE, {IDOLIZED : 0.5}) :
			self.assertEqual(Pricing.buy_price(character, sword), 650)

	def test_free_mode_costs_nothing(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.ECONOMY, "free", overwrite=True)
		character = self.add_character(charisma=1)
		self.assertEqual(Pricing.buy_price(character, self.sword), 0)


class TestSelling(MoneyTestCase) :

	def test_selling_is_based_on_the_catalog_price(self) :
		character = self.add_character(currency=0)
		entry = Gear.grant(character, self.sword, USER_ID)
		# Granted for free, but sells for 30% of the 1000 catalog price.
		self.assertEqual(Gear.sell_value(entry), 300)
		received, problem = Gear.sell(entry, USER_ID)
		self.assertEqual((received, problem), (300, None))

	def test_charisma_and_masterwork_change_the_sale(self) :
		character = self.add_character(charisma=10, currency=0)
		entry = Gear.grant(character, self.sword, USER_ID)
		CharacterGearTransactions().update(entry.id, quality=MASTERWORK)
		entry = CharacterGearTransactions().get(entry.id)
		# 40% × 1.5.
		self.assertEqual(Gear.sell_value(entry), 600)

	def test_an_item_gone_from_the_catalog_sells_by_what_was_paid(self) :
		character = self.add_character(currency=5000)
		entry, _ = Gear.buy(character, self.sword, member_access(), USER_ID)
		GearItemTransactions().delete(self.sword.id)
		entry = CharacterGearTransactions().get(entry.id)
		self.assertEqual(Gear.sell_value(entry), 300)

	def test_buying_and_selling_never_pays(self) :
		character = self.add_character(charisma=30, currency=5000)
		entry, _ = Gear.buy(character, self.sword, member_access(), USER_ID)
		self.assertLess(Gear.sell_value(entry), entry.price_paid)


class TestPriceHints(MoneyTestCase) :

	def test_weapon_and_armor_suggestions(self) :
		sword = Packs.combat_for(WEAPON, None, {"dice" : "2d6"})
		self.assertTrue(200 <= Pricing.suggest(WEAPON, sword, {"strength" : 4}) <= 400)
		plate = Packs.combat_for(ARMOR, None, {"ac" : 4, "dt" : 3})
		self.assertEqual(Pricing.suggest(ARMOR, plate), 2550)

	def test_no_suggestion_without_values(self) :
		self.assertIsNone(Pricing.suggest("material", {}))
		self.assertEqual(Pricing.suggestion_text("material", {}, {}, 10, GUILD_ID), "")

	def test_suggestion_text_compares_the_price(self) :
		plate = Packs.combat_for(ARMOR, None, {"ac" : 4, "dt" : 3})
		self.assertIn("below", Pricing.suggestion_text(ARMOR, plate, {}, 100, GUILD_ID))
		self.assertIn("above", Pricing.suggestion_text(ARMOR, plate, {}, 99999, GUILD_ID))
		self.assertNotIn("set is", Pricing.suggestion_text(ARMOR, plate, {}, 2550, GUILD_ID))


class TestReport(MoneyTestCase) :

	def test_report(self) :
		rich = self.add_character("Rich", currency=900)
		poor = self.add_character("Poor", currency=100)
		self.add_character("Waiting", state="pending", currency=5000)
		ledger = CurrencyTransactions()
		ledger.log(rich.id, GUILD_ID, 200, ROLEPLAY, USER_ID)
		ledger.log(poor.id, GUILD_ID, 50, ROLEPLAY, USER_ID)
		ledger.log(rich.id, GUILD_ID, -300, BUY, USER_ID, "Sword")
		report = Report.build(GUILD_ID)
		self.assertEqual((report.characters, report.total, report.median), (2, 1000, 500))
		self.assertEqual(report.income, [(ROLEPLAY, 250, 2)])
		self.assertEqual(report.spending, [(BUY, -300, 1)])
		self.assertEqual(report.richest[0], ("Rich", 900))
		self.assertEqual(report.earners, [("Rich", 200), ("Poor", 50)])
		fields = Report.lines(report, "caps")
		self.assertIn("250 caps came in and 300 went out", fields["Last 7 days"])
		self.assertIn("roleplay posts: 250 (2×)", fields["Came in"])

	def test_old_changes_fall_outside_the_window(self) :
		character = self.add_character(currency=100)
		CurrencyTransactions().log(character.id, GUILD_ID, 50, ROLEPLAY, USER_ID)
		later = datetime.now(timezone.utc) + timedelta(days=30)
		self.assertEqual(Report.build(GUILD_ID, now=later).income, [])
