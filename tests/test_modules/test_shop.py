import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from classes.characters.Access import Access, EVENT
from classes.gear.Gear import ARMOR, Gear, WEAPON
from classes.kernel.ConfigData import ConfigData
from classes.proxy.Proxy import Proxy
from database.transactions.CharacterGearTransactions import BROKEN, CharacterGearTransactions, LOST
from database.transactions.CurrencyTransactions import BUY, CurrencyTransactions, GM_GIVE, ROLEPLAY, START
from database.transactions.GearItemTransactions import GearItemTransactions
from database.transactions.TagRuleTransactions import TagRuleTransactions
from modules.Currency import balance_text, ledger_line
from modules.Gear import entry_choices, entry_label, find_entry, inventory_lines, unmet_warning
from modules.Shop import balances_text, find_item, pages
from resources.configs.ConfigMapping import ConfigMapping
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID
from test_modules.test_proxy import CHANNEL_ID, FakeChannel, FakeWebhook, fake_message

TAG_EVENT = 702


class ShopTestCase(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()
		ConfigData().add_key(GUILD_ID, ConfigMapping.CURRENCY_NAME, "caps", overwrite=True)
		items = GearItemTransactions()
		self.sword = items.add(GUILD_ID, WEAPON, "Sword", price=100, requirements={"strength" : 4})
		self.plate = items.add(GUILD_ID, ARMOR, "Plate", price=1000, requirements={"strength" : 8})
		self.relic = items.add(GUILD_ID, WEAPON, "Relic", price=5, tag_ids=[TAG_EVENT])
		TagRuleTransactions().set(GUILD_ID, 888, TAG_EVENT, EVENT, None)
		self.character = self.add_character("Ayla", currency=1500)

	def own(self, item) :
		return Gear.grant(self.character, item, USER_ID)


class TestRoleplayLedger(ShopTestCase) :

	def setUp(self) :
		super().setUp()
		self.character = self.add_character("Aria", prefix="Aria:")
		patcher = patch("classes.proxy.Proxy.WebhookManager.get", new=AsyncMock(return_value=FakeWebhook()))
		patcher.start()
		self.addCleanup(patcher.stop)
		self.bot = SimpleNamespace(get_guild=lambda guild_id : None)

	def post(self, content) :
		return asyncio.run(Proxy.handle(self.bot, fake_message(content, FakeChannel())))

	def test_roleplay_currency_is_written_to_the_ledger(self) :
		ConfigData().add_to_list(GUILD_ID, ConfigMapping.XP_CHANNELS, CHANNEL_ID)
		self.assertTrue(self.post("Aria: " + "x" * 400))
		rows = CurrencyTransactions().get_all(self.character.id)
		# 400 / 30 = 13.
		self.assertEqual([(row.amount, row.reason, row.actor_uid) for row in rows], [(13, ROLEPLAY, USER_ID)])

	def test_posts_outside_roleplay_channels_earn_nothing(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.PROXY_OUTSIDE_RP, "TRUE", overwrite=True)
		self.post("Aria: " + "x" * 400)
		self.assertEqual(CurrencyTransactions().get_all(self.character.id), [])


class TestOwnedGearHelpers(ShopTestCase) :

	def test_find_entry_by_id_or_name(self) :
		first, second = self.own(self.sword), self.own(self.sword)
		entries = CharacterGearTransactions().get_all(self.character.id)
		self.assertEqual(find_entry(entries, str(second.id)).id, second.id)
		self.assertEqual(find_entry(entries, "sword").id, first.id)
		self.assertIsNone(find_entry(entries, "Plate"))
		self.assertIsNone(find_entry(entries, ""))

	def test_duplicates_get_numbered_labels(self) :
		first, second = self.own(self.sword), self.own(self.sword)
		plate = self.own(self.plate)
		Gear.equip(plate)
		entries = CharacterGearTransactions().get_all(self.character.id)
		self.assertEqual([entry_label(entry, entries) for entry in entries],
		                 ["Sword #1", "Sword #2", "Plate (equipped)"])
		choices = entry_choices(entries, "sw")
		self.assertEqual([(choice.name, choice.value) for choice in choices],
		                 [("Sword #1", str(first.id)), ("Sword #2", str(second.id))])

	def test_inventory_lines(self) :
		self.own(self.sword)
		plate = self.own(self.plate)
		Gear.equip(plate)
		Gear.set_status(self.own(self.sword), LOST, USER_ID)
		lines = inventory_lines(self.character, Gear.inventory(self.character.id, include_gone=True))
		self.assertEqual(lines, ["**Plate** (armor) · worn · misses Strength 8", "**Sword** (weapon) · No proficiency set",
		                         "~~Sword~~ (weapon) · lost"])
		self.assertEqual(len(inventory_lines(self.character, Gear.inventory(self.character.id))), 2)

	def test_gear_from_a_removed_catalog_item_still_shows(self) :
		entry = self.own(self.plate)
		GearItemTransactions().delete(self.plate.id)
		Gear.set_status(entry, BROKEN, USER_ID)
		lines = inventory_lines(self.character, Gear.inventory(self.character.id, include_gone=True))
		self.assertEqual(lines, ["~~Plate~~ (armor) · broken"])

	def test_unmet_warning(self) :
		self.assertIn("Strength 8", unmet_warning(self.character, self.plate))
		self.assertEqual(unmet_warning(self.character, self.sword), "")
		self.assertEqual(unmet_warning(self.character, None), "")


class TestShopHelpers(ShopTestCase) :

	def test_pages_never_split_a_line(self) :
		self.assertEqual(pages([]), [])
		self.assertEqual(pages(["a", "b"]), ["a\nb"])
		result = pages(["x" * 6, "y" * 6, "z" * 3], limit=10)
		self.assertEqual(result, ["x" * 6, "y" * 6 + "\n" + "z" * 3])
		self.assertTrue(all(len(page) <= 10 for page in pages(["w" * 25, "v"], limit=10)))

	def test_find_item_only_sees_the_visible_catalog(self) :
		items = Gear.shop_items(GUILD_ID, Access())
		self.assertEqual(find_item(items, "sword").item.id, self.sword.id)
		self.assertIsNone(find_item(items, "Relic"))
		self.assertIsNotNone(find_item(Gear.shop_items(GUILD_ID, Access(staff=True)), "relic"))

	def test_balances(self) :
		bryn = self.add_character("Bryn", currency=300)
		self.assertEqual(balance_text(GUILD_ID, 5), "5 caps")
		self.assertEqual(balances_text(GUILD_ID, [self.character, bryn]), "Ayla: 1500 caps · Bryn: 300 caps")
		self.assertEqual(balances_text(GUILD_ID, []), "")
		ConfigData().add_key(GUILD_ID, ConfigMapping.ECONOMY, "free", overwrite=True)
		self.assertEqual(balances_text(GUILD_ID, [self.character]), "")


class TestLedgerLines(ShopTestCase) :

	def test_lines(self) :
		ledger = CurrencyTransactions()
		ledger.log(self.character.id, GUILD_ID, 3000, START)
		ledger.log(self.character.id, GUILD_ID, -100, BUY, USER_ID, "Sword")
		ledger.log(self.character.id, GUILD_ID, 50, GM_GIVE, 42, "event prize")
		lines = [ledger_line(row, "caps") for row in ledger.get_all(self.character.id)]
		self.assertTrue(lines[0].startswith("`+50` caps · given by <@42>: event prize · <t:"))
		self.assertTrue(lines[1].startswith("`-100` caps · bought Sword"))
		self.assertTrue(lines[2].startswith("`+3000` caps · starting amount"))
