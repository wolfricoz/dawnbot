"""Phase 6 of design/economy.md: healers, starter kits, weapon training and lifestyle."""
from datetime import datetime, timedelta, timezone

from classes.combat.CombatFlow import CombatFlow
from classes.economy import Lifestyle, Merchants, Spending
from classes.gear import Condition
from classes.gear.Gear import ARMOR, Gear, WEAPON
from classes.kernel.ConfigData import ConfigData
from database.transactions.CharacterGearTransactions import CharacterGearTransactions
from database.transactions.CharacterInfoTransactions import CharacterInfoTransactions
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.CurrencyTransactions import CurrencyTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from database.transactions.MerchantTransactions import MerchantTransactions
from database.transactions.OccupationTransactions import OccupationTransactions
from resources.configs.ConfigMapping import ConfigMapping
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID

OTHER_ID = 288647277181665280


class SpendingTestCase(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()
		items = GearItemTransactions()
		self.sword = items.add(GUILD_ID, WEAPON, "Sword", price=250)
		self.jack = items.add(GUILD_ID, ARMOR, "Jack", price=150)
		self.merchant = MerchantTransactions().add(GUILD_ID, "Hilde", markup=1.2,
		                                           services=[Merchants.HEALING, Merchants.TRAINING])
		self.character = self.add_character(currency=30000)

	def character_now(self) :
		return CharacterTransactions().get_by_id(self.character.id)


class TestHealers(SpendingTestCase) :

	def test_injury_lines_carry_their_severity(self) :
		text = CombatFlow.injury_text(None, "Ambush", "a deep cut", "serious")
		self.assertEqual(text, "[serious] a deep cut (Ambush)")
		text = CombatFlow.injury_text(text, "Ambush", "a bruise")
		self.assertEqual(text.splitlines()[1], "a bruise (Ambush)")
		self.assertEqual(Spending.severity_of("[grave] a broken leg"), Spending.GRAVE)
		self.assertEqual(Spending.severity_of("a bruise"), Spending.MINOR)

	def test_healing_takes_an_injury_off_the_sheet(self) :
		CharacterInfoTransactions().add(self.character.id, Spending.INJURIES, "[serious] a deep cut (Ambush)\na bruise")
		lines = Spending.injuries(self.character)
		self.assertEqual(len(lines), 2)
		self.assertEqual(Spending.heal_price(self.merchant, Spending.severity_of(lines[0]), self.character), 1200)
		self.assertEqual(Spending.remove_injury(self.character, 0), "[serious] a deep cut (Ambush)")
		self.assertEqual(Spending.injuries(self.character), ["a bruise"])
		Spending.remove_injury(self.character, 0)
		self.assertEqual(Spending.injuries(self.character), [])
		self.assertIsNone(Spending.remove_injury(self.character, 0))


class TestStarterKits(SpendingTestCase) :

	def test_kit_on_top_of_starting_money(self) :
		guard = OccupationTransactions().add(GUILD_ID, "Guard", kit=[self.sword.id, self.jack.id])
		CharacterTransactions().update(self.character.id, occupation_id=guard.id)
		given = Spending.grant_kit(self.character_now(), USER_ID)
		self.assertEqual(sorted(entry.name for entry in given), ["Jack", "Sword"])
		self.assertEqual({entry.source for entry in given}, {Spending.KIT})
		# Kit items sell for nothing.
		self.assertEqual(Gear.sell_value(given[0]), 0)

	def test_kits_can_be_turned_off(self) :
		guard = OccupationTransactions().add(GUILD_ID, "Guard", kit=[self.sword.id])
		CharacterTransactions().update(self.character.id, occupation_id=guard.id)
		ConfigData().add_key(GUILD_ID, ConfigMapping.STARTER_KITS, "DISABLED", overwrite=True)
		self.assertEqual(Spending.grant_kit(self.character_now(), USER_ID), [])


class TestTraining(SpendingTestCase) :

	def test_training_with_a_merchant(self) :
		sword = Gear.grant(self.character, self.sword, USER_ID)
		training, problem = Spending.start_with_merchant(self.character, sword, self.merchant, USER_ID)
		self.assertIsNone(problem)
		self.assertEqual((training.target, training.days_needed, training.paid), ("poor", 1, 600))
		self.assertEqual(self.character_now().currency, 29400)
		training, lines = Spending.train_day(training)
		self.assertEqual(training.state, Spending.DONE)
		self.assertEqual(CharacterGearTransactions().get(sword.id).proficiency, "poor")

	def test_longer_training_takes_days(self) :
		sword = Gear.grant(self.character, self.sword, USER_ID)
		CharacterGearTransactions().update(sword.id, proficiency="average")
		sword = CharacterGearTransactions().get(sword.id)
		training, _ = Spending.start_with_merchant(self.character, sword, self.merchant, USER_ID)
		self.assertEqual((training.target, training.days_needed), ("good", 5))
		self.assertIn("already being trained", Spending.training_problem(sword))
		for _ in range(4) :
			training, _ = Spending.train_day(training)
		self.assertEqual(CharacterGearTransactions().get(sword.id).proficiency, "average")
		training, _ = Spending.train_day(training)
		self.assertEqual(CharacterGearTransactions().get(sword.id).proficiency, "good")

	def test_limits(self) :
		swords = [Gear.grant(self.character, self.sword, USER_ID) for _ in range(3)]
		for sword in swords[:2] :
			CharacterGearTransactions().update(sword.id, proficiency="good")
		CharacterGearTransactions().update(swords[2].id, proficiency="average")
		self.assertIn("at most", Spending.training_problem(CharacterGearTransactions().get(swords[2].id)))
		CharacterGearTransactions().update(swords[0].id, proficiency="excellent")
		self.assertIn("any further", Spending.training_problem(CharacterGearTransactions().get(swords[0].id)))
		plain = MerchantTransactions().add(GUILD_ID, "Plain")
		_, problem = Spending.start_with_merchant(self.character, swords[1], plain, USER_ID)
		self.assertIn("doesn't train", problem)

	def test_training_with_another_players_character(self) :
		master = OccupationTransactions().add(GUILD_ID, "Weaponmaster", trains=True)
		teacher = self.add_character("Teacher", user_id=OTHER_ID, occupation_id=master.id, currency=0)
		sword = Gear.grant(self.character, self.sword, USER_ID)
		training, problem = Spending.start_with_trainer(self.character, sword, teacher, USER_ID)
		self.assertIsNone(problem)
		self.assertEqual(CharacterTransactions().get_by_id(teacher.id).currency, 500)
		self.assertEqual(training.trainer, "Teacher")
		own = self.add_character("Own", occupation_id=master.id)
		other_sword = Gear.grant(self.character, self.sword, USER_ID)
		_, problem = Spending.start_with_trainer(self.character, other_sword, own, USER_ID)
		self.assertIn("own characters", problem)
		plain = self.add_character("Plain", user_id=OTHER_ID)
		_, problem = Spending.start_with_trainer(self.character, other_sword, plain, USER_ID)
		self.assertIn("doesn't train", problem)


class TestLifestyle(SpendingTestCase) :

	def setUp(self) :
		super().setUp()
		ConfigData().add_key(GUILD_ID, ConfigMapping.LIFESTYLE, "ENABLED", overwrite=True)

	def test_off_by_default(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.LIFESTYLE, "DISABLED", overwrite=True)
		self.assertIsNone(Lifestyle.of(self.character))
		self.assertEqual(Lifestyle.haggle_bonus(self.character), 0)
		self.assertIn("doesn't use", Lifestyle.choose(self.character, Lifestyle.WEALTHY)[1])

	def test_choosing_pays_the_first_week(self) :
		self.assertEqual(Lifestyle.of(self.character), Lifestyle.MODEST)
		updated, problem = Lifestyle.choose(self.character, Lifestyle.WEALTHY, USER_ID)
		self.assertIsNone(problem)
		self.assertEqual((updated.lifestyle, updated.currency), (Lifestyle.WEALTHY, 28250))
		self.assertEqual(Lifestyle.haggle_bonus(updated), 2)
		self.assertEqual(Lifestyle.rumor_bonus(updated), 2)
		self.assertEqual(CurrencyTransactions().get_all(self.character.id)[0].reason, Lifestyle.REASON)

	def test_weekly_charge_and_dropping_a_tier(self) :
		now = datetime.now(timezone.utc)
		poorish = self.add_character("Poorish", currency=300)
		CharacterTransactions().update(poorish.id, lifestyle=Lifestyle.WEALTHY, lifestyle_paid_until=now - timedelta(hours=1))
		tier, paid = Lifestyle.weekly(CharacterTransactions().get_by_id(poorish.id), now)
		self.assertEqual((tier, paid), (Lifestyle.MODEST, 250))
		after = CharacterTransactions().get_by_id(poorish.id)
		self.assertEqual((after.lifestyle, after.currency), (Lifestyle.MODEST, 50))
		# Paid for the week: nothing due until then.
		self.assertIsNone(Lifestyle.weekly(after, now + timedelta(days=6)))
		self.assertIsNotNone(Lifestyle.weekly(after, now + timedelta(days=8)))
		self.assertEqual(CharacterTransactions().get_by_id(poorish.id).lifestyle, Lifestyle.DESTITUTE)

	def test_comfortable_looks_after_worn_gear(self) :
		sword = Gear.grant(self.character, self.sword, USER_ID)
		CharacterGearTransactions().update(sword.id, condition=Condition.WORN)
		CharacterTransactions().update(self.character.id, lifestyle=Lifestyle.COMFORTABLE)
		Lifestyle.weekly(self.character_now())
		self.assertEqual(CharacterGearTransactions().get(sword.id).condition, Condition.GOOD)

	def test_haggling_uses_the_lifestyle(self) :
		merchant = MerchantTransactions().add(GUILD_ID, "Haggler", haggle_dc=12)
		CharacterTransactions().update(self.character.id, lifestyle=Lifestyle.DESTITUTE)
		_, lines = Merchants.haggle(merchant, self.character_now(), self.sword)
		self.assertIn("-2", lines[0])
