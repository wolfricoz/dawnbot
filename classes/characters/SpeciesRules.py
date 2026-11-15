"""How a species changes the SPECIAL rules: its own limits per stat and its changes to the starting values.

Player-made species have to balance out: every point a limit goes up, another limit goes down by the same amount (for
the maximums and the minimums separately), and the starting changes add up to 0. A species' limits stay between -2
and 13.
"""
from classes.characters.Special import STATS, StatRules
from database.database import Species

LOWEST = -2
HIGHEST = 13
# The largest change to one starting value.
MAX_MODIFIER = 5
# What describe says about a species that leaves every stat as it is.
NO_CHANGES = "No changes to the SPECIAL stats."

Limits = dict[str, tuple[int, int]]


class SpeciesRules :

	# ============================================================
	@staticmethod
	def limits(species: Species | None, rules: StatRules, data: dict | None = None, legendary: bool = False) -> Limits :
		"""{stat: (min, max)}; stats the species does not change follow the server. data replaces the species' own
		stat_limits, for a definition that is not saved yet. Legendary characters have their maximums doubled."""
		data = data if data is not None else (species.stat_limits if species is not None else {}) or {}
		limits = {stat : tuple(data[stat]) if stat in data else (rules.minimum, rules.maximum) for stat in STATS}
		if legendary :
			limits = {stat : (low, high * 2 if high > 0 else high) for stat, (low, high) in limits.items()}
		return limits

	# ============================================================
	@staticmethod
	def modifiers(species: Species | None, data: dict | None = None) -> dict[str, int] :
		data = data if data is not None else (species.stat_modifiers if species is not None else {}) or {}
		return {stat : int(data.get(stat, 0)) for stat in STATS}

	# ============================================================
	@staticmethod
	def start_values(rules: StatRules, limits: Limits, modifiers: dict[str, int]) -> dict[str, int] :
		"""What every stat starts at with point-buy."""
		return {stat : max(limits[stat][0], min(rules.base + modifiers[stat], limits[stat][1])) for stat in STATS}

	# ============================================================
	@staticmethod
	def apply_modifiers(values: dict[str, int], limits: Limits, modifiers: dict[str, int]) -> dict[str, int] :
		"""Rolled values with the species' changes added, kept inside its limits."""
		return {stat : max(limits[stat][0], min(values[stat] + modifiers[stat], limits[stat][1])) for stat in STATS}

	# ============================================================
	@staticmethod
	def check_definition(minimums: list[int], maximums: list[int], modifiers: list[int],
	                     rules: StatRules) -> str | None :
		"""Why these limits and starting changes do not balance out, or None when they do."""
		for stat, low, high in zip(STATS, minimums, maximums) :
			if not LOWEST <= low <= HIGHEST or not LOWEST <= high <= HIGHEST :
				return f"Every limit has to be between {LOWEST} and {HIGHEST}; check {stat.capitalize()}."
			if low > high :
				return f"{stat.capitalize()}'s minimum ({low}) is higher than its maximum ({high})."
		raised = sum(high - rules.maximum for high in maximums)
		if raised :
			return (f"The maximums go {'up' if raised > 0 else 'down'} by {abs(raised)} in total. Every point one goes "
			        f"up, another has to go down, so the changes add up to 0.")
		lowered = sum(low - rules.minimum for low in minimums)
		if lowered :
			return (f"The minimums go {'up' if lowered > 0 else 'down'} by {abs(lowered)} in total. Every point one goes "
			        f"up, another has to go down, so the changes add up to 0.")
		if any(abs(change) > MAX_MODIFIER for change in modifiers) :
			return f"A starting change can be at most {MAX_MODIFIER} up or down."
		if sum(modifiers) :
			return f"The starting changes add up to {sum(modifiers)}; they have to add up to 0."
		return None

	# ============================================================
	@staticmethod
	def to_data(minimums: list[int], maximums: list[int], modifiers: list[int],
	            rules: StatRules) -> tuple[dict, dict] :
		"""The stat_limits and stat_modifiers to store: only the stats that differ from the server."""
		limits = {stat : [low, high] for stat, low, high in zip(STATS, minimums, maximums)
		          if (low, high) != (rules.minimum, rules.maximum)}
		changes = {stat : change for stat, change in zip(STATS, modifiers) if change}
		return limits, changes

	# ============================================================
	@staticmethod
	def describe(species: Species | None, rules: StatRules, limits_data: dict | None = None,
	             modifiers_data: dict | None = None) -> str :
		"""The stats the species changes, one line each, or a note that it changes none."""
		limits = SpeciesRules.limits(species, rules, limits_data)
		modifiers = SpeciesRules.modifiers(species, modifiers_data)
		lines = []
		for stat in STATS :
			parts = []
			if limits[stat] != (rules.minimum, rules.maximum) :
				parts.append(f"{limits[stat][0]} to {limits[stat][1]}")
			if modifiers[stat] :
				parts.append(f"starts {modifiers[stat]:+d}")
			if parts :
				lines.append(f"**{stat.capitalize()}:** {', '.join(parts)}")
		return "\n".join(lines) or NO_CHANGES
