import random
import unittest
from datetime import datetime, timedelta, timezone

from classes.checks import Checks
from classes.economy import Crafting, Downtime, FactionFlow as Rules, RecipePacks
from classes.economy.DowntimeFlow import DowntimeFlow
from classes.economy.FactionFlow import FactionFlow
from classes.economy.JobFlow import JobFlow, PARTIAL, SUCCESS
from classes.gear.Gear import Gear
from classes.gear.Packs import Packs
from classes.kernel.ConfigData import ConfigData
from database.transactions.CharacterGearTransactions import CharacterGearTransactions, MATERIAL
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.EconomyTransactions import EconomyTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from database.transactions.LanguageTransactions import LanguageTransactions
from database.transactions.OccupationTransactions import OccupationTransactions
from database.transactions.ProxyTransactions import ProxyTransactions
from resources.configs.ConfigMapping import ConfigMapping
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID


class FixedRng :
	def __init__(self, *values) :
		self.values = list(values)

	def randint(self, low, high) :
		return self.values.pop(0)

	def random(self) :
		return self.values.pop(0)


class TestRules(unittest.TestCase) :

	def test_tiers(self) :
		self.assertEqual([Rules.tier(value) for value in (-100, -50, -49, -15, -14, 14, 15, 49, 50, 100)],
		                 ["vilified", "vilified", "disliked", "disliked", "neutral", "neutral", "liked", "liked",
		                  "idolized", "idolized"])
		self.assertTrue(Rules.meets(20, "liked"))
		self.assertFalse(Rules.meets(10, "liked"))
		self.assertTrue(Rules.meets(-80, None))

	def test_charisma_scales_gains(self) :
		self.assertEqual(Rules.scaled_gain(10, 5), 10)
		self.assertEqual(Rules.scaled_gain(10, 10), 15)
		self.assertEqual(Rules.scaled_gain(10, 1), 6)
		self.assertEqual(Rules.scaled_gain(10, -5), 5)
		self.assertEqual(Rules.scaled_gain(-10, 10), -10)

	def test_downtime_days(self) :
		now = datetime(2026, 11, 15, 3, tzinfo=timezone.utc)
		self.assertEqual(Downtime.day_key(now, 0), "2026-11-15")
		self.assertEqual(Downtime.day_key(now, 6), "2026-11-14")
		self.assertEqual(Downtime.next_reset(now, 6), datetime(2026, 11, 15, 6, tzinfo=timezone.utc))
		self.assertEqual(Downtime.next_reset(now, 0), datetime(2026, 11, 16, tzinfo=timezone.utc))

	def test_pay_and_study(self) :
		self.assertEqual([Downtime.pay(50, outcome) for outcome in
		                  (Checks.CRIT, Checks.STRONG, Checks.SUCCESS, Checks.FAILURE, Checks.BAD)], [100, 75, 50, 25, 0])
		self.assertEqual(Downtime.pay(50, Checks.SUCCESS, odd_jobs=True), 25)
		self.assertEqual([Downtime.study_stage(points, 10) for points in (9, 10, 19, 20)],
		                 [None, "partial", "partial", "fluent"])

	def test_quality_combat(self) :
		self.assertEqual(Crafting.adjust_combat("weapon", {"hit_mod" : 1}, Crafting.MASTERWORK)["hit_mod"], 2)
		self.assertEqual(Crafting.adjust_combat("armor", {"dt" : 0}, Crafting.CURSED)["dt"], 0)
		self.assertEqual(Crafting.adjust_combat("armor", {"dt" : 2}, Crafting.CURSED)["dt"], 1)
		self.assertEqual(Crafting.adjust_combat("weapon", {"hit_mod" : 0}, None), {"hit_mod" : 0})


class EconomyCase(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()

	def item(self, name, kind="weapon", price=100, **fields) :
		return GearItemTransactions().add(GUILD_ID, kind, name, price=price, **({"requirements" : {}, "combat" : {}} | fields))


class TestFactions(EconomyCase) :

	def test_change_rivals_and_clamp(self) :
		guards = EconomyTransactions().add_faction(GUILD_ID, "Guards")
		thieves = EconomyTransactions().add_faction(GUILD_ID, "Thieves", rivals=[guards.id])
		character = self.add_character(charisma=10)
		lines = FactionFlow.change(character, thieves, 20, "test")
		self.assertEqual(EconomyTransactions().standing(character.id, thieves.id), 30)
		self.assertEqual(EconomyTransactions().standing(character.id, guards.id), -15)
		self.assertEqual(len(lines), 2)
		FactionFlow.change(character, thieves, 500, "test")
		self.assertEqual(EconomyTransactions().standing(character.id, thieves.id), 100)
		FactionFlow.change(character, thieves, -30, "test")
		self.assertEqual(EconomyTransactions().standing(character.id, thieves.id), 70)
		# Losses don't spread to rivals.
		self.assertEqual(EconomyTransactions().standing(character.id, guards.id), -100)

	def test_hidden_factions(self) :
		secret = EconomyTransactions().add_faction(GUILD_ID, "Cult", hidden=True)
		EconomyTransactions().add_faction(GUILD_ID, "Guild")
		character = self.add_character()
		self.assertEqual([faction.name for faction, _ in FactionFlow.visible(character)], ["Guild"])
		FactionFlow.change(character, secret, 5, "test")
		self.assertEqual(len(FactionFlow.visible(character)), 2)

	def test_shop(self) :
		guild_faction = EconomyTransactions().add_faction(GUILD_ID, "Smiths")
		sword = self.item("Guild Blade", faction_id=guild_faction.id, faction_tier="liked")
		plain = self.item("Stick", price=10)
		character = self.add_character()
		self.assertIsNone(FactionFlow.buy_problem(character, plain))
		self.assertIn("needs Liked", FactionFlow.buy_problem(character, sword))
		EconomyTransactions().set_standing(character.id, guild_faction.id, 60, 60, "test", None)
		self.assertIsNone(FactionFlow.buy_problem(character, sword))
		self.assertEqual(FactionFlow.price_for(character, sword, 100), 80)
		EconomyTransactions().set_standing(character.id, guild_faction.id, -60, -120, "test", None)
		self.assertIn("won't sell", FactionFlow.buy_problem(character, sword))


class TestCrafting(EconomyCase) :

	def setUp(self) :
		super().setUp()
		self.iron = self.item("Iron Ingot", MATERIAL, 20)
		self.leather = self.item("Leather Strip", MATERIAL, 10)
		self.sword = self.item("Arming Sword", "weapon", 250, salvage={"Iron Ingot" : 4})
		self.potion = self.item("Healing Draught", "consumable", 40)
		self.character = self.add_character(strength=8)

	def stock(self, item, amount) :
		CharacterGearTransactions().add(self.character.id, item.id, item.name, item.kind, "granted", item.price,
		                                quantity=amount)

	def recipe(self, result, ingredients, **fields) :
		return EconomyTransactions().add_recipe(GUILD_ID, f"Make {result.name}", result_item_id=result.id,
		                                        ingredients=ingredients, stat="strength", dc=12, **fields)

	def test_materials_stack(self) :
		self.stock(self.iron, 2)
		self.stock(self.iron, 3)
		entries = [entry for entry in CharacterGearTransactions().get_all(self.character.id)]
		self.assertEqual(len(entries), 1)
		self.assertEqual(Crafting.owned(self.character.id), {self.iron.id : 5})

	def test_ingredients(self) :
		parsed, problem = Crafting.parse_ingredients(GUILD_ID, "Iron Ingot x2, leather strip")
		self.assertIsNone(problem)
		self.assertEqual(parsed, [{"item_id" : self.iron.id, "amount" : 2}, {"item_id" : self.leather.id,
		                                                                     "amount" : 1}])
		self.assertIsNotNone(Crafting.parse_ingredients(GUILD_ID, "Mithril x2")[1])
		self.assertEqual(Crafting.ingredients_text(parsed), "Iron Ingot ×2, Leather Strip")

	def test_outcomes(self) :
		recipe = self.recipe(self.sword, [{"item_id" : self.iron.id, "amount" : 4}])
		self.assertEqual(Crafting.missing(self.character.id, recipe), ["Iron Ingot ×4"])
		self.stock(self.iron, 20)
		# Strength 8 is +3 against DC 12.
		outcome, _, _ = Crafting.make(self.character, recipe, rng=FixedRng(10))
		self.assertEqual(outcome, Crafting.SUCCESS)
		self.assertEqual(Crafting.owned(self.character.id)[self.iron.id], 16)
		outcome, _, _ = Crafting.make(self.character, recipe, rng=FixedRng(7))
		self.assertEqual(outcome, Crafting.FAILURE)
		self.assertEqual(Crafting.owned(self.character.id)[self.iron.id], 14)
		outcome, _, _ = Crafting.make(self.character, recipe, rng=FixedRng(20))
		self.assertEqual(outcome, Crafting.CRIT)
		outcome, _, _ = Crafting.make(self.character, recipe, rng=FixedRng(1))
		self.assertEqual(outcome, Crafting.BAD)
		names = sorted(entry.name for entry in CharacterGearTransactions().get_all(self.character.id)
		               if entry.kind == "weapon")
		self.assertEqual(names, ["Arming Sword", "Cursed Arming Sword", "Masterwork Arming Sword"])
		self.assertEqual(Crafting.owned(self.character.id)[self.iron.id], 6)

	def test_crit_on_a_consumable_makes_one_extra(self) :
		recipe = self.recipe(self.potion, [{"item_id" : self.leather.id, "amount" : 1}])
		self.stock(self.leather, 1)
		Crafting.make(self.character, recipe, rng=FixedRng(20))
		self.assertEqual(Crafting.owned(self.character.id).get(self.potion.id), 2)

	def test_projects(self) :
		recipe = self.recipe(self.sword, [{"item_id" : self.iron.id, "amount" : 2}], days=2)
		self.stock(self.iron, 2)
		project = Crafting.start_project(self.character, recipe)
		self.assertNotIn(self.iron.id, Crafting.owned(self.character.id))
		outcome, _, finished = Crafting.work(self.character, project, rng=FixedRng(20))
		self.assertFalse(finished)
		outcome, _, finished = Crafting.work(self.character, EconomyTransactions().project(project.id),
		                                     rng=FixedRng(1))
		self.assertEqual(EconomyTransactions().project(project.id).days_done, 0)
		Crafting.work(self.character, EconomyTransactions().project(project.id), rng=FixedRng(15))
		outcome, lines, finished = Crafting.work(self.character, EconomyTransactions().project(project.id),
		                                         rng=FixedRng(15))
		self.assertTrue(finished)
		# The crit made it masterwork and the bad failure left a flaw: they cancel out.
		names = [entry.name for entry in CharacterGearTransactions().get_all(self.character.id) if entry.kind == "weapon"]
		self.assertEqual(names, ["Arming Sword"])
		self.stock(self.iron, 2)
		clean = Crafting.start_project(self.character, recipe)
		Crafting.work(self.character, clean, rng=FixedRng(20))
		Crafting.work(self.character, EconomyTransactions().project(clean.id), rng=FixedRng(15))
		self.assertTrue(any(entry.name == "Masterwork Arming Sword"
		                    for entry in CharacterGearTransactions().get_all(self.character.id)))

	def test_salvage_and_curses(self) :
		entry = CharacterGearTransactions().add(self.character.id, self.sword.id, self.sword.name, "weapon", "shop", 250)
		got, problem = Crafting.salvage(self.character, entry, FixedRng(0.1, 0.9, 0.1, 0.1))
		self.assertIsNone(problem)
		self.assertEqual(got, ["Iron Ingot ×3"])
		self.assertEqual(CharacterGearTransactions().get(entry.id).status, Crafting.SALVAGED)
		armor = self.item("Plate", "armor", 1000)
		cursed = Crafting.give(self.character, armor, 1, Crafting.CURSED)[0]
		self.assertEqual(Gear.sell_value(cursed), 0)
		Gear.equip(cursed)
		cursed = CharacterGearTransactions().get(cursed.id)
		self.assertIsNone(Gear.unequip(cursed))
		other = CharacterGearTransactions().add(self.character.id, armor.id, "Plate", "armor", "shop", 1000)
		self.assertIsNotNone(Gear.equip(other)[1])
		lifted = Crafting.uncurse(cursed)
		self.assertEqual((lifted.name, lifted.quality), ("Plate", None))
		masterwork = Crafting.give(self.character, self.sword, 1, Crafting.MASTERWORK)[0]
		self.assertEqual(Gear.sell_value(masterwork), int(250 * 0.3 * 1.5))

	def test_quality_reaches_fights(self) :
		from classes.combat.Loadout import Loadout

		armor = self.item("Mail", "armor", 500, combat={"armor_class" : "medium", "ac" : 2, "dt" : 2})
		GearItemTransactions().update(self.sword.id, combat={"dice" : "1d8", "hit_mod" : 1})
		sword = GearItemTransactions().get(self.sword.id)
		Crafting.give(self.character, sword, 1, Crafting.MASTERWORK)
		cursed = Crafting.give(self.character, armor, 1, Crafting.CURSED)[0]
		Gear.equip(cursed)
		stats = Loadout.character_stats(self.character)
		weapon = next(weapon for weapon in stats["weapons"] if weapon["name"] == "Masterwork Arming Sword")
		self.assertEqual(weapon["hit_mod"], 2)
		self.assertEqual(stats["armor"]["dt"], 1)
		Crafting.uncurse(CharacterGearTransactions().get(cursed.id))
		self.assertEqual(Loadout.character_stats(self.character)["armor"]["dt"], 2)

	def test_recipe_pack(self) :
		data = RecipePacks.load("fantasy")
		gear = {item["name"].lower() for item in Packs.load("fantasy")["items"]}
		materials = {material["name"].lower() for material in data["materials"]}
		for recipe in data["recipes"] :
			self.assertIn(recipe["result"].lower(), gear | materials, recipe["name"])
			for ingredient in recipe["ingredients"] :
				self.assertIn(ingredient.lower(), gear | materials, recipe["name"])
		added, skipped, missing = RecipePacks.import_into(GUILD_ID, "fantasy")
		# Only the materials and recipes whose results exist here (the setUp's sword and potion) go in.
		self.assertIn("Steel Ingot", added)
		self.assertIn("Iron Ingot", skipped)
		self.assertTrue(missing)
		self.assertIsNotNone(EconomyTransactions().find_recipe(GUILD_ID, "Healing Draught"))


class TestDowntimeAndJobs(EconomyCase) :

	def test_work_pays(self) :
		occupation = OccupationTransactions().add(GUILD_ID, "Smith")
		OccupationTransactions().update(occupation.id, pay=80, work_stat="strength")
		character = self.add_character(strength=8, occupation_id=occupation.id, currency=0)
		random.seed(3)
		outcome, lines, details, _ = DowntimeFlow.work(character, None)
		self.assertEqual(details["earned"], Downtime.pay(80, outcome))
		self.assertEqual(CharacterTransactions().get_by_id(character.id).currency, details["earned"])
		self.assertEqual(details["stat"], "strength")

	def test_once_a_day_and_active(self) :
		character = self.add_character()
		self.assertIn("needs a roleplay post", DowntimeFlow.problem(character))
		ProxyTransactions().log([10], character.id, USER_ID, GUILD_ID, 5, 400, True, 1, 1)
		self.assertIsNone(DowntimeFlow.problem(character))
		EconomyTransactions().add_downtime(character.id, DowntimeFlow.day(GUILD_ID), "work", "success", {})
		self.assertIn("already spent", DowntimeFlow.problem(character))
		ConfigData().add_key(GUILD_ID, ConfigMapping.DOWNTIME_ACTIVE_DAYS, 0, overwrite=True)
		other = self.add_character("Idle")
		self.assertIsNone(DowntimeFlow.problem(other))

	def test_study_teaches(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.STUDY_DAYS, 1, overwrite=True)
		language = LanguageTransactions().add(GUILD_ID, "Elvish")
		character = self.add_character(intelligence=13)
		for _ in range(6) :
			DowntimeFlow.study(character, language)
		known = {entry.language_id : entry.fluency for entry in LanguageTransactions().known(character.id)}
		self.assertEqual(known.get(language.id), "fluent")

	def test_job_pay_out(self) :
		faction = EconomyTransactions().add_faction(GUILD_ID, "Watch")
		poster = self.add_character("Poster", currency=500)
		hero = self.add_character("Hero", user_id=USER_ID + 1, currency=0)
		sidekick = self.add_character("Sidekick", user_id=USER_ID + 2, currency=0)
		job = EconomyTransactions().add_job(GUILD_ID, poster_uid=USER_ID, poster_character_id=poster.id,
		                                    title="Rats", description="Clear the cellar",
		                                    reward={"currency" : 100, "xp" : 40, "items" : []}, slots=2,
		                                    faction_id=faction.id, rep_success=10, rep_failure=5, escrow=200,
		                                    state="taken")
		first = EconomyTransactions().add_claim(job.id, hero.id, hero.uid, "claimed")
		EconomyTransactions().add_claim(job.id, sidekick.id, sidekick.uid, "claimed")
		lines = JobFlow.pay_out(job, [first.id], PARTIAL, USER_ID)
		self.assertEqual(len(lines), 1)
		self.assertEqual(CharacterTransactions().get_by_id(hero.id).currency, 50)
		self.assertEqual(CharacterTransactions().get_by_id(hero.id).xp, 20)
		self.assertEqual(EconomyTransactions().standing(hero.id, faction.id), 5)
		# The poster gets back what wasn't paid out.
		self.assertEqual(CharacterTransactions().get_by_id(poster.id).currency, 650)
		self.assertEqual(CharacterTransactions().get_by_id(sidekick.id).currency, 0)
		self.assertIn("Rats", JobFlow.embed(EconomyTransactions().job(job.id)).title)

	def test_overdue_jobs(self) :
		past = datetime.now(timezone.utc) - timedelta(hours=1)
		job = EconomyTransactions().add_job(GUILD_ID, poster_uid=USER_ID, title="Late", description="x", reward={},
		                                    deadline=past, state="open", escrow=0)
		self.assertEqual([entry.id for entry in EconomyTransactions().overdue_jobs(datetime.now(timezone.utc))],
		                 [job.id])
		self.assertEqual(JobFlow.reward_text(job), "Nothing but gratitude")
		self.assertTrue(SUCCESS)
