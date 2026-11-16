"""Phase 4 of design/economy.md: merchants, stock and restocks, haggling, services, lodging and stashes, shop modes."""
from datetime import datetime, timedelta, timezone

from classes.characters.Access import Access
from classes.economy import Merchants
from classes.gear import Carry, Condition, Rarity
from classes.gear.Gear import ARMOR, Gear, WEAPON
from classes.kernel.ConfigData import ConfigData
from database.transactions.CharacterGearTransactions import CharacterGearTransactions, OWNED
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.CurrencyTransactions import CurrencyTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from database.transactions.MerchantTransactions import MerchantTransactions
from database.transactions.WorldTransactions import WorldTransactions
from resources.configs.ConfigMapping import ConfigMapping
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID


class FixedRng :

	def __init__(self, *numbers) :
		self.numbers = list(numbers)

	def randint(self, low, high) :
		value = self.numbers.pop(0) if len(self.numbers) > 1 else self.numbers[0]
		return max(low, min(high, value))


class MerchantTestCase(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()
		items = GearItemTransactions()
		self.sword = items.add(GUILD_ID, WEAPON, "Sword", price=1000, weight=2)
		self.plate = items.add(GUILD_ID, ARMOR, "Plate", price=3000, weight=20)
		self.ingot = items.add(GUILD_ID, "material", "Iron Ingot", price=20)
		self.town = WorldTransactions().save_location(GUILD_ID, 501, name="Town")
		self.woods = WorldTransactions().save_location(GUILD_ID, 502, name="Woods")
		self.merchant = MerchantTransactions().add(GUILD_ID, "Greta", location_ids=[self.town.id], markup=1.2,
		                                           buys=[WEAPON], pays=0.5, services=[Merchants.REPAIR,
		                                                                              Merchants.LODGING],
		                                           lodging_price=100, haggle_dc=12)
		self.line = MerchantTransactions().set_stock(self.merchant.id, self.sword.id, quantity=2, in_stock=2)
		self.character = self.add_character(currency=10000)

	def merchant_now(self) :
		return MerchantTransactions().get(self.merchant.id)

	def line_now(self) :
		return MerchantTransactions().stock_entry(self.merchant.id, self.sword.id)


class TestPricesAndStock(MerchantTestCase) :

	def test_where_merchants_trade(self) :
		self.assertTrue(Merchants.trades_at(self.merchant, self.town.id))
		self.assertFalse(Merchants.trades_at(self.merchant, self.woods.id))
		self.assertFalse(Merchants.trades_at(self.merchant, None))
		wanderer = MerchantTransactions().add(GUILD_ID, "Wanderer")
		self.assertTrue(Merchants.trades_at(wanderer, None))
		self.assertEqual([merchant.name for merchant in Merchants.merchants_at(GUILD_ID, self.town.id)],
		                 ["Greta", "Wanderer"])

	def test_price_has_markup_and_charisma(self) :
		self.assertEqual(Merchants.base_price(self.merchant, self.line, self.sword), 1200)
		self.assertEqual(Merchants.price(self.merchant, self.line, self.sword, self.character), 1200)
		smooth = self.add_character("Smooth", charisma=10)
		self.assertEqual(Merchants.price(self.merchant, self.line, self.sword, smooth), 1020)
		line = MerchantTransactions().set_stock(self.merchant.id, self.sword.id, price=500)
		self.assertEqual(Merchants.base_price(self.merchant, line, self.sword), 600)

	def test_buying_counts_out_of_the_stock(self) :
		for _ in range(2) :
			entry, problem = Merchants.buy(self.merchant, self.line_now(), self.sword, self.character, Access(), USER_ID)
			self.assertIsNone(problem)
		self.assertEqual(entry.price_paid, 1200)
		self.assertEqual(entry.source, "merchant")
		self.assertEqual(CharacterTransactions().get_by_id(self.character.id).currency, 7600)
		self.assertEqual(Merchants.wares(self.merchant), [])
		_, problem = Merchants.buy(self.merchant, self.line_now(), self.sword, self.character, Access(), USER_ID)
		self.assertIn("stock", problem)
		rows = CurrencyTransactions().get_all(self.character.id)
		self.assertEqual(rows[0].note, "Sword from Greta")

	def test_materials_stack(self) :
		line = MerchantTransactions().set_stock(self.merchant.id, self.ingot.id)
		for _ in range(3) :
			Merchants.buy(self.merchant, line, self.ingot, self.character, Access(), USER_ID)
		stacks = [entry for entry in CharacterGearTransactions().get_all(self.character.id) if entry.kind == "material"]
		self.assertEqual([entry.quantity for entry in stacks], [3])

	def test_not_enough_currency(self) :
		poor = self.add_character("Poor", currency=10)
		_, problem = Merchants.buy(self.merchant, self.line, self.sword, poor, Access(), USER_ID)
		self.assertIn("not enough", problem)
		self.assertEqual(self.line_now().in_stock, 2)

	def test_restock_and_rotating_stock(self) :
		MerchantTransactions().set_stock(self.merchant.id, self.sword.id, in_stock=0)
		rare = MerchantTransactions().set_stock(self.merchant.id, self.plate.id, chance=30)
		merchant = Merchants.restock(self.merchant, rng=FixedRng(50))
		self.assertEqual(merchant.cycle, 1)
		self.assertEqual(self.line_now().in_stock, 2)
		self.assertFalse(MerchantTransactions().stock_entry(self.merchant.id, self.plate.id).available)
		Merchants.restock(merchant, rng=FixedRng(10))
		self.assertTrue(MerchantTransactions().stock_entry(self.merchant.id, rare.gear_item_id).available)

	def test_restock_due(self) :
		now = datetime.now(timezone.utc)
		self.assertTrue(Merchants.due(self.merchant, now))
		restocked = Merchants.restock_due(now)
		self.assertEqual([merchant.id for merchant in restocked], [self.merchant.id])
		self.assertFalse(Merchants.due(self.merchant_now(), now + timedelta(days=6)))
		self.assertTrue(Merchants.due(self.merchant_now(), now + timedelta(days=7)))
		manual = MerchantTransactions().add(GUILD_ID, "Hermit", restock=Merchants.MANUAL)
		self.assertFalse(Merchants.due(manual, now))

	def test_selling_to_a_merchant(self) :
		entry = Gear.grant(self.character, self.sword, USER_ID)
		# 30% of 1000, times the merchant's 0.5.
		value, problem = Merchants.sell(self.merchant, entry, USER_ID)
		self.assertEqual((value, problem), (150, None))
		plate = Gear.grant(self.character, self.plate, USER_ID)
		_, problem = Merchants.sell(self.merchant, plate, USER_ID)
		self.assertIn("doesn't buy armor", problem)

	def test_repair_price_has_markup(self) :
		entry = Gear.grant(self.character, self.sword, USER_ID)
		CharacterGearTransactions().update(entry.id, condition=Condition.BROKEN)
		entry = CharacterGearTransactions().get(entry.id)
		self.assertEqual(Merchants.repair_price(self.merchant, entry, self.sword, self.character), 480)


class TestHaggling(MerchantTestCase) :

	def test_success_takes_off_the_price(self) :
		outcome, lines = Merchants.haggle(self.merchant, self.character, self.sword, FixedRng(14))
		self.assertIsNotNone(outcome)
		self.assertEqual(Merchants.discount_for(self.merchant_now(), self.character, self.sword.id), 10)
		self.assertEqual(Merchants.price(self.merchant_now(), self.line, self.sword, self.character), 1080)
		outcome, lines = Merchants.haggle(self.merchant_now(), self.character, self.sword, FixedRng(14))
		self.assertIsNone(outcome)
		self.assertIn("already haggled", lines[0])

	def test_a_bad_failure_offends_until_restock(self) :
		Merchants.haggle(self.merchant, self.character, self.sword, FixedRng(3))
		self.assertTrue(Merchants.refused(self.merchant_now(), self.character))
		_, problem = Merchants.buy(self.merchant_now(), self.line, self.sword, self.character, Access(), USER_ID)
		self.assertIn("won't deal", problem)
		merchant = Merchants.restock(self.merchant_now())
		self.assertFalse(Merchants.refused(merchant, self.character))
		self.assertEqual(Merchants.discount_for(merchant, self.character, self.sword.id), 0)

	def test_merchants_that_dont_haggle(self) :
		stubborn = MerchantTransactions().add(GUILD_ID, "Stubborn")
		outcome, lines = Merchants.haggle(stubborn, self.character, self.sword)
		self.assertIsNone(outcome)
		self.assertIn("doesn't haggle", lines[0])


class TestLodgingAndStash(MerchantTestCase) :

	def test_rent_and_stash(self) :
		entry = Gear.grant(self.character, self.sword, USER_ID)
		self.assertIn("paid room", Merchants.stash(self.character, entry, self.town.id))
		lodging, problem = Merchants.rent(self.merchant, self.character, self.town.id, 2, USER_ID)
		self.assertIsNone(problem)
		self.assertEqual(CharacterTransactions().get_by_id(self.character.id).currency, 9800)
		self.assertGreater(lodging.paid_until, datetime.now(timezone.utc) + timedelta(days=13))
		self.assertIsNone(Merchants.stash(self.character, entry, self.town.id))
		self.assertEqual(CharacterGearTransactions().get(entry.id).status, Merchants.STASHED)
		self.assertEqual(CharacterGearTransactions().get_all(self.character.id), [])
		self.assertEqual([stashed.id for stashed in Merchants.stashed(self.character, self.town.id)], [entry.id])
		self.assertIn("isn't in", Merchants.unstash(self.character, CharacterGearTransactions().get(entry.id),
		                                            self.woods.id))
		self.assertIsNone(Merchants.unstash(self.character, CharacterGearTransactions().get(entry.id), self.town.id))
		self.assertEqual(CharacterGearTransactions().get(entry.id).status, OWNED)

	def test_renting_adds_to_time_paid(self) :
		first, _ = Merchants.rent(self.merchant, self.character, self.town.id, 1, USER_ID)
		second, _ = Merchants.rent(self.merchant, self.character, self.town.id, 1, USER_ID)
		self.assertAlmostEqual((second.paid_until - first.paid_until).days, 7)

	def test_stashed_items_weigh_nothing(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.CARRY_WEIGHT, "kg", overwrite=True)
		plate = Gear.grant(self.character, self.plate, USER_ID)
		Merchants.rent(self.merchant, self.character, self.town.id, 1, USER_ID)
		Merchants.stash(self.character, plate, self.town.id)
		self.assertEqual(Carry.load_of(self.character)[0], 0)

	def test_no_rooms(self) :
		inn = MerchantTransactions().add(GUILD_ID, "Smith", services=[Merchants.REPAIR])
		_, problem = Merchants.rent(inn, self.character, self.town.id, 1, USER_ID)
		self.assertIn("no rooms", problem)


class TestShopModes(MerchantTestCase) :

	def test_global_by_default(self) :
		self.assertEqual(Merchants.shop_mode(GUILD_ID), Merchants.GLOBAL)
		self.assertTrue(Merchants.global_shop_sells(self.plate))
		self.assertIsNone(Merchants.global_shop_problem(GUILD_ID))

	def test_both_keeps_rare_items_for_merchants(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.SHOP_MODE, "both", overwrite=True)
		self.assertTrue(Merchants.global_shop_sells(self.sword))
		self.assertEqual(Rarity.of(self.plate), Rarity.RARE)
		self.assertFalse(Merchants.global_shop_sells(self.plate))
		_, problem = Gear.buy(self.character, self.plate, Access(), USER_ID)
		self.assertIn("sold by merchants", problem)

	def test_merchants_only(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.SHOP_MODE, "merchants", overwrite=True)
		self.assertIsNotNone(Merchants.global_shop_problem(GUILD_ID))
		_, problem = Gear.buy(self.character, self.sword, Access(), USER_ID)
		self.assertIn("sold by merchants", problem)
		# Starting gear still comes from the catalog.
		entry, problem = Gear.buy(self.character, self.sword, Access(), USER_ID, source="creation")
		self.assertIsNone(problem)
