"""The SPECIAL picker: setting the stats step of an interview with one menu per stat instead of typing seven numbers.

With point-buy, each menu lists the values the stat can take with the points that are left, so the total can never go
over the budget. With rolling, each menu lists the rolled values that are not placed on another stat yet.

What the player picks is kept in their draft (stat_work for point-buy, stat_assign for rolling), so the picker keeps
working after a restart. Confirming feeds the seven values to the interview as if they were typed, so the same checks
apply. This module never talks to Discord; views/multiselect/StatPicker.py draws it.
"""
from dataclasses import dataclass, field

from classes.characters.Interview import Interview, RESPEC
from classes.characters.SpeciesRules import SpeciesRules
from classes.characters.Special import POINT_BUY, ROLLED, STATS, Special
from database.database import Drafts
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.DraftTransactions import DraftTransactions

# A Discord menu lists at most 25 options.
OPTION_LIMIT = 25


@dataclass
class Option :
	value: str
	label: str
	description: str | None = None
	default: bool = False


@dataclass
class State :
	"""Everything the picker shows."""
	method: str
	# The value each stat has now; None for a stat no rolled value is placed on yet.
	values: dict[str, int | None]
	options: dict[str, list[Option]]
	limits: dict[str, tuple[int, int]]
	budget: int = 0
	left: int = 0
	rolled: list[int] = field(default_factory=list)
	unplaced: list[int] = field(default_factory=list)
	rerolls: int = 0
	modifiers: dict[str, int] = field(default_factory=dict)
	complete: bool = False


# ============================================================
def is_open(draft: Drafts | None) -> bool :
	"""Whether the draft is at the stats step of a character interview, where the picker is used."""
	return draft is not None and draft.step == "stats" and isinstance(draft.answers, dict) \
		and "queue" in draft.answers and draft.kind in ("create", "edit", "import", RESPEC)


# ============================================================
def method(draft: Drafts) -> str :
	return draft.answers.get("stat_method") or Special.rules(draft.guild_id).methods[0]


# ============================================================
def _defaults(draft: Drafts) -> dict[str, int] :
	"""Where point-buy starts: the stats already set, the character's current stats for a respec, or the starting
	values."""
	answers = draft.answers
	if answers.get("stats") and answers.get("stat_method", POINT_BUY) == POINT_BUY :
		return dict(answers["stats"])
	if draft.kind == RESPEC and draft.target_id :
		character = CharacterTransactions().get_by_id(draft.target_id)
		if character is not None :
			return {stat : getattr(character, stat) for stat in STATS}
	return SpeciesRules.start_values(Special.rules(draft.guild_id), Interview._limits(draft), Interview._modifiers(draft))


# ============================================================
def _fits(values: dict, limits: dict, budget: int) -> bool :
	return set(values) == set(STATS) and sum(values.values()) <= budget \
		and all(limits[stat][0] <= values[stat] <= limits[stat][1] for stat in STATS)


# ============================================================
def _work(draft: Drafts, limits: dict, budget: int) -> dict[str, int] :
	"""The point-buy values picked so far, started again when they no longer fit (the species changed)."""
	work = draft.answers.get("stat_work")
	if isinstance(work, dict) and _fits(work, limits, budget) :
		return dict(work)
	work = _defaults(draft)
	if not _fits(work, limits, budget) :
		work = {stat : limits[stat][0] for stat in STATS}
	return work


# ============================================================
def _assignment(draft: Drafts) -> dict[str, int] :
	"""Which rolled value (by its place in the roll) each stat has; a stale assignment is dropped."""
	rolled = draft.rolled_values or []
	assign = draft.answers.get("stat_assign")
	if not isinstance(assign, dict) :
		return {}
	indexes = [index for index in assign.values() if isinstance(index, int)]
	if len(set(indexes)) != len(indexes) or any(not 0 <= index < len(rolled) for index in indexes) :
		return {}
	return {stat : index for stat, index in assign.items() if stat in STATS and isinstance(index, int)}


# ============================================================
def _window(options: list[Option], current: int | None) -> list[Option] :
	"""At most 25 options, centred on the current value."""
	if len(options) <= OPTION_LIMIT :
		return options
	index = next((i for i, option in enumerate(options) if option.default), 0)
	start = max(0, min(index - OPTION_LIMIT // 2, len(options) - OPTION_LIMIT))
	return options[start : start + OPTION_LIMIT]


# ============================================================
def state(draft: Drafts) -> State :
	"""What the picker shows for the draft as it is now."""
	limits = Interview._limits(draft)
	modifiers = Interview._modifiers(draft)
	if method(draft) == ROLLED :
		Interview._ensure_roll(draft)
		rolled = list(draft.rolled_values)
		assign = _assignment(draft)
		used = set(assign.values())
		options = {}
		for stat in STATS :
			own = assign.get(stat)
			# The stat's own value comes first so it stays selected; equal values after it are one option.
			order = ([own] if own is not None else []) + [index for index in range(len(rolled))
			                                               if index not in used]
			choices, seen = [], set()
			for index in order :
				value = rolled[index]
				if value in seen :
					continue
				seen.add(value)
				final = SpeciesRules.apply_modifiers({s : value for s in STATS}, limits, modifiers)[stat]
				choices.append(Option(str(index), f"{stat.capitalize()} {value}",
				                      f"{final} after your species" if final != value else None, index == own))
			options[stat] = sorted(choices, key=lambda option : -rolled[int(option.value)])
		values = {stat : rolled[assign[stat]] if stat in assign else None for stat in STATS}
		unplaced = [value for index, value in enumerate(rolled) if index not in used]
		return State(ROLLED, values, options, limits, rolled=rolled, unplaced=sorted(unplaced, reverse=True),
		             rerolls=draft.rerolls, modifiers=modifiers, complete=len(assign) == len(STATS))

	budget = Interview._budget(draft)
	work = _work(draft, limits, budget)
	left = budget - sum(work.values())
	starts = _defaults(draft) if draft.kind == RESPEC else SpeciesRules.start_values(
		Special.rules(draft.guild_id), limits, modifiers)
	options = {}
	for stat in STATS :
		low, high = limits[stat]
		top = min(high, work[stat] + left)
		choices = []
		for value in range(low, top + 1) :
			change = value - work[stat]
			if value == work[stat] :
				description = f"current, {left} point{'s' if left != 1 else ''} left"
			elif change > 0 :
				description = f"costs {change} point{'s' if change != 1 else ''}, leaves {left - change}"
			else :
				description = f"frees {-change} point{'s' if change != -1 else ''}, leaves {left - change}"
			if value == starts.get(stat) and value != work[stat] :
				description += " (start)"
			choices.append(Option(str(value), f"{stat.capitalize()} {value}", description, value == work[stat]))
		options[stat] = _window(choices, work[stat])
	return State(POINT_BUY, dict(work), options, limits, budget=budget, left=left, modifiers=modifiers,
	             complete=True)


# ============================================================
def choose(draft: Drafts, stat: str, value: str) -> str | None :
	"""Applies a pick from a stat's menu. Returns why it was refused, or None."""
	if stat not in STATS :
		return "That is not a SPECIAL stat."
	try :
		number = int(value)
	except ValueError :
		return "That is not a value I can use."
	if method(draft) == ROLLED :
		Interview._ensure_roll(draft)
		assign = _assignment(draft)
		if not 0 <= number < len(draft.rolled_values) :
			return "That value is not part of your roll."
		# Equal rolled values share an option, so take a copy of that value that is still free.
		value_wanted = draft.rolled_values[number]
		free = [index for index, rolled in enumerate(draft.rolled_values)
		        if rolled == value_wanted and (index not in assign.values() or assign.get(stat) == index)]
		if not free :
			return f"Every {value_wanted} in your roll is already placed on another stat."
		assign[stat] = number if number in free else free[0]
		draft.answers["stat_assign"] = assign
	else :
		limits = Interview._limits(draft)
		budget = Interview._budget(draft)
		work = _work(draft, limits, budget)
		low, high = limits[stat]
		if not low <= number <= high :
			return f"{stat.capitalize()} has to be between {low} and {high}."
		if sum(work.values()) - work[stat] + number > budget :
			return "You don't have enough points left for that."
		work[stat] = number
		draft.answers["stat_work"] = work
	DraftTransactions().save(draft)
	return None


# ============================================================
def reset(draft: Drafts) -> None :
	"""Back to where this step started (the saved stats, or the starting values), or every rolled value unplaced."""
	draft.answers.pop("stat_work", None)
	draft.answers.pop("stat_assign", None)
	DraftTransactions().save(draft)


# ============================================================
def reroll(draft: Drafts) -> None :
	draft.rolled_values = Special.roll(Special.rules(draft.guild_id))
	draft.rerolls += 1
	draft.answers.pop("stat_assign", None)
	DraftTransactions().save(draft)


# ============================================================
def answer_text(draft: Drafts) -> str | None :
	"""The seven values in stat order, as the interview reads a typed answer; None while a rolled value is unplaced."""
	current = state(draft)
	if not current.complete :
		return None
	return " ".join(str(current.values[stat]) for stat in STATS)


# ============================================================
def header(draft: Drafts) -> str :
	"""The text above the menus."""
	current = state(draft)
	rules = Special.rules(draft.guild_id)
	lines = []
	if current.method == ROLLED :
		lines.append(f"### Place your SPECIAL roll\nRolled: **{', '.join(str(value) for value in current.rolled)}**")
		if current.unplaced :
			lines.append(f"Still to place: {', '.join(str(value) for value in current.unplaced)}")
		else :
			lines.append("Every value is placed. Press **Confirm** to continue.")
		if any(current.modifiers.values()) :
			lines.append("Your species then changes them: " + ", ".join(
				f"{stat.capitalize()} {change:+d}" for stat, change in current.modifiers.items() if change) + ".")
		lines.append(f"-# Rerolls so far: {current.rerolls}")
	else :
		lines.append(f"### Set your SPECIAL stats\nPoints left: **{current.left}** of {current.budget}")
		if all(limit == (rules.minimum, rules.maximum) for limit in current.limits.values()) :
			lines.append(f"Every stat goes from {rules.minimum} to {rules.maximum}.")
		else :
			lines.append("Your species' limits: " + ", ".join(
				f"{stat[0].upper()} {low}-{high}" for stat, (low, high) in current.limits.items()) + ".")
		lines.append("-# Points you don't spend are kept for later.")
	return "\n".join(lines)
