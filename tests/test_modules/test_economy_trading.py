"""Phase 3 of design/economy.md: trades, payments and the market."""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from classes.economy import MarketFlow as Market, Trading
from classes.economy.MarketFlow import MarketFlow
from classes.gear.Gear import ARMOR, CURSED, Gear, WEAPON
from classes.kernel.ConfigData import ConfigData
from database.transactions.CharacterGearTransactions import CharacterGearTransactions, OWNED
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.CurrencyTransactions import CurrencyTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from database.transactions.TradeTransactions import Move, Payment, TradeTransactions, Transfer
from modules.Currency import ledger_line
from resources.configs.ConfigMapping import ConfigMapping
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID

OTHER_ID = 288647277181665280


class TradingTestCase(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()
		items = GearItemTransactions()
		self.sword = items.add(GUILD_ID, WEAPON, "Sword", price=200, weight=2)
		self.plate = items.add(GUILD_ID, ARMOR, "Plate", price=2000, weight=20)
		self.ayla = self.add_character("Ayla", currency=1000)
		self.bryn = self.add_character("Bryn", user_id=OTHER_ID, currency=500)
		self.alt = self.add_character("Alt", currency=0)

	def trade(self, left=None, right=None) :
		return TradeTransactions().add_trade(GUILD_ID, left or self.ayla, right or self.bryn)

	def entry(self, entry) :
		return CharacterGearTransactions().get(entry.id)

	def character(self, character) :
		return CharacterTransactions().get_by_id(character.id)


class TestTradeRules(TradingTestCase) :

	def test_own_characters_cannot_trade(self) :
		self.assertIn("own characters", Trading.pair_problem(self.ayla, self.alt))
		self.assertIsNone(Trading.pair_problem(self.ayla, self.bryn))
		pending = self.add_character("Pending", user_id=OTHER_ID, state="pending")
		self.assertIn("approved", Trading.pair_problem(self.ayla, pending))

	def test_equipped_items_have_to_be_put_away(self) :
		sword = Gear.grant(self.ayla, self.sword, USER_ID)
		self.assertIsNone(Trading.tradable(sword))
		Gear.equip(sword)
		self.assertIn("equipped", Trading.tradable(self.entry(sword)))

	def test_offers_and_checks(self) :
		trade = self.trade()
		self.assertIn("Nothing", Trading.check(trade))
		sword = Gear.grant(self.ayla, self.sword, USER_ID)
		trade = TradeTransactions().update_trade(trade.id, offers=Trading.with_offer(trade, Trading.LEFT, [sword.id]))
		trade = TradeTransactions().update_trade(trade.id,
		                                         offers=Trading.with_offer(trade, Trading.RIGHT, currency=300))
		self.assertEqual(Trading.offer(trade, Trading.LEFT), {"items" : [sword.id], "currency" : 0})
		self.assertEqual(Trading.offer(trade, Trading.RIGHT), {"items" : [], "currency" : 300})
		self.assertIsNone(Trading.check(trade))
		ConfigData().add_key(GUILD_ID, ConfigMapping.TRADING, "DISABLED", overwrite=True)
		self.assertIn("off", Trading.check(trade))

	def test_carry_weight_is_checked_for_the_receiver(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.CARRY_WEIGHT, "kg", overwrite=True)
		plates = [Gear.grant(self.ayla, self.plate, USER_ID) for _ in range(6)]
		trade = self.trade()
		trade = TradeTransactions().update_trade(
			trade.id, offers=Trading.with_offer(trade, Trading.LEFT, [plate.id for plate in plates]))
		self.assertIn("couldn't carry", Trading.check(trade))

	def test_item_line_tells_what_a_trader_should_know(self) :
		sword = Gear.grant(self.ayla, self.sword, USER_ID)
		CharacterGearTransactions().update(sword.id, quality=CURSED, condition="worn")
		self.assertEqual(Trading.item_line(self.entry(sword)), "Sword (cursed, worn)")


class TestTransfers(TradingTestCase) :

	def test_a_trade_swaps_everything_at_once(self) :
		sword = Gear.grant(self.ayla, self.sword, USER_ID)
		CharacterGearTransactions().update(sword.id, proficiency="good")
		trade = self.trade()
		trade = TradeTransactions().update_trade(trade.id, offers={"left" : {"items" : [sword.id], "currency" : 100},
		                                                           "right" : {"items" : [], "currency" : 250}})
		self.assertIsNone(TradeTransactions().transfer(Trading.build_transfer(trade, USER_ID), GUILD_ID))
		moved = self.entry(sword)
		self.assertEqual((moved.character_id, moved.proficiency, moved.source), (self.bryn.id, None, "traded"))
		self.assertEqual((self.character(self.ayla).currency, self.character(self.bryn).currency), (1150, 350))
		reasons = sorted((row.amount, row.reason) for row in CurrencyTransactions().get_all(self.ayla.id))
		self.assertEqual(reasons, [(-100, Trading.TRADE_OUT), (250, Trading.TRADE_IN)])
		self.assertIn("trade: Trade with Bryn", ledger_line(CurrencyTransactions().get_all(self.ayla.id)[0], "caps"))

	def test_nothing_happens_when_part_fails(self) :
		sword = Gear.grant(self.ayla, self.sword, USER_ID)
		transfer = Transfer(moves=[Move(sword.id, self.ayla.id, self.bryn.id)],
		                    payments=[Payment(self.bryn.id, -9999, Trading.TRADE_OUT),
		                              Payment(self.ayla.id, 9999, Trading.TRADE_IN)])
		self.assertIn("enough", TradeTransactions().transfer(transfer, GUILD_ID))
		self.assertEqual(self.entry(sword).character_id, self.ayla.id)
		self.assertEqual(self.character(self.ayla).currency, 1000)
		self.assertEqual(CurrencyTransactions().get_all(self.ayla.id), [])

	def test_an_item_that_moved_away_stops_the_trade(self) :
		sword = Gear.grant(self.ayla, self.sword, USER_ID)
		Gear.equip(sword)
		transfer = Transfer(moves=[Move(sword.id, self.ayla.id, self.bryn.id)])
		self.assertIn("equipped", TradeTransactions().transfer(transfer, GUILD_ID))
		transfer = Transfer(moves=[Move(sword.id, self.bryn.id, self.ayla.id)])
		self.assertIn("no longer", TradeTransactions().transfer(transfer, GUILD_ID))

	def test_pay(self) :
		self.assertIsNone(Trading.pay(self.ayla, self.bryn, 300, USER_ID, "for the map"))
		self.assertEqual((self.character(self.ayla).currency, self.character(self.bryn).currency), (700, 800))
		self.assertIn("payment: Paid Bryn: for the map",
		              ledger_line(CurrencyTransactions().get_all(self.ayla.id)[0], "caps"))
		self.assertIn("own characters", Trading.pay(self.ayla, self.alt, 10, USER_ID))
		self.assertIn("enough", Trading.pay(self.bryn, self.ayla, 5000, OTHER_ID))
		ConfigData().add_key(GUILD_ID, ConfigMapping.ECONOMY, "free", overwrite=True)
		self.assertIn("free mode", Trading.pay(self.ayla, self.bryn, 10, USER_ID))


class TestMarket(TradingTestCase) :

	def list_sword(self, price=400) :
		sword = Gear.grant(self.ayla, self.sword, USER_ID)
		listing = TradeTransactions().add_listing(GUILD_ID, sword, self.ayla, price,
		                                          datetime.now(timezone.utc) + timedelta(days=14))
		return sword, listing

	def test_listing_takes_the_item_out_of_the_inventory(self) :
		sword, listing = self.list_sword()
		self.assertEqual(self.entry(sword).status, "listed")
		self.assertEqual(CharacterGearTransactions().get_all(self.ayla.id), [])
		# It can't be listed twice.
		self.assertIsNone(TradeTransactions().add_listing(GUILD_ID, self.entry(sword), self.ayla, 10, None))

	def test_buying_pays_the_seller_minus_the_fee(self) :
		sword, listing = self.list_sword(400)
		self.assertIsNone(Market.buy_problem(listing, self.bryn))
		transfer, fee = Market.purchase(listing, self.bryn, OTHER_ID)
		self.assertEqual(fee, 20)
		self.assertIsNone(TradeTransactions().buy_listing(listing.id, transfer, self.bryn, fee))
		self.assertEqual((self.character(self.ayla).currency, self.character(self.bryn).currency), (1380, 100))
		moved = self.entry(sword)
		self.assertEqual((moved.character_id, moved.status, moved.source), (self.bryn.id, OWNED, "market"))
		sold = TradeTransactions().listing(listing.id)
		self.assertEqual((sold.state, sold.buyer_character_id, sold.fee), ("sold", self.bryn.id, 20))
		# A second buyer is refused and nothing changes.
		self.assertIn("isn't open", TradeTransactions().buy_listing(listing.id, transfer, self.bryn, fee))
		self.assertEqual(self.character(self.bryn).currency, 100)

	def test_buy_problems(self) :
		_, listing = self.list_sword(400)
		self.assertIn("own listing", Market.buy_problem(listing, self.alt))
		poor = self.add_character("Poor", user_id=OTHER_ID, currency=10)
		self.assertIn("not enough", Market.buy_problem(listing, poor))
		ConfigData().add_key(GUILD_ID, ConfigMapping.ECONOMY, "free", overwrite=True)
		self.assertIn("free mode", Market.problem_for(GUILD_ID))

	def test_withdrawn_and_expired_listings_return_the_item(self) :
		sword, listing = self.list_sword()
		self.assertIsNotNone(TradeTransactions().close_listing(listing.id, Market.WITHDRAWN))
		self.assertEqual(self.entry(sword).status, OWNED)
		self.assertIsNone(TradeTransactions().close_listing(listing.id, Market.WITHDRAWN))
		other, old = self.list_sword()
		TradeTransactions().update_listing(old.id, expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))
		client = SimpleNamespace()
		with patch.object(MarketFlow, "refresh", new=AsyncMock()), \
				patch.object(MarketFlow, "tell_seller", new=AsyncMock()) as told :
			asyncio.run(MarketFlow.tick(client))
		self.assertEqual(TradeTransactions().listing(old.id).state, Market.EXPIRED)
		self.assertEqual(self.entry(other).status, OWNED)
		told.assert_awaited_once()

	def test_fee_setting(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.MARKET_FEE, 10, overwrite=True)
		self.assertEqual(Market.fee_for(GUILD_ID, 999), 99)
