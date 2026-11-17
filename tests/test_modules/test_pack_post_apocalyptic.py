"""The post-apocalyptic genre pack (design/economy.md, packs): gear, recipes, bestiary with loot, merchants and
starter kits, and the pack format's new parts."""
from classes.combat.BestiaryFlow import BestiaryFlow
from classes.economy import RecipePacks
from classes.gear import Carry, Rarity
from classes.gear.Packs import Packs
from database.transactions.BestiaryTransactions import BestiaryTransactions
from database.transactions.EconomyTransactions import EconomyTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from database.transactions.MerchantTransactions import MerchantTransactions
from database.transactions.OccupationTransactions import OccupationTransactions
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID

PACK = "post_apocalyptic"
# Names the pack must not use (they belong to existing games).
BORROWED = ["stimpak", "radaway", "nuka", "pip-boy", "pipboy", "vault", "power armor", "deathclaw", "ghoul",
            "brahmin", "super mutant", "bottle cap"]


class TestPostApocalypticPack(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()

	def test_the_pack_loads_and_is_original(self) :
		data = Packs.load(PACK)
		self.assertIn((PACK, "Post-apocalyptic"), Packs.available())
		self.assertEqual(data["currency_name"], "scrip")
		kinds = {item["kind"] for item in data["items"]}
		self.assertEqual(kinds, {"weapon", "armor", "consumable", "accessory"})
		text = str(data).lower() + str(RecipePacks.load(PACK)).lower()
		for name in BORROWED :
			self.assertNotIn(name, text)

	def test_prices_follow_the_rarity_ladder(self) :
		rarities = {Rarity.from_price(item["price"]) for item in Packs.load(PACK)["items"]}
		self.assertEqual(rarities, {Rarity.COMMON, Rarity.UNCOMMON, Rarity.RARE})

	def test_every_item_has_a_weight(self) :
		self.assertTrue(all(item.get("weight") is not None for item in Packs.load(PACK)["items"]))

	def test_guns_use_ammunition(self) :
		items = {item["name"] : item for item in Packs.load(PACK)["items"]}
		self.assertTrue(Carry.uses_ammo(items["Lever Rifle"]["combat"]))
		self.assertFalse(Carry.uses_ammo(items["Machete"]["combat"]))

	def test_full_import(self) :
		added, _ = Packs.import_into(GUILD_ID, PACK)
		self.assertEqual(len(added), 40)
		recipes_added, _, problems = RecipePacks.import_into(GUILD_ID, PACK)
		self.assertEqual(problems, [])
		# 11 materials and 12 recipes.
		self.assertEqual(len(recipes_added), 23)
		self.assertIsNotNone(EconomyTransactions().find_recipe(GUILD_ID, "Pipe Pistol"))
		self.assertEqual(GearItemTransactions().find(GUILD_ID, "Pipe Pistol").salvage, {"Scrap Metal" : 2, "Spring" : 1})
		entries, _, problems = BestiaryFlow.import_pack(GUILD_ID, PACK, USER_ID)
		self.assertEqual((len(entries), problems), (7, []))
		raider = BestiaryTransactions().find(GUILD_ID, "Wasteland Raider")
		self.assertEqual([drop["name"] for drop in raider.loot["items"]], ["Pipe Pistol", "Med-Injector", "Scrap Metal"])
		data = Packs.load(PACK)
		merchants, skipped, problems = Packs.import_merchants(GUILD_ID, data)
		self.assertEqual((len(merchants), skipped, problems), (3, [], []))
		clinic = MerchantTransactions().find(GUILD_ID, "Halloway's Clinic")
		self.assertEqual(clinic.services, ["healing"])
		self.assertEqual(len(MerchantTransactions().stock(clinic.id)), 8)
		self.assertEqual(Packs.import_merchants(GUILD_ID, data)[1], [m["name"] for m in data["merchants"]])

	def test_kits_go_to_occupations_with_the_same_name(self) :
		Packs.import_into(GUILD_ID, PACK)
		medic = OccupationTransactions().add(GUILD_ID, "medic")
		own_kit = OccupationTransactions().add(GUILD_ID, "Guard", kit=[1])
		lines = Packs.apply_kits(GUILD_ID, Packs.load(PACK))
		self.assertEqual(len(lines), 1)
		kit = OccupationTransactions().get(medic.id).kit
		self.assertEqual([GearItemTransactions().get(item_id).name for item_id in kit],
		                 ["Pipe Pistol", "Patched Duster", "Med-Injector", "Field Dressing"])
		self.assertEqual(OccupationTransactions().get(own_kit.id).kit, [1])

	def test_merchant_stock_waits_for_the_catalog(self) :
		_, _, problems = Packs.import_merchants(GUILD_ID, Packs.load(PACK))
		self.assertTrue(problems)
		self.assertIn("not in the catalog yet", problems[0])
