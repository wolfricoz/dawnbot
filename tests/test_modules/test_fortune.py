"""Bad-roll protection: after 3 failed rolls in a row, the next failed roll is made again once."""
import unittest

from classes.combat import Fortune
from classes.combat.CombatFlow import CombatFlow
from classes.dice.Dice import Dice
from database.transactions.CharacterTransactions import CharacterTransactions
from modules.Tools import BAD_TIERS
from test_modules.base import DatabaseTestCase
from test_modules.test_combat import Dice as Rolls, duel, engine


def maker(*values) :
	values = list(values)
	return lambda : values.pop(0)


class TestFortuneRules(unittest.TestCase) :

	def test_streaks(self) :
		ok = lambda value : value >= 10
		same = lambda value : value
		self.assertEqual(Fortune.roll(0, maker(4), ok, same), (4, 1, None))
		self.assertEqual(Fortune.roll(2, maker(4), ok, same), (4, 3, None))
		self.assertEqual(Fortune.roll(2, maker(12), ok, same), (12, 0, None))
		# Armed: a failure is made again and the better result counts.
		self.assertEqual(Fortune.roll(3, maker(4, 15), ok, same), (15, 0, 4))
		self.assertEqual(Fortune.roll(3, maker(6, 2), ok, same), (6, 1, 6))
		self.assertEqual(Fortune.roll(3, maker(11), ok, same), (11, 0, None))
		self.assertTrue(Fortune.armed(3))
		self.assertFalse(Fortune.armed(None))

	def test_bad_dice_rolls(self) :
		poor = Dice.roll(20, 1, rng=Rolls(2))
		good = Dice.roll(20, 1, rng=Rolls(15))
		self.assertIn(poor.tier, BAD_TIERS)
		self.assertNotIn(good.tier, BAD_TIERS)


class TestFortuneInFights(unittest.TestCase) :

	def setUp(self) :
		self.fight = duel()
		self.ayla = self.fight.combatant(1)
		self.ayla.character_id = 50

	def test_failed_attacks_build_up_and_then_get_a_second_roll(self) :
		run = engine(self.fight, 2)
		run.start()
		run.attack(self.ayla, 2)
		self.assertEqual((self.ayla.stats["bad_streak"], run.outcome.streaks), (1, {50 : 1}))
		self.ayla.stats["bad_streak"] = 3
		self.ayla.ap = 7
		run = engine(self.fight, 2, 15, 3)
		run.attack(self.ayla, 2)
		self.assertTrue(any("luck turns" in line for line in run.outcome.lines))
		self.assertLess(self.fight.combatant(2).hp, 30)
		self.assertEqual(self.ayla.stats["bad_streak"], 0)

	def test_npcs_have_no_protection(self) :
		bandit = self.fight.combatant(2)
		bandit.stats["bad_streak"] = 3
		run = engine(self.fight, 2, 15)
		run.resolve_attack(bandit, self.ayla, bandit.weapons[0])
		self.assertEqual(self.ayla.hp, 30)
		self.assertEqual(run.outcome.streaks, {})

	def test_saves_count(self) :
		self.ayla.stats["bad_streak"] = 3
		run = engine(self.fight, 3, 18)
		save = run.fortune(self.ayla, lambda : run.rng.randint(1, 20), lambda value : value >= 12,
		                   lambda value : value)
		self.assertEqual(save, 18)


class TestFortuneStorage(DatabaseTestCase) :

	def test_characters_keep_their_streak(self) :
		self.add_server()
		character = self.add_character()
		result, first = Fortune.for_character(character.id, maker(3), lambda value : value >= 10, lambda value : value)
		self.assertEqual((result, first, CharacterTransactions().get_by_id(character.id).bad_streak), (3, None, 1))
		CombatFlow.save_streaks({character.id : 3})
		result, first = Fortune.for_character(character.id, maker(3, 14), lambda value : value >= 10,
		                                      lambda value : value)
		self.assertEqual((result, first, CharacterTransactions().get_by_id(character.id).bad_streak), (14, 3, 0))
		fight = duel()
		fight.combatant(1).character_id = character.id
		CombatFlow.save_streaks({character.id : 2})
		CombatFlow.refresh_streaks(fight)
		self.assertEqual(fight.combatant(1).stats["bad_streak"], 2)
