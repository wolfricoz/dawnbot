import random
import unittest

from classes.characters.Special import Special
from classes.dice.Dice import (CRITICAL_FAILURE, CRITICAL_SUCCESS, Dice, DiceRoll, GREAT, MIXED, Modifier, POOR,
                               SUCCESS, TIERS)
from classes.dice.DiceCard import DiceCard
from classes.dice.Flavor import Flavor, GENERAL, STAT_LINES, TIER_COLOURS, TIER_LABELS
from classes.kernel.ConfigData import ConfigData
from resources.configs.ConfigMapping import ConfigMapping
from test_modules.base import DatabaseTestCase, GUILD_ID


class TestDice(unittest.TestCase) :

	def test_limits(self) :
		self.assertIsNone(Dice.check(20, 1))
		self.assertIsNotNone(Dice.check(1, 1))
		self.assertIsNotNone(Dice.check(1001, 1))
		self.assertIsNotNone(Dice.check(20, 0))
		self.assertIsNotNone(Dice.check(20, 51))

	def test_rolls_stay_on_the_dice(self) :
		rng = random.Random(1)
		for _ in range(200) :
			roll = Dice.roll(6, 5, rng=rng)
			self.assertEqual(roll.amount, 5)
			self.assertTrue(all(1 <= value <= 6 for value in roll.rolls))

	def test_modifiers_are_added_once(self) :
		roll = DiceRoll(sides=20, rolls=[4, 6], modifiers=[Modifier("Strength 8", 3), Modifier("Bonus", -1)])
		self.assertEqual((roll.natural, roll.modifier, roll.total, roll.notation), (10, 2, 12, "2d20+2"))

	def test_big_dice_triple_modifiers(self) :
		roll = Dice.roll(100, 1, [Modifier("Bonus", 2)], rng=random.Random(3))
		self.assertEqual(roll.modifier, 6)
		self.assertEqual(roll.total, roll.natural + 6)

	def test_zero_modifiers_are_left_out(self) :
		roll = Dice.roll(20, 1, [Modifier("Bonus", 0)])
		self.assertEqual((roll.modifiers, roll.notation), ([], "1d20"))

	def test_stat_modifier_centres_on_the_base(self) :
		self.assertEqual([Dice.stat_modifier(value, 5) for value in (1, 5, 10)], [-4, 0, 5])

	def test_criticals_come_from_the_dice_alone(self) :
		self.assertEqual(DiceRoll(20, [20], [Modifier("Bonus", -10)]).tier, CRITICAL_SUCCESS)
		self.assertEqual(DiceRoll(20, [1], [Modifier("Bonus", 10)]).tier, CRITICAL_FAILURE)
		self.assertEqual(DiceRoll(6, [6, 6, 6]).tier, CRITICAL_SUCCESS)
		self.assertEqual(DiceRoll(6, [6, 6, 5]).tier, GREAT)

	def test_tiers_follow_the_total(self) :
		self.assertEqual(DiceRoll(20, [16]).tier, GREAT)
		self.assertEqual(DiceRoll(20, [11]).tier, SUCCESS)
		self.assertEqual(DiceRoll(20, [6]).tier, MIXED)
		self.assertEqual(DiceRoll(20, [5]).tier, POOR)
		# A good stat lifts the same roll a tier.
		self.assertEqual(DiceRoll(20, [5], [Modifier("Agility 9", 4)]).tier, MIXED)

	def test_quality_stays_between_zero_and_one(self) :
		self.assertEqual(DiceRoll(20, [19], [Modifier("Bonus", 50)]).quality, 1.0)
		self.assertEqual(DiceRoll(20, [2], [Modifier("Bonus", -50)]).quality, 0.0)


class TestFlavor(unittest.TestCase) :

	def test_every_tier_has_text(self) :
		for tier in TIERS :
			self.assertIn(tier, TIER_LABELS)
			self.assertIn(tier, TIER_COLOURS)
			self.assertGreaterEqual(len(GENERAL[tier]), 3)
			for stat, lines in STAT_LINES.items() :
				self.assertTrue(lines.get(tier), f"{stat} has no {tier} lines")

	def test_every_line_names_the_roller(self) :
		for tier in TIERS :
			for line in GENERAL[tier] + [line for lines in STAT_LINES.values() for line in lines[tier]] :
				self.assertIn("{name}", line)
				self.assertIn("Ayla", line.format(name="Ayla"))

	def test_stat_lines_are_used(self) :
		rng = random.Random(5)
		lines = {Flavor.line(GREAT, "Ayla", "strength", rng) for _ in range(200)}
		self.assertTrue(lines & {line.format(name="Ayla") for line in STAT_LINES["strength"][GREAT]})


class TestDiceCard(unittest.TestCase) :

	def test_card_shows_the_roll(self) :
		roll = DiceRoll(20, [17], [Modifier("Strength 8", 3)])
		embed = DiceCard.embed(roll, roller="rico", goal="Lift the gate", character_name="Ayla", stat="strength",
		                       thumbnail_url="https://example.com/a.png", rng=random.Random(1))
		self.assertEqual(embed.title, "Lift the gate")
		self.assertIn("# 🎲 20", embed.description)
		self.assertIn("`17 + 3 = 20`", embed.description)
		self.assertEqual(embed.author.name, "Ayla · Strength check")
		self.assertEqual(embed.footer.text, "Rolled by rico")
		self.assertEqual(embed.thumbnail.url, "https://example.com/a.png")
		self.assertEqual(embed.colour.value, TIER_COLOURS[GREAT])
		self.assertIn("Strength 8 **+3**", embed.fields[2].value)

	def test_card_without_a_goal_or_character(self) :
		embed = DiceCard.embed(DiceRoll(6, [1, 1]), roller="rico", rng=random.Random(1))
		self.assertEqual(embed.title, "Roll: 2d6")
		self.assertEqual(embed.author.name, "rico rolls the dice")
		self.assertEqual(embed.fields[0].name, TIER_LABELS[CRITICAL_FAILURE])
		self.assertEqual(embed.fields[2].value, "none")

	def test_faces(self) :
		self.assertEqual(DiceCard.face(6, 6), "**`⚅ 6`**🔥")
		self.assertEqual(DiceCard.face(1, 20), "`1`💀")
		self.assertEqual(DiceCard.face(7, 20), "`7`")

	def test_tripled_modifiers_are_explained(self) :
		text = DiceCard.modifiers_text(DiceRoll(100, [50], [Modifier("Bonus", 2)], multiplier=3))
		self.assertIn("×3 for a d100 → **+6**", text)

	def test_the_most_dice_fit_in_a_field(self) :
		self.assertLessEqual(len(DiceCard.dice_text(DiceRoll(1000, [1000] * 50))), 1024)

	def test_meter(self) :
		self.assertEqual(DiceCard.meter(DiceRoll(20, [20])), "▰" * 12)
		self.assertEqual(DiceCard.meter(DiceRoll(20, [1])), "▱" * 12)


class TestStatModifierFromServer(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()

	def test_the_server_base_sets_the_centre(self) :
		character = self.add_character(strength=8)
		self.assertEqual(Dice.stat_modifier(character.strength, Special.rules(GUILD_ID).base), 3)
		ConfigData().add_key(GUILD_ID, ConfigMapping.STAT_BASE, 4, overwrite=True)
		self.assertEqual(Dice.stat_modifier(character.strength, Special.rules(GUILD_ID).base), 4)
