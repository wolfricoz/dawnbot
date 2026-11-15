"""Roll tables (design/roleplay-tools.md, section 9): reading the entries staff paste, rolling, and filling in inline
dice and nested tables. No Discord here.

Staff paste one entry per line. A table is rolled over ranges or by weight:
- `01-05: A rusty key` (or `6: …`, `7. …`) gives the entry a range; the table rolls 1dN, N being the highest number.
- `3x A rusty key` gives it a weight; lines without a prefix weigh 1. Ranges and weights can't be mixed.
Blank lines and lines starting with `#` are skipped.

Inside an entry, `{2d6}` (also `{d8}`, `{1d4+1}`) is rolled when the entry comes up and `[[Other table]]` rolls that
table in its place, at most 3 tables deep. After the text, `| item: Arming Sword`, `| currency: 2d6`, `| xp: 50` and
`| npc: 1d4 Grey Wolf` add actions, which a GM applies with the roll card's Grant and Start fight buttons.
"""
import random
import re
from dataclasses import dataclass, field

WEIGHTS = "weights"
MAX_ENTRIES = 200
MAX_RANGE = 1000
MAX_WEIGHT = 100
MAX_DEPTH = 3
ENTRY_LIMIT = 1000
INLINE_AMOUNT = 50
INLINE_SIDES = 1000

ITEM = "item"
CURRENCY = "currency"
XP = "xp"
NPC = "npc"
ACTION_KINDS = [ITEM, CURRENCY, XP, NPC]
AMOUNT_LIMIT = 1000000
NPC_LIMIT = 10

RANGE_PREFIX = re.compile(r"^(\d{1,4})(?:\s*[-–]\s*(\d{1,4}))?\s*[:.)]\s*")
WEIGHT_PREFIX = re.compile(r"^(\d{1,3})\s*[x×]\s+", re.IGNORECASE)
INLINE_DICE = re.compile(r"\{\s*(\d{0,2})\s*d\s*(\d{1,4})\s*(?:([+-])\s*(\d{1,6}))?\s*\}", re.IGNORECASE)
NESTED = re.compile(r"\[\[([^\[\]]{1,100})\]\]")
AMOUNT = re.compile(r"^(?:(\d{0,2})\s*d\s*(\d{1,4})\s*(?:([+-])\s*(\d{1,6}))?|(\d{1,7}))$", re.IGNORECASE)
# Wide on purpose: a count that is too big is caught and refused instead of becoming part of the name.
NPC_ACTION = re.compile(r"^(?:(\d{0,4}\s*d\s*\d{1,7}(?:\s*[+-]\s*\d{1,7})?|\d{1,7})\s+)?(.+)$", re.IGNORECASE)


@dataclass
class Parsed :
	"""What a pasted table turned into."""
	entries: list[dict]
	dice: str
	errors: list[str] = field(default_factory=list)


@dataclass
class Rolled :
	"""One roll on a table, with everything filled in."""
	natural: int
	rolled: int
	text: str
	actions: list[dict]
	notes: list[str] = field(default_factory=list)


# == amounts ==

# ============================================================
def valid_amount(text: str) -> bool :
	match = AMOUNT.match((text or "").strip())
	if match is None :
		return False
	if match.group(5) is not None :
		return int(match.group(5)) <= AMOUNT_LIMIT
	amount = int(match.group(1) or 1)
	return 1 <= amount <= INLINE_AMOUNT and 1 <= int(match.group(2)) <= INLINE_SIDES


# ============================================================
def roll_amount(text, rng: random.Random | None = None) -> int :
	"""Rolls `2d6+1` or reads `50`; at least 0."""
	if isinstance(text, int) :
		return max(0, text)
	match = AMOUNT.match(str(text or "").strip())
	if match is None :
		return 0
	if match.group(5) is not None :
		return int(match.group(5))
	rng = rng or random
	amount, sides = int(match.group(1) or 1), int(match.group(2))
	total = sum(rng.randint(1, sides) for _ in range(min(amount, INLINE_AMOUNT)))
	if match.group(3) :
		total += int(match.group(4)) * (1 if match.group(3) == "+" else -1)
	return max(0, total)


# == parsing ==

# ============================================================
def parse_action(text: str) -> tuple[dict | None, str | None] :
	"""`item: Arming Sword` → ({"kind": "item", "name": "Arming Sword"}, None), or (None, why it is wrong)."""
	kind, separator, value = text.partition(":")
	kind, value = kind.strip().lower(), value.strip()
	if not separator or kind not in ACTION_KINDS :
		return None, f"`{text.strip()}` is not an action (use item:, currency:, xp: or npc:)"
	if not value :
		return None, f"`{text.strip()}` needs a value"
	if kind == ITEM :
		return {"kind" : ITEM, "name" : value[:100]}, None
	if kind in (CURRENCY, XP) :
		value = value.replace(" ", "")
		if not valid_amount(value) :
			return None, f"`{text.strip()}`: the amount must be a number or dice like 2d6"
		return {"kind" : kind, "amount" : value}, None
	match = NPC_ACTION.match(value)
	count = (match.group(1) or "1").replace(" ", "")
	if not valid_amount(count) :
		return None, f"`{text.strip()}`: the count must be a number or dice like 1d4"
	return {"kind" : NPC, "name" : match.group(2).strip()[:100], "count" : count}, None


# ============================================================
def parse_line(line: str) -> tuple[dict | None, list[str]] :
	"""One pasted line → an entry (with low/high or weight), or None and the problems."""
	problems = []
	entry = {"low" : None, "high" : None, "weight" : 1}
	text = line.strip()
	range_match = RANGE_PREFIX.match(text)
	weight_match = WEIGHT_PREFIX.match(text) if range_match is None else None
	if range_match :
		low = int(range_match.group(1))
		high = int(range_match.group(2)) if range_match.group(2) else low
		if low < 1 or high < low or high > MAX_RANGE :
			problems.append(f"`{range_match.group(0).strip()}` is not a range from 1 to {MAX_RANGE}")
		entry["low"], entry["high"] = low, high
		text = text[range_match.end() :]
	elif weight_match :
		weight = int(weight_match.group(1))
		if not 1 <= weight <= MAX_WEIGHT :
			problems.append(f"a weight must be between 1 and {MAX_WEIGHT}")
		entry["weight"] = weight
		text = text[weight_match.end() :]
	parts = text.split("|")
	entry["text"] = parts[0].strip()[:ENTRY_LIMIT]
	entry["actions"] = []
	for part in parts[1 :] :
		if not part.strip() :
			continue
		action, problem = parse_action(part)
		if problem :
			problems.append(problem)
		else :
			entry["actions"].append(action)
	if not entry["text"] and not entry["actions"] :
		problems.append("an entry needs text")
	return (None if problems else entry), problems


# ============================================================
def parse(text: str) -> Parsed :
	"""Reads a pasted table. errors lists what is wrong, with line numbers; entries are only usable without errors."""
	entries, errors = [], []
	for number, line in enumerate((text or "").splitlines(), start=1) :
		if not line.strip() or line.strip().startswith("#") :
			continue
		entry, problems = parse_line(line)
		errors.extend(f"Line {number}: {problem}" for problem in problems)
		if entry is not None :
			entry["line"] = number
			entries.append(entry)
	if not entries and not errors :
		errors.append("The table has no entries.")
	if len(entries) > MAX_ENTRIES :
		errors.append(f"A table can have at most {MAX_ENTRIES} entries.")
	ranged = [entry for entry in entries if entry["low"] is not None]
	if ranged and len(ranged) != len(entries) :
		errors.append("Give every line a range (like `01-05:`) or none of them; ranges and weights can't be mixed.")
		return Parsed(entries, WEIGHTS, errors)
	dice = WEIGHTS
	if ranged :
		ordered = sorted(ranged, key=lambda entry : entry["low"])
		expected = 1
		for entry in ordered :
			if entry["low"] < expected :
				errors.append(f"Line {entry['line']}: {entry['low']}-{entry['high']} overlaps another range")
			elif entry["low"] > expected :
				gap = f"{expected}" if entry["low"] - 1 == expected else f"{expected}-{entry['low'] - 1}"
				errors.append(f"Nothing covers {gap}")
			expected = max(expected, entry["high"] + 1)
		dice = f"1d{expected - 1}"
	for entry in entries :
		entry.pop("line", None)
	return Parsed(entries, dice, errors)


# ============================================================
def export(entries, dice: str) -> str :
	"""The entries as text that parse() reads back."""
	width = len(str(sides(dice) or 0))
	lines = []
	for entry in entries :
		low, high, weight = _get(entry, "low"), _get(entry, "high"), _get(entry, "weight") or 1
		if dice != WEIGHTS and low is not None :
			prefix = f"{low:0{width}d}: " if low == high else f"{low:0{width}d}-{high:0{width}d}: "
		else :
			prefix = f"{weight}x " if weight != 1 else ""
		actions = "".join(f" | {action_text(action)}" for action in _get(entry, "actions") or [])
		lines.append(f"{prefix}{_get(entry, 'text')}{actions}")
	return "\n".join(lines)


# ============================================================
def action_text(action: dict) -> str :
	"""An action as it is written in a table: `item: Arming Sword`."""
	kind = action.get("kind")
	if kind == ITEM :
		return f"item: {action.get('name')}"
	if kind == NPC :
		count = str(action.get("count", "1"))
		return f"npc: {action.get('name')}" if count == "1" else f"npc: {count} {action.get('name')}"
	return f"{kind}: {action.get('amount')}"


# ============================================================
def sides(dice: str) -> int | None :
	"""N of a `1dN` table; None for a table rolled by weight."""
	if not dice or dice == WEIGHTS or not dice.startswith("1d") :
		return None
	try :
		return int(dice[2 :])
	except ValueError :
		return None


# ============================================================
def _get(entry, key) :
	return entry.get(key) if isinstance(entry, dict) else getattr(entry, key, None)


# == rolling ==

# ============================================================
def pick(entries, dice: str, rng: random.Random | None = None, shift: int = 0) :
	"""Rolls a table: (entry, natural roll, roll after the shift). shift moves the roll towards the high end (Luck),
	staying on the table."""
	rng = rng or random
	if not entries :
		return None, 0, 0
	top = sides(dice)
	if top :
		natural = rng.randint(1, top)
		rolled = max(1, min(top, natural + shift))
		for entry in entries :
			low, high = _get(entry, "low"), _get(entry, "high")
			if low is not None and low <= rolled <= high :
				return entry, natural, rolled
		return None, natural, rolled
	total = sum(max(1, _get(entry, "weight") or 1) for entry in entries)
	natural = rng.randint(1, total)
	rolled = max(1, min(total, natural + shift))
	running = 0
	for entry in entries :
		running += max(1, _get(entry, "weight") or 1)
		if rolled <= running :
			return entry, natural, rolled
	return entries[-1], natural, rolled


# ============================================================
def roll_inline(match: re.Match, rng: random.Random) -> str :
	amount = int(match.group(1) or 1)
	sides_ = int(match.group(2))
	if not 1 <= amount <= INLINE_AMOUNT or not 1 <= sides_ <= INLINE_SIDES :
		return match.group(0)
	total = sum(rng.randint(1, sides_) for _ in range(amount))
	if match.group(3) :
		total += int(match.group(4)) * (1 if match.group(3) == "+" else -1)
	return f"**{max(0, total)}**"


# ============================================================
def fill(text: str, lookup, rng: random.Random | None = None, depth: int = 0) -> tuple[str, list[dict], list[str]] :
	"""Fills in inline dice and nested tables.

	@param lookup: a table's name → (dice, entries), or None when there is no such table.
	@return: the text, the actions of nested entries (dice not rolled yet), and notes about tables that were missing
	or too deep.
	"""
	rng = rng or random
	actions, notes = [], []

	def nested(match: re.Match) -> str :
		name = match.group(1).strip()
		if depth >= MAX_DEPTH :
			notes.append(f"[[{name}]] is more than {MAX_DEPTH} tables deep, so it was not rolled.")
			return name
		found = lookup(name)
		if found is None :
			notes.append(f"There is no table called {name}.")
			return name
		dice, entries = found
		entry, _, _ = pick(entries, dice, rng)
		if entry is None :
			return name
		text_, inner_actions, inner_notes = fill(_get(entry, "text") or "", lookup, rng, depth + 1)
		actions.extend(_get(entry, "actions") or [])
		actions.extend(inner_actions)
		notes.extend(inner_notes)
		return text_

	text = NESTED.sub(nested, text or "")
	text = INLINE_DICE.sub(lambda match : roll_inline(match, rng), text)
	return text, actions, notes


# ============================================================
def resolve(actions: list[dict], rng: random.Random | None = None) -> list[dict] :
	"""Rolls the dice of actions: amounts and NPC counts become numbers."""
	resolved = []
	for action in actions :
		action = dict(action)
		if action.get("kind") in (CURRENCY, XP) :
			action["amount"] = min(AMOUNT_LIMIT, roll_amount(action.get("amount"), rng))
		elif action.get("kind") == NPC :
			action["count"] = max(1, min(NPC_LIMIT, roll_amount(action.get("count", 1), rng)))
		resolved.append(action)
	return resolved


# ============================================================
def roll(entries, dice: str, lookup, rng: random.Random | None = None, shift: int = 0) -> Rolled | None :
	"""Rolls a table and fills everything in."""
	rng = rng or random
	entry, natural, rolled = pick(entries, dice, rng, shift)
	if entry is None :
		return None
	text, nested_actions, notes = fill(_get(entry, "text") or "", lookup, rng)
	actions = resolve(list(_get(entry, "actions") or []) + nested_actions, rng)
	return Rolled(natural=natural, rolled=rolled, text=text or "…", actions=actions, notes=notes)


# ============================================================
def actions_summary(actions: list[dict], currency_name: str = "currency") -> tuple[list[str], list[str]] :
	"""The rewards (items, currency, XP) and the encounter (NPCs) of rolled actions, as short lines."""
	rewards, encounter = [], []
	for action in actions :
		kind = action.get("kind")
		if kind == ITEM :
			rewards.append(str(action.get("name")))
		elif kind == CURRENCY and action.get("amount") :
			rewards.append(f"{action['amount']} {currency_name}")
		elif kind == XP and action.get("amount") :
			rewards.append(f"{action['amount']} XP")
		elif kind == NPC :
			count = action.get("count", 1)
			encounter.append(f"{count} × {action.get('name')}" if count != 1 else str(action.get("name")))
	return rewards, encounter


# ============================================================
def luck_shift(luck: int, base: int = 5) -> int :
	"""How far Luck moves a Luck-touched roll: twice the Luck modifier."""
	return 2 * (int(luck) - base)
