"""The rules of checks (design/roleplay-tools.md, sections 7 and 8). No Discord here.

A check is `d20 + stat modifier + modifiers` against a DC. Crits and fumbles follow the combat rules: the crit range
widens with Luck (Rules.crit_min) and fumbles grow at low Luck (Rules.fumble_max); a crit always succeeds and a fumble
always fails. Beating the DC by 5 or more (or a crit) is a strong success, failing by 5 or more (or a fumble) a bad
failure. A character with Luck 0 or below must confirm a natural crit with a second roll, as in combat.
"""
import random
from dataclasses import dataclass, field

from classes.characters.Special import STATS
from classes.combat import Rules
from classes.combat.Rules import Bonus

INDIVIDUAL = "individual"
GROUP = "group"
OPPOSED = "opposed"
PASSIVE = "passive"
KINDS = [INDIVIDUAL, GROUP, OPPOSED]

PUBLIC = "public"
HIDDEN_DC = "hidden_dc"
SECRET = "secret"
VISIBILITIES = [PUBLIC, HIDDEN_DC, SECRET]

OPEN = "open"
CLOSED = "closed"

CRIT = "crit"
STRONG = "strong"
SUCCESS = "success"
FAILURE = "failure"
BAD = "bad"
FUMBLE = "fumble"
# An opposed roll between characters has no DC; until both sides rolled it only says it was rolled.
ROLLED = "rolled"
SUCCESSES = {CRIT, STRONG, SUCCESS}
OUTCOME_LABELS = {CRIT : "💥 Critical success", STRONG : "🌟 Strong success", SUCCESS : "✅ Success",
                  FAILURE : "❌ Failure", BAD : "💢 Bad failure", FUMBLE : "💀 Fumble", ROLLED : "🎲 Rolled"}

DCS = {"easy" : 8, "average" : 12, "hard" : 15, "very hard" : 18, "heroic" : 22}
DC_MIN = 1
DC_MAX = 40
MODIFIER_LIMIT = 20
HELP_BONUS = 2
STRONG_MARGIN = Rules.STRONG_MARGIN
DEFAULT_HOURS = 24
MAX_HOURS = 168


# ============================================================
def parse_dc(text) -> int | None :
	"""A DC typed as a number (1 to 40) or a name (easy, average, hard, very hard, heroic)."""
	if text is None :
		return None
	if isinstance(text, int) :
		return text if DC_MIN <= text <= DC_MAX else None
	word = " ".join(str(text).replace("_", " ").replace("-", " ").lower().split())
	if word.replace(" ", "") == "veryhard" :
		word = "very hard"
	if word in DCS :
		return DCS[word]
	try :
		value = int(word)
	except ValueError :
		return None
	return value if DC_MIN <= value <= DC_MAX else None


# ============================================================
def dc_text(dc: int | None, hidden: bool = False) -> str :
	"""`DC 15 (Hard)`, or `DC ?` when it is hidden."""
	if hidden or dc is None :
		return "DC ?"
	names = [name.capitalize() for name, value in DCS.items() if value == dc]
	return f"DC {dc} ({names[0]})" if names else f"DC {dc}"


@dataclass
class CheckResult :
	natural: int
	rolls: list[int]
	bonuses: list[Bonus]
	total: int
	dc: int | None
	outcome: str
	confirm: int | None = None
	notes: list[str] = field(default_factory=list)

	# ============================================================
	@property
	def success(self) -> bool :
		return self.outcome in SUCCESSES

	# ============================================================
	@property
	def modifier(self) -> int :
		return sum(bonus.value for bonus in self.bonuses)

	# ============================================================
	def breakdown(self) -> str :
		"""`17 (14 +3)`"""
		return f"{self.total} ({self.natural} {self.modifier:+d})"


# ============================================================
def outcome_of(natural_fumble: bool, crit: bool, total: int, dc: int | None) -> str :
	if natural_fumble :
		return FUMBLE
	if crit :
		return CRIT
	if dc is None :
		return ROLLED
	if total >= dc + STRONG_MARGIN :
		return STRONG
	if total >= dc :
		return SUCCESS
	if total <= dc - STRONG_MARGIN :
		return BAD
	return FAILURE


# ============================================================
def bonuses_for(stats: dict, stat: str, base: int = 5, modifier: int = 0, extras: list[Bonus] | None = None) -> list[
	Bonus] :
	"""The parts of a check's modifier: the stat, the check's own modifier and anything extra (help, weather)."""
	value = Rules.stat(stats, stat)
	bonuses = [Bonus(f"{Rules.STAT_SHORT.get(stat, stat[:3].upper())} {value}", Rules.modifier(value, base))]
	if modifier :
		bonuses.append(Bonus("Check", modifier))
	bonuses.extend(extras or [])
	return bonuses


# ============================================================
def roll(stats: dict, stat: str, dc: int | None, base: int = 5, modifier: int = 0, extras: list[Bonus] | None = None,
         rng: random.Random | None = None) -> CheckResult :
	"""Rolls a check for a character's stats ({stat: value}); dc None is an opposed roll between characters."""
	luck = Rules.stat(stats, "luck")
	bonuses = bonuses_for(stats, stat, base, modifier, extras)
	attack = Rules.roll_attack(bonuses, dc if dc is not None else 0, crit_from=Rules.crit_min(luck),
	                           fumble_to=Rules.fumble_max(luck), confirm_crits=luck <= 0, rng=rng)
	result = CheckResult(natural=attack.natural, rolls=attack.rolls, bonuses=bonuses, total=attack.total, dc=dc,
	                     outcome=outcome_of(attack.fumble, attack.crit, attack.total, dc), confirm=attack.confirm)
	if attack.confirm is not None and not attack.crit :
		result.notes.append(f"crit not confirmed ({attack.confirm})")
	return result


# ============================================================
def npc_roll(bonus: int, rng: random.Random | None = None) -> tuple[int, int] :
	"""An NPC's side of an opposed check: the natural d20 and the total."""
	natural = (rng or random).randint(1, 20)
	return natural, natural + bonus


# ============================================================
def opposed_winner(first: CheckResult, second: CheckResult) -> int :
	"""1 or 2. A crit beats anything but a crit, a fumble loses to anything but a fumble, and otherwise the higher
	total wins. A tie goes to the defender (side 2)."""
	if (first.outcome == CRIT) != (second.outcome == CRIT) :
		return 1 if first.outcome == CRIT else 2
	if (first.outcome == FUMBLE) != (second.outcome == FUMBLE) :
		return 2 if first.outcome == FUMBLE else 1
	return 1 if first.total > second.total else 2


# ============================================================
def group_passed(outcomes: list[str]) -> bool | None :
	"""A group check succeeds when at least half the rollers succeeded; None when nobody rolled."""
	if not outcomes :
		return None
	return sum(outcome in SUCCESSES for outcome in outcomes) * 2 >= len(outcomes)


# ============================================================
def stats_of(character) -> dict :
	"""A character's SPECIAL as {stat: value}."""
	return {stat : int(getattr(character, stat, 0) or 0) for stat in STATS}


# ============================================================
def may_roll(allowed: dict | None, uid: int, role_ids: list[int]) -> bool :
	"""Whether a member may roll on a check limited to a role or a member (either one is enough)."""
	allowed = allowed or {}
	role, member = allowed.get("role"), allowed.get("member")
	if not role and not member :
		return True
	return (member is not None and int(member) == uid) or (role is not None and int(role) in role_ids)


# ============================================================
def take_help(helps: list[dict], target_uid: int) -> tuple[list[dict], dict | None] :
	"""Uses up the first unused help given to a member. Returns the updated list and the help (or None)."""
	updated = [dict(help_) for help_ in helps or []]
	for help_ in updated :
		if not help_.get("used") and int(help_.get("target_uid", 0)) == target_uid :
			help_["used"] = True
			return updated, help_
	return updated, None


# ============================================================
def help_problem(helps: list[dict], helper_uid: int, helper_character_id: int, target_uid: int) -> str | None :
	"""Why a character can't help on this check, or None."""
	if target_uid == helper_uid :
		return "You can't help yourself; pick another member."
	if any(int(help_.get("helper_character_id", 0)) == helper_character_id for help_ in helps or []) :
		return "That character already helped on this check."
	return None
