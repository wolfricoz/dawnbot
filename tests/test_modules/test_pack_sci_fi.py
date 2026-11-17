"""The sci-fi genre pack (design/economy.md, packs): original items, no names from existing franchises, and a full
import."""
from classes.combat.BestiaryFlow import BestiaryFlow
from classes.economy import RecipePacks
from classes.gear import Carry, Rarity
from classes.gear.Packs import Packs
from database.transactions.GearItemTransactions import GearItemTransactions
from database.transactions.MerchantTransactions import MerchantTransactions
from database.transactions.OccupationTransactions import OccupationTransactions
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID

PACK = "sci_fi"
# Names that belong to existing franchises.
BORROWED = ["lightsaber", "blaster", "phaser", "tricorder", "jedi", "wookiee", "droid", "stormtrooper", "klingon",
            "borg", "xenomorph", "pulse rifle", "plasma cutter", "needler", "spartan", "bolter", "lasgun",
            "chainsword", "stimpack", "medi-gel", "omni-tool", "reflec", "warp drive", "tardis", "sonic screwdriver"]


class TestSciFiPack(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()

	def test_the_pack_loads_and_is_original(self) :
		data = Packs.load(PACK)
		self.assertIn((PACK, "Sci-fi"), Packs.available())
		self.assertEqual(data["currency_name"], "credits")
		self.assertEqual({item["kind"] for item in data["items"]}, {"weapon", "armor", "consumable", "accessory"})
		text = str(data).lower() + str(RecipePacks.load(PACK)).lower()
		for name in BORROWED :
			self.assertNotIn(name, text)

	def test_prices_weights_and_ammunition(self) :
		items = {item["name"] : item for item in Packs.load(PACK)["items"]}
		self.assertEqual({Rarity.from_price(item["price"]) for item in items.values()},
		                 {Rarity.COMMON, Rarity.UNCOMMON, Rarity.RARE})
		self.assertTrue(all(item.get("weight") is not None for item in items.values()))
		self.assertTrue(Carry.uses_ammo(items["Coil Carbine"]["combat"]))
		# A thrown spike doesn't use ammunition.
		self.assertFalse(Carry.uses_ammo(items["Gravity Spike"]["combat"]))

	def test_full_import(self) :
		added, _ = Packs.import_into(GUILD_ID, PACK)
		self.assertEqual(len(added), 41)
		_, _, problems = RecipePacks.import_into(GUILD_ID, PACK)
		self.assertEqual(problems, [])
		self.assertEqual(GearItemTransactions().find(GUILD_ID, "Beam Pistol").salvage,
		                 {"Microchip" : 1, "Power Cell" : 1})
		entries, _, problems = BestiaryFlow.import_pack(GUILD_ID, PACK, USER_ID)
		self.assertEqual((len(entries), problems), (7, []))
		merchants, _, problems = Packs.import_merchants(GUILD_ID, Packs.load(PACK))
		self.assertEqual((len(merchants), problems), (4, []))
		dealer = MerchantTransactions().find(GUILD_ID, "Licensed Arms Dealer")
		self.assertEqual(dealer.services, ["training", "identify"])

	def test_kits(self) :
		Packs.import_into(GUILD_ID, PACK)
		pilot = OccupationTransactions().add(GUILD_ID, "Pilot")
		Packs.apply_kits(GUILD_ID, Packs.load(PACK))
		names = [GearItemTransactions().get(item_id).name for item_id in OccupationTransactions().get(pilot.id).kit]
		self.assertEqual(names, ["Flight Suit", "Flechette Pistol", "Comm Pendant"])
