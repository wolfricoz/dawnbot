"""Dice rolls for /dice: the dice, the modifiers (including one from a character's SPECIAL stat) and how well it went.

A stat gives a modifier of the stat minus the server's STAT_BASE, so an average character (5 by default) rolls at +0,
a 10 at +5 and a 1 at -4. Dice of 100 sides or more triple every modifier, as /dice always has. Modifiers are added
once to the total, not to each die.
"""
import random
from dataclasses import dataclass, field

MIN_SIDES = 2
MAX_SIDES = 1000
MAX_AMOUNT = 50
# Dice with this many sides or more triple their modifiers.
BIG_DIE = 100
BIG_DIE_MULTIPLIER = 3

CRITICAL_SUCCESS = "critical_success"
GREAT = "great"
SUCCESS = "success"
MIXED = "mixed"
POOR = "poor"
CRITICAL_FAILURE = "critical_failure"
# From best to worst.
TIERS = [CRITICAL_SUCCESS, GREAT, SUCCESS, MIXED, POOR, CRITICAL_FAILURE]


@dataclass
class Modifier :
	"""One thing added to the roll, e.g. Strength 8 → +3."""
	label: str
	value: int


@dataclass
class DiceRoll :
	sides: int
	rolls: list[int]
	# Before any multiplier.
	modifiers: list[Modifier] = field(default_factory=list)
	multiplier: int = 1

	@property
	def amount(self) -> int :
		return len(self.rolls)

	@property
	def natural(self) -> int :
		return sum(self.rolls)

	@property
	def modifier(self) -> int :
		return sum(modifier.value for modifier in self.modifiers) * self.multiplier

	@property
	def total(self) -> int :
		return self.natural + self.modifier

	@property
	def notation(self) -> str :
		"""2d20+3"""
		return f"{self.amount}d{self.sides}{self.modifier:+d}" if self.modifier else f"{self.amount}d{self.sides}"

	@property
	def is_critical_success(self) -> bool :
		return all(roll == self.sides for roll in self.rolls)

	@property
	def is_critical_failure(self) -> bool :
		return all(roll == 1 for roll in self.rolls)

	@property
	def quality(self) -> float :
		"""Where the total lands between the lowest and highest the dice alone can roll, from 0 to 1."""
		lowest, highest = self.amount, self.amount * self.sides
		return max(0.0, min(1.0, (self.total - lowest) / (highest - lowest)))

	@property
	def tier(self) -> str :
		"""Criticals come from the dice alone; the rest from the total, so a good stat makes a roll go better."""
		if self.is_critical_success :
			return CRITICAL_SUCCESS
		if self.is_critical_failure :
			return CRITICAL_FAILURE
		quality = self.quality
		if quality >= 0.75 :
			return GREAT
		if quality >= 0.5 :
			return SUCCESS
		if quality >= 0.25 :
			return MIXED
		return POOR


class Dice :

	# ============================================================
	@staticmethod
	def check(sides: int, amount: int) -> str | None :
		"""Why these dice can't be rolled, or None when they can."""
		if sides < MIN_SIDES or sides > MAX_SIDES :
			return f"Dice need between {MIN_SIDES} and {MAX_SIDES} sides."
		if amount < 1 or amount > MAX_AMOUNT :
			return f"You can roll between 1 and {MAX_AMOUNT} dice at once."
		return None

	# ============================================================
	@staticmethod
	def stat_modifier(value: int, base: int) -> int :
		return value - base

	# ============================================================
	@staticmethod
	def roll(sides: int, amount: int = 1, modifiers: list[Modifier] | None = None,
	         rng: random.Random | None = None) -> DiceRoll :
		rng = rng or random
		modifiers = [modifier for modifier in modifiers or [] if modifier.value]
		return DiceRoll(sides=sides, rolls=[rng.randint(1, sides) for _ in range(amount)], modifiers=modifiers,
		                multiplier=BIG_DIE_MULTIPLIER if sides >= BIG_DIE else 1)
