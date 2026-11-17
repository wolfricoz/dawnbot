"""Phase 5 of design/economy.md: magic items, attunement, identification, enchanting designs and loot."""
from types import SimpleNamespace

from classes.combat import EffectCatalog, Effects, PassiveCatalog
from classes.combat.Loadout import Loadout
from classes.combat.Resolver import Resolver
from classes.economy import Crafting, Enchanting, Loot, Merchants
from classes.gear import Magic, Rarity
from classes.gear.Gear import ACCESSORY, ARMOR, CURSED, Gear, WEAPON
from classes.gear.Packs import Packs
from classes.kernel.ConfigData import ConfigData
from database.transactions.AbilityTransactions import AbilityTransactions
from database.transactions.BestiaryTransactions import BestiaryTransactions
from database.transactions.CharacterGearTransactions import CharacterGearTransactions
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.EconomyTransactions import EconomyTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from database.transactions.MerchantTransactions import MerchantTransactions
from resources.configs.ConfigMapping import ConfigMapping
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID

OTHER_ID = 288647277181665280


def active_effect(tier: str) :
	"""A magic effect of exactly this tier, an attack or blast when there is one."""
	pool = [effect for effect in EffectCatalog.ACTIVE_EFFECTS if effect.tier == tier and effect.realm == Effects.MAGIC]
	return next((effect for effect in pool if effect.mechanic in (Effects.ATTACK, Effects.BLAST)), pool[0])


def passive_effect(tier: str) :
	return next(effect for effect in PassiveCatalog.PASSIVE_EFFECTS if effect.tier == tier)


class FixedRng :

	def __init__(self, *numbers) :
		self.numbers = list(numbers)

	def randint(self, low, high) :
		value = self.numbers.pop(0) if len(self.numbers) > 1 else self.numbers[0]
		return max(low, min(high, value))


class MagicTestCase(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()
		items = GearItemTransactions()
		self.weak = active_effect(Effects.WEAK)
		self.normal = active_effect(Effects.NORMAL)
		self.wand = items.add(GUILD_ID, WEAPON, "Wand", price=1200, rarity=Rarity.UNCOMMON,
		                      combat=Packs.combat_for(WEAPON, None, {"dice" : "1d4", "range" : "ranged"}),
		                      enchantments={"activation" : "active", "effects" : [{"key" : self.weak.key}],
		                                    "charges" : 2, "recharge" : "day", "bonus" : True})
		self.amulet = items.add(GUILD_ID, ACCESSORY, "Amulet", price=2000, slot="neck", rarity=Rarity.RARE,
		                        enchantments={"activation" : "passive",
		                                      "effects" : [{"key" : passive_effect(Effects.WEAK).key}]})
		self.mail = items.add(GUILD_ID, ARMOR, "Mail", price=1300, rarity=Rarity.UNCOMMON,
		                      combat=Packs.combat_for(ARMOR, None, {"armor_class" : "medium", "ac" : 2, "dt" : 2}),
		                      enchantments={"bonus" : True})
		self.plain = items.add(GUILD_ID, WEAPON, "Club", price=50, combat=Packs.combat_for(WEAPON, None, {"dice" : "1d6"}))
		self.character = self.add_character(currency=10000)

	def entry(self, entry) :
		return CharacterGearTransactions().get(entry.id)


class TestEnchantments(MagicTestCase) :

	def test_budgets(self) :
		weak = {"activation" : "active", "effects" : [{"key" : self.weak.key}]}
		normal = {"activation" : "active", "effects" : [{"key" : self.normal.key}]}
		two_weak = {"activation" : "active", "effects" : [{"key" : self.weak.key}, {"key" : self.weak.key}]}
		self.assertIsNone(Magic.check(Rarity.UNCOMMON, weak))
		self.assertIn("Uncommon", Magic.check(Rarity.UNCOMMON, normal))
		self.assertIsNone(Magic.check(Rarity.RARE, normal))
		self.assertIsNone(Magic.check(Rarity.RARE, two_weak))
		self.assertIn("Common items", Magic.check(Rarity.COMMON, weak))
		self.assertIn("Unknown", Magic.check(Rarity.RARE, {"activation" : "active", "effects" : [{"key" : "nope"}]}))
		# The catalogs top out at Normal effects, so Very rare allows two of them.
		two_normal = {"activation" : "active", "effects" : [{"key" : self.normal.key}, {"key" : self.normal.key}]}
		self.assertIn("Rare item", Magic.check(Rarity.RARE, two_normal))
		self.assertIsNone(Magic.check(Rarity.VERY_RARE, two_normal))

	def test_build_finds_effects_by_name(self) :
		data, problem = Magic.build("active", [self.weak.name], charges=3, recharge="day", bonus=True)
		self.assertIsNone(problem)
		self.assertEqual((data["effects"], data["charges"], data["recharge"], data["bonus"]),
		                 ([{"key" : self.weak.key}], 3, "day", True))
		self.assertIn("no passive effect", Magic.build("passive", ["Nothing Like It"])[1])

	def test_describe(self) :
		self.assertIn(f"Active (2 charges a day): {self.weak.name}", Magic.describe(self.wand))
		self.assertIn("+1 to hit", Magic.describe(self.wand))
		self.assertEqual(Magic.describe(self.mail), "+1 DT")
		self.assertEqual(Magic.describe(self.plain), "")


class TestAttunement(MagicTestCase) :

	def test_only_attuned_items_work(self) :
		wand = Gear.grant(self.character, self.wand, USER_ID)
		self.assertFalse(Magic.working(wand, self.wand))
		stats = Loadout.character_stats(self.character)
		self.assertEqual([ability["name"] for ability in stats["abilities"]], [])
		self.assertIsNone(Magic.attune_problem(self.character, wand, self.wand))
		Magic.attune(wand)
		stats = Loadout.character_stats(self.character)
		ability = next(ability for ability in stats["abilities"] if ability["name"] == "Wand")
		self.assertEqual((ability["fixed_bonus"], ability["uses"], ability["id"]), (3, 2, f"item:{wand.id}"))
		weapon = next(weapon for weapon in stats["weapons"] if weapon["name"] == "Wand")
		self.assertEqual(weapon["hit_mod"], 1)

	def test_armor_and_accessories_must_be_worn(self) :
		mail, amulet = Gear.grant(self.character, self.mail, USER_ID), Gear.grant(self.character, self.amulet, USER_ID)
		Magic.attune(mail)
		Magic.attune(amulet)
		self.assertFalse(Magic.working(self.entry(mail), self.mail))
		Gear.equip(self.entry(mail))
		Gear.equip(self.entry(amulet))
		stats = Loadout.character_stats(self.character)
		self.assertEqual(stats["armor"]["dt"], 3)
		item_passives = [passive for passive in stats["passives"] if str(passive["id"]).startswith("item:")]
		self.assertTrue(item_passives)
		self.assertEqual(sum(int(passive.get("ap_cost") or 0) for passive in item_passives), 0)

	def test_attunement_limit(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.ATTUNEMENT_SLOTS, 1, overwrite=True)
		first, second = Gear.grant(self.character, self.wand, USER_ID), Gear.grant(self.character, self.wand, USER_ID)
		Magic.attune(first)
		self.assertIn("most it can be", Magic.attune_problem(self.character, second, self.wand))
		CharacterTransactions().update(self.character.id, legendary=True)
		legend = CharacterTransactions().get_by_id(self.character.id)
		self.assertIsNone(Magic.attune_problem(legend, second, self.wand))
		self.assertIn("isn't a magic item", Magic.attune_problem(legend, Gear.grant(legend, self.plain, USER_ID),
		                                                         self.plain))

	def test_cursed_items_hold_on(self) :
		wand = Gear.grant(self.character, self.wand, USER_ID)
		Magic.attune(wand)
		CharacterGearTransactions().update(wand.id, quality=CURSED)
		self.assertIsNone(Magic.unattune(self.entry(wand)))

	def test_daily_charges(self) :
		wand = Gear.grant(self.character, self.wand, USER_ID)
		self.assertEqual(Magic.charges(wand, self.wand, "2026-11-17"), 2)
		Magic.spend_charges(wand.id, 1, "2026-11-17")
		self.assertEqual(Magic.charges(self.entry(wand), self.wand, "2026-11-17"), 1)
		# A new day brings them back.
		self.assertEqual(Magic.charges(self.entry(wand), self.wand, "2026-11-18"), 2)

	def test_item_effects_roll_with_the_item_bonus(self) :
		resolver = SimpleNamespace(mod=lambda actor, stat : 99)
		self.assertEqual(Resolver.ability_mod(resolver, None, {"fixed_bonus" : 4, "stat" : "intelligence"}), 4)
		self.assertEqual(Resolver.ability_mod(resolver, None, {"stat" : "intelligence"}), 99)

	def test_unidentified_items_do_nothing(self) :
		wand = Gear.grant(self.character, self.wand, USER_ID)
		CharacterGearTransactions().update(wand.id, identified=False, attuned=True)
		self.assertFalse(Magic.working(self.entry(wand), self.wand))
		GearItemTransactions().update(self.wand.id, unidentified_name="a humming stick")
		wand_item = GearItemTransactions().get(self.wand.id)
		self.assertEqual(Magic.shown_name(self.entry(wand), wand_item), "a humming stick")
		self.assertEqual(Magic.identify_dc(wand_item), 12)
		Magic.identify(self.entry(wand))
		self.assertTrue(Magic.working(self.entry(wand), wand_item))


class TestDesigns(MagicTestCase) :

	def design(self, rarity=Rarity.UNCOMMON) :
		data, _ = Magic.build("active", [self.weak.key], charges=1, recharge="fight")
		return Enchanting.DesignTransactions().add(guild_id=GUILD_ID, creator_uid=USER_ID, character_id=self.character.id,
		                                           base_item_id=self.plain.id, name="Ember Club", rarity=rarity,
		                                           enchantments=data)

	def test_design_problems(self) :
		data, _ = Magic.build("active", [self.normal.key])
		self.assertIn("Uncommon", Enchanting.design_problem(GUILD_ID, "New", self.plain, Rarity.UNCOMMON, data))
		self.assertIn("already a magic item", Enchanting.design_problem(GUILD_ID, "New", self.wand, Rarity.RARE, data))
		self.assertIn("already has", Enchanting.design_problem(GUILD_ID, "Wand", self.plain, Rarity.RARE, data))
		self.assertIn("Legendary", Enchanting.design_problem(GUILD_ID, "New", self.plain, Rarity.LEGENDARY, data))

	def test_approval_makes_a_crafted_only_item_and_a_recipe(self) :
		item, problem = Enchanting.approve(self.design(), USER_ID)
		self.assertIsNone(problem)
		self.assertTrue(item.crafted_only)
		self.assertEqual((item.kind, item.rarity, item.price), (WEAPON, Rarity.UNCOMMON, 1300))
		self.assertIn("only made by crafting", Gear.lock_reason(item, SimpleNamespace(
			for_character=lambda character_id : None, staff=False, check=lambda requirements : None)))
		recipe = EconomyTransactions().find_recipe(GUILD_ID, "Ember Club")
		self.assertEqual((recipe.result_item_id, recipe.dc, recipe.enchanting), (item.id, 12, True))
		self.assertEqual(recipe.ingredients, [{"item_id" : self.plain.id, "amount" : 1}])

	def test_only_spellcasters_enchant(self) :
		item, _ = Enchanting.approve(self.design(), USER_ID)
		recipe = EconomyTransactions().find_recipe(GUILD_ID, "Ember Club")
		self.assertIn("spellcaster", Crafting.lock_reason(self.character, recipe))
		spell = AbilityTransactions().add(GUILD_ID, "Spark", kind="spell", tier="cantrip", stat="intelligence",
		                                  effects=[{"key" : self.weak.key}], state="approved", creator_uid=USER_ID)
		AbilityTransactions().learn(self.character.id, spell.id)
		self.assertIsNone(Crafting.lock_reason(self.character, recipe))

	def test_a_crit_adds_a_charge(self) :
		item, _ = Enchanting.approve(self.design(), USER_ID)
		recipe = EconomyTransactions().find_recipe(GUILD_ID, "Ember Club")
		Gear.grant(self.character, self.plain, USER_ID)
		outcome, _, lines = Crafting.make(self.character, recipe, USER_ID, FixedRng(20))
		self.assertEqual(outcome, Crafting.CRIT)
		made = next(entry for entry in CharacterGearTransactions().get_all(self.character.id)
		            if entry.gear_item_id == item.id)
		self.assertEqual((made.quality, made.extra_charges), ("masterwork", 1))
		self.assertEqual(Magic.charges(made, item), 2)


class TestLoot(MagicTestCase) :

	def setUp(self) :
		super().setUp()
		self.bandit = BestiaryTransactions().add(GUILD_ID, "Bandit", preset="standard",
		                                         loot={"currency" : "10", "items" : [{"name" : "Club", "chance" : 100,
		                                                                              "amount" : 1},
		                                                                             {"name" : "Wand", "chance" : 50,
		                                                                              "amount" : 1}]})
		self.bryn = self.add_character("Bryn", user_id=OTHER_ID)

	def fight(self) :
		npc = SimpleNamespace(side_id=2, bestiary_id=self.bandit.id, character_id=None, state="downed", uid=None)
		ayla = SimpleNamespace(side_id=1, bestiary_id=None, character_id=self.character.id, state="active", uid=USER_ID)
		bryn = SimpleNamespace(side_id=1, bestiary_id=None, character_id=self.bryn.id, state="active", uid=OTHER_ID)
		return SimpleNamespace(id=7, guild_id=GUILD_ID, winner_side_id=1, combatants=[npc, ayla, bryn],
		                       title="Ambush")

	def test_parse_and_describe(self) :
		parsed, problem = Loot.parse(GUILD_ID, "Club 50%, Wand x2, Amulet 10% x3")
		self.assertIsNone(problem)
		self.assertEqual(parsed, [{"name" : "Club", "chance" : 50, "amount" : 1},
		                          {"name" : "Wand", "chance" : 100, "amount" : 2},
		                          {"name" : "Amulet", "chance" : 10, "amount" : 3}])
		self.assertIn("no item", Loot.parse(GUILD_ID, "Dragon 5%")[1])
		self.assertEqual(Loot.describe({"currency" : "3d10", "items" : parsed[:1]}), "3d10 currency, Club 50%")

	def test_roll(self) :
		currency, items = Loot.roll(self.fight(), FixedRng(30, 80))
		self.assertEqual(currency, 10)
		self.assertEqual([entry["name"] for entry in items], ["Club"])

	def test_settle_in_gm_mode(self) :
		loot = Loot.LootTransactions().add(guild_id=GUILD_ID, fight_id=7, currency=11, mode=Loot.GM,
		                                   items=[{"item_id" : self.plain.id, "name" : "Club", "amount" : 1,
		                                           "claims" : [], "winner" : None},
		                                          {"item_id" : self.wand.id, "name" : "Wand", "amount" : 1,
		                                           "claims" : [], "winner" : None}])
		loot = Loot.claim(loot, 0, self.character.id)
		loot = Loot.claim(loot, 0, self.bryn.id)
		lines = Loot.settle(loot, self.fight(), picks={0 : self.bryn.id}, actor_uid=USER_ID)
		self.assertIn("→ **Bryn**", lines[0])
		self.assertIn("left behind", lines[1])
		self.assertIn("5 each", lines[2])
		self.assertEqual(CharacterTransactions().get_by_id(self.character.id).currency, 10005)
		self.assertEqual(Loot.LootTransactions().get(loot.id).state, Loot.SETTLED)

	def test_claim_mode_rolls_off_and_identify(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.IDENTIFY, "ENABLED", overwrite=True)
		loot = Loot.LootTransactions().add(guild_id=GUILD_ID, fight_id=7, currency=0, mode=Loot.CLAIM,
		                                   items=[{"item_id" : self.wand.id, "name" : "Wand", "amount" : 1,
		                                           "claims" : [self.character.id, self.bryn.id], "winner" : None}])
		Loot.settle(loot, self.fight(), rng=FixedRng(3, 17))
		won = [entry for entry in CharacterGearTransactions().get_all(self.bryn.id) if entry.gear_item_id == self.wand.id]
		self.assertEqual(len(won), 1)
		self.assertFalse(won[0].identified)

	def test_roll_off_rerolls_ties(self) :
		self.assertEqual(Loot.roll_off([1, 2], FixedRng(10, 10, 4, 12)), 2)


class TestIdentifyService(MagicTestCase) :

	def test_price(self) :
		merchant = MerchantTransactions().add(GUILD_ID, "Sage", markup=1.5, services=[Merchants.IDENTIFY])
		self.assertEqual(Merchants.identify_price(merchant, self.wand), 180)
		self.assertEqual(Merchants.identify_price(merchant, self.plain), 10)
