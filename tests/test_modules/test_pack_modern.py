"""The modern genre pack (design/economy.md, packs): original items, no brand or product names, and a full import."""
from classes.combat.BestiaryFlow import BestiaryFlow
from classes.economy import RecipePacks
from classes.gear import Carry, Rarity
from classes.gear.Packs import Packs
from database.transactions.BestiaryTransactions import BestiaryTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from database.transactions.MerchantTransactions import MerchantTransactions
from database.transactions.OccupationTransactions import OccupationTransactions
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID

PACK = "modern"
# Brand and product names the pack must not use.
BRANDS = ["glock", "kevlar", "taser", "epipen", "ak-47", "ar-15", "colt", "remington", "beretta", "uzi", "smith &",
          "winchester", "harley", "advil", "tylenol", "red bull", "leatherman", "maglite"]


class TestModernPack(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()

	def test_the_pack_loads_and_names_no_brands(self) :
		data = Packs.load(PACK)
		self.assertIn((PACK, "Modern"), Packs.available())
		self.assertEqual(data["currency_name"], "dollars")
		self.assertEqual({item["kind"] for item in data["items"]}, {"weapon", "armor", "consumable", "accessory"})
		text = str(data).lower() + str(RecipePacks.load(PACK)).lower()
		for name in BRANDS :
			self.assertNotIn(name, text)

	def test_prices_weights_and_ammunition(self) :
		items = {item["name"] : item for item in Packs.load(PACK)["items"]}
		self.assertEqual({Rarity.from_price(item["price"]) for item in items.values()},
		                 {Rarity.COMMON, Rarity.UNCOMMON, Rarity.RARE})
		self.assertTrue(all(item.get("weight") is not None for item in items.values()))
		self.assertTrue(Carry.uses_ammo(items["Service Pistol"]["combat"]))
		self.assertFalse(Carry.uses_ammo(items["Stun Gun"]["combat"]))

	def test_full_import(self) :
		added, _ = Packs.import_into(GUILD_ID, PACK)
		self.assertEqual(len(added), 38)
		_, _, problems = RecipePacks.import_into(GUILD_ID, PACK)
		self.assertEqual(problems, [])
		self.assertEqual(GearItemTransactions().find(GUILD_ID, "Tactical Knife").salvage,
		                 {"Metal Parts" : 1, "Polymer Stock" : 1})
		entries, _, problems = BestiaryFlow.import_pack(GUILD_ID, PACK, USER_ID)
		self.assertEqual((len(entries), problems), (7, []))
		self.assertEqual(BestiaryTransactions().find(GUILD_ID, "Crime Boss").loot["currency"], "10d10")
		merchants, _, problems = Packs.import_merchants(GUILD_ID, Packs.load(PACK))
		self.assertEqual((len(merchants), problems), (4, []))
		self.assertEqual(MerchantTransactions().find(GUILD_ID, "Roadside Motel").lodging_price, 120)

	def test_kits(self) :
		Packs.import_into(GUILD_ID, PACK)
		officer = OccupationTransactions().add(GUILD_ID, "Police Officer")
		Packs.apply_kits(GUILD_ID, Packs.load(PACK))
		names = [GearItemTransactions().get(item_id).name for item_id in OccupationTransactions().get(officer.id).kit]
		self.assertEqual(names, ["Service Pistol", "Telescopic Baton", "Concealable Vest"])
