"""SPECIAL stats: the server's rules, point-buy, rolling, and the levels that earn more points.

The defaults follow Fallout 1 and 2: every stat starts at 5, a new character has 5 extra points, and stats stay
between 1 and 10. Servers can change each number (see ConfigMapping).
"""
import random
import re
from dataclasses import dataclass

from classes.kernel.ConfigData import ConfigData
from database.database import Characters
from database.transactions.CharacterTransactions import CharacterTransactions
from resources.configs.ConfigMapping import ConfigMapping, defaults

STATS = ["strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck"]

POINT_BUY = "point_buy"
ROLLED = "rolled"

# A rolled stat is 2d6-2, kept inside the server's limits.
ROLL_DICE = 2
ROLL_SIDES = 6
ROLL_MODIFIER = -2
# How often a roll that adds up to more than point-buy allows is rolled again before it is lowered instead.
ROLL_ATTEMPTS = 200


@dataclass
class StatRules :
	"""A server's SPECIAL rules."""
	base: int
	bonus: int
	minimum: int
	maximum: int
	method: str

	@property
	def budget(self) -> int :
		"""The most points a new character's stats can add up to."""
		return self.base * len(STATS) + self.bonus

	@property
	def methods(self) -> list[str] :
		return [POINT_BUY, ROLLED] if self.method == "both" else [self.method]


class Special :

	# == rules ==

	# ============================================================
	@staticmethod
	def rules(guild_id: int) -> StatRules :
		"""The guild's rules. Settings that contradict each other fall back to the defaults, so a wrong setting can
		never make character creation impossible."""
		config = ConfigData()
		minimum = config.get_int(guild_id, ConfigMapping.STAT_MIN)
		maximum = config.get_int(guild_id, ConfigMapping.STAT_MAX)
		base = config.get_int(guild_id, ConfigMapping.STAT_BASE)
		if minimum > maximum :
			minimum, maximum = defaults[ConfigMapping.STAT_MIN], defaults[ConfigMapping.STAT_MAX]
		base = max(minimum, min(base, maximum))
		bonus = max(0, config.get_int(guild_id, ConfigMapping.STAT_BONUS))
		method = str(config.get_key(guild_id, ConfigMapping.STAT_METHOD)).lower()
		if method not in ("both", POINT_BUY, ROLLED) :
			method = defaults[ConfigMapping.STAT_METHOD]
		return StatRules(base=base, bonus=bonus, minimum=minimum, maximum=maximum, method=method)

	# == setting stats ==

	# ============================================================
	@staticmethod
	def parse(text: str) -> list[int] | None :
		"""Reads seven whole numbers from a message, in the order of STATS. None when it is not exactly seven."""
		numbers = re.findall(r"-?\d+", text)
		if len(numbers) != len(STATS) or re.sub(r"[-\d\s,;/|]", "", text) :
			return None
		return [int(number) for number in numbers]

	# ============================================================
	@staticmethod
	def check_values(values: list[int], rules: StatRules, budget: int,
	                 limits: dict[str, tuple[int, int]] | None = None) -> str | None :
		"""Why these seven values are not allowed, or None when they are. limits are a species' own {stat: (min,
		max)}; without them every stat follows the server's limits."""
		for stat, value in zip(STATS, values) :
			low, high = limits[stat] if limits else (rules.minimum, rules.maximum)
			if value < low or value > high :
				if limits and limits[stat] != (rules.minimum, rules.maximum) :
					return f"{stat.capitalize()} is {value}, but for your species it has to be between {low} and {high}."
				return f"{stat.capitalize()} is {value}, but every stat has to be between {low} and {high}."
		if sum(values) > budget :
			return f"That adds up to {sum(values)} points, but you have {budget}. Take {sum(values) - budget} off."
		return None

	# ============================================================
	@staticmethod
	def roll(rules: StatRules, rng: random.Random | None = None) -> list[int] :
		"""Rolls seven values, highest first. A roll that adds up to more than point-buy allows is rolled again."""
		rng = rng or random
		values = []
		for _ in range(ROLL_ATTEMPTS) :
			values = []
			for _ in STATS :
				value = sum(rng.randint(1, ROLL_SIDES) for _ in range(ROLL_DICE)) + ROLL_MODIFIER
				values.append(max(rules.minimum, min(value, rules.maximum)))
			if sum(values) <= rules.budget :
				return sorted(values, reverse=True)
		# With a very small budget almost every roll is too high; lower the last roll's highest values instead of
		# rolling forever.
		while sum(values) > rules.budget and max(values) > rules.minimum :
			values[values.index(max(values))] -= 1
		return sorted(values, reverse=True)

	# ============================================================
	@staticmethod
	def check_assignment(values: list[int], rolled: list[int]) -> str | None :
		"""Why these values are not the rolled ones in some order, or None when they are."""
		if sorted(values) != sorted(rolled) :
			return f"Use each rolled value exactly once: {', '.join(str(value) for value in rolled)}."
		return None

	# ============================================================
	@staticmethod
	def as_dict(values: list[int]) -> dict[str, int] :
		return dict(zip(STATS, values))

	# ============================================================
	@staticmethod
	def summary(stats: dict[str, int]) -> str :
		"""S 5 · P 6 · ..."""
		return " · ".join(f"{stat[0].upper()} {stats.get(stat, 0)}" for stat in STATS)

	# == levels ==

	# ============================================================
	@staticmethod
	def xp_for_level(level: int, base: int) -> int :
		"""The total XP needed to reach a level: base x L(L-1)/2."""
		return base * level * (level - 1) // 2

	# ============================================================
	@staticmethod
	def level_for_xp(xp: int, base: int) -> int :
		level = 1
		while Special.xp_for_level(level + 1, base) <= xp :
			level += 1
		return level

	# ============================================================
	@staticmethod
	def level_base(guild_id: int) -> int :
		base = ConfigData().get_int(guild_id, ConfigMapping.LEVEL_BASE)
		return base if base and base > 0 else defaults[ConfigMapping.LEVEL_BASE]

	# ============================================================
	@staticmethod
	def _progress(character: Characters, **changes) -> tuple[Characters, int] :
		base = Special.level_base(character.guild_id)
		points = max(0, ConfigData().get_int(character.guild_id, ConfigMapping.POINTS_PER_LEVEL) or 0)
		return CharacterTransactions().progress(character.id, lambda xp : Special.level_for_xp(xp, base), points,
		                                        **changes)

	# ============================================================
	@staticmethod
	def set_xp(character: Characters, xp: int) -> tuple[Characters, int] :
		"""Sets the character's XP and levels it up when the XP has reached new levels.

		A level never goes down: when the XP drops, the character keeps its level and the points it earned.
		@return: the updated character and the number of levels gained.
		"""
		return Special._progress(character, set_xp=xp)

	# ============================================================
	@staticmethod
	def add_xp(character: Characters, amount: int, currency: int = 0) -> tuple[Characters, int] :
		"""Adds XP (and currency) to what the character has in the database, not to the copy passed in."""
		return Special._progress(character, add_xp=amount, add_currency=currency)

	# ============================================================
	@staticmethod
	def spend(character: Characters, stat: str, amount: int = 1) -> tuple[Characters | None, str | None] :
		"""Spends unspent points on a stat.

		@return: the updated character, or None and the reason it was refused.
		"""
		stat = stat.lower()
		if stat not in STATS :
			return None, f"{stat} is not a SPECIAL stat."
		if amount < 1 :
			return None, "Spend at least 1 point."
		if amount > character.unspent_points :
			return None, f"{character.name} has {character.unspent_points} unspent points."
		# Imported here: the species rules are built on this module.
		from classes.characters.SpeciesRules import SpeciesRules
		from database.transactions.SpeciesTransactions import SpeciesTransactions

		rules = Special.rules(character.guild_id)
		maximum = SpeciesRules.limits(SpeciesTransactions().get(character.species_id), rules)[stat][1]
		current = getattr(character, stat)
		if current + amount > maximum :
			return None, f"{stat.capitalize()} is {current} and cannot go above {maximum}."
		updated = CharacterTransactions().update(character.id, **{stat : current + amount,
		                                                          "unspent_points" : character.unspent_points - amount})
		return updated, None
