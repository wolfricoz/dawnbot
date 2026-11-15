"""The card a check is posted as: what is being checked, who rolled and how it went, as far as its visibility allows."""
import discord

from classes.checks import Checks
from classes.checks.Checks import CLOSED, GROUP, HIDDEN_DC, OPPOSED, SECRET
from classes.combat import Rules
from database.database import CheckRolls, Checks as CheckRecord

OPEN_COLOUR = discord.Colour.blurple()
SUCCESS_COLOUR = discord.Colour.green()
FAILURE_COLOUR = discord.Colour.red()
CLOSED_COLOUR = discord.Colour.dark_grey()
LINES_PER_FIELD = 12
MAX_LINES = 36


# ============================================================
def stat_name(stat: str) -> str :
	return (stat or "").capitalize()


# ============================================================
def is_character_duel(check: CheckRecord) -> bool :
	"""An opposed check between two characters (rather than players against an NPC)."""
	return check.kind == OPPOSED and bool(check.opposed) and "1" in check.opposed


# ============================================================
def roll_line(roll: CheckRolls, visibility: str, show_stat: bool = False) -> str :
	"""One roll as the card shows it."""
	if visibility == SECRET :
		return f"🎲 **{roll.name}** rolled."
	stat = f" · {stat_name(roll.stat)}" if show_stat else ""
	modifier = roll.total - roll.natural
	line = f"**{roll.name}**{stat} · **{roll.total}** ({roll.natural} {modifier:+d}) · {Checks.OUTCOME_LABELS[roll.outcome]}"
	if roll.helped_by :
		line += f" · helped by {roll.helped_by}"
	if (roll.details or {}).get("rerolled") :
		line += f" · bad-luck reroll (first {roll.details['rerolled']})"
	return line


# ============================================================
def result_line(check: CheckRecord, rolls: list[CheckRolls]) -> str | None :
	"""The outcome of a closed check (or a duel where both rolled)."""
	if check.visibility == SECRET :
		return "Closed. Only the caller can see the results." if check.state == CLOSED else None
	if is_character_duel(check) :
		by_side = {roll.side : roll for roll in rolls}
		if 1 in by_side and 2 in by_side :
			winner = (check.opposed or {}).get("winner")
			if winner :
				return f"🏆 **{by_side[int(winner)].name}** wins."
		return "Closed before both sides rolled." if check.state == CLOSED else None
	if check.state != CLOSED :
		return None
	if not rolls :
		return "Closed. Nobody rolled."
	passed = sum(roll.outcome in Checks.SUCCESSES for roll in rolls)
	if check.kind == GROUP :
		verdict = "✅ The group succeeds" if Checks.group_passed([roll.outcome for roll in rolls]) else \
			"❌ The group fails"
		return f"{verdict} ({passed} of {len(rolls)} succeeded)."
	return f"{passed} of {len(rolls)} succeeded."


# ============================================================
def title(check: CheckRecord) -> str :
	if is_character_duel(check) :
		first, second = check.opposed["1"], check.opposed["2"]
		return f"⚔️ {first.get('name')} ({stat_name(first.get('stat'))}) vs {second.get('name')} " \
		       f"({stat_name(second.get('stat'))})"
	if check.kind == OPPOSED and check.opposed :
		return f"⚔️ {stat_name(check.stat)} vs {check.opposed.get('npc')}"
	kind = "Group check" if check.kind == GROUP else "check"
	return f"🎯 {stat_name(check.stat)} {kind} · {Checks.dc_text(check.dc, check.visibility != 'public')}"


# ============================================================
def description(check: CheckRecord) -> str :
	lines = []
	if check.title :
		lines.append(f"**{check.title}**")
	if check.kind == OPPOSED and check.opposed and not is_character_duel(check) :
		npc = check.opposed
		shown = check.visibility == "public"
		lines.append(f"{npc.get('npc')} rolled **{npc.get('total') if shown else '?'}**. Beat it to succeed; a tie goes "
		             f"to {npc.get('npc')}.")
	if check.kind == GROUP :
		lines.append("The group succeeds when at least half of the rollers succeed.")
	if check.modifier :
		lines.append(f"Modifier for everyone: **{check.modifier:+d}**")
	allowed = check.allowed or {}
	who = [mention for mention in (f"<@&{allowed['role']}>" if allowed.get("role") else None,
	                               f"<@{allowed['member']}>" if allowed.get("member") else None) if mention]
	if who :
		lines.append(f"Only {' or '.join(who)} can roll.")
	if check.visibility == HIDDEN_DC :
		lines.append("The DC is hidden.")
	elif check.visibility == SECRET :
		lines.append("🔒 Secret: only the caller sees the results.")
	if check.state != CLOSED :
		if is_character_duel(check) :
			lines.append("Each side presses **Roll**; the higher total wins and a tie goes to "
			             f"{check.opposed['2'].get('name')}.")
		else :
			lines.append("Press **Roll** to roll as your character. **Help** gives another member +2 on their roll.")
		if check.expires_at :
			lines.append(f"Closes <t:{int(check.expires_at.timestamp())}:R>.")
	lines.append(f"-# Called by <@{check.caller_uid}>")
	return "\n".join(lines)


# ============================================================
def colour(check: CheckRecord, rolls: list[CheckRolls]) -> discord.Colour :
	if check.state != CLOSED or check.visibility == SECRET :
		return OPEN_COLOUR if check.state != CLOSED else CLOSED_COLOUR
	if check.kind == GROUP and rolls :
		return SUCCESS_COLOUR if Checks.group_passed([roll.outcome for roll in rolls]) else FAILURE_COLOUR
	return CLOSED_COLOUR


# ============================================================
def embed(check: CheckRecord, rolls: list[CheckRolls]) -> discord.Embed :
	card = discord.Embed(title=title(check)[:256], description=description(check)[:4096], colour=colour(check, rolls))
	duel = is_character_duel(check)
	visibility = check.visibility
	if duel and check.state != CLOSED and not (check.opposed or {}).get("winner") :
		# Neither side sees the other's total before both rolled.
		visibility = SECRET
	lines = [roll_line(roll, visibility, show_stat=duel) for roll in rolls[:MAX_LINES]]
	if len(rolls) > MAX_LINES :
		lines.append(f"…and {len(rolls) - MAX_LINES} more.")
	for start in range(0, len(lines), LINES_PER_FIELD) :
		card.add_field(name="Rolls" if start == 0 else "​",
		               value="\n".join(lines[start :start + LINES_PER_FIELD])[:1024], inline=False)
	helps = [help_ for help_ in check.helps or []]
	if helps :
		help_lines = [f"🤝 {help_.get('helper_name')} helps <@{help_.get('target_uid')}>"
		              f"{' (used)' if help_.get('used') else f' (+{Checks.HELP_BONUS})'}" for help_ in helps[:15]]
		card.add_field(name="Help", value="\n".join(help_lines)[:1024], inline=False)
	result = result_line(check, rolls)
	if result :
		card.add_field(name="Result", value=result, inline=False)
	return card


# ============================================================
def results_text(check: CheckRecord, rolls: list[CheckRolls]) -> str :
	"""Everything about the rolls, for the caller (Results button)."""
	head = f"{title(check).split(' · ')[0]} · {Checks.dc_text(check.dc)}"
	if check.kind == OPPOSED and check.opposed and not is_character_duel(check) :
		head += f" (vs {check.opposed.get('npc')}: {check.opposed.get('total')})"
	if not rolls :
		return f"{head}\nNobody has rolled yet."
	lines = [roll_line(roll, "public", show_stat=is_character_duel(check)) for roll in rolls]
	passed = sum(roll.outcome in Checks.SUCCESSES for roll in rolls)
	return "\n".join([head] + lines + [f"{passed} of {len(rolls)} succeeded."])[:2000]


# ============================================================
def own_result(check: CheckRecord, name: str, result: Checks.CheckResult) -> str :
	"""What the roller is told privately."""
	if check.visibility == SECRET :
		return f"🎲 {name} rolled. Only the caller sees how it went."
	if result.outcome == Checks.ROLLED :
		return f"🎲 {name} rolled **{result.total}** ({result.natural} {result.modifier:+d}). The result shows once " \
		       f"both sides rolled."
	bonuses = Rules.bonus_text(result.bonuses)
	return f"🎲 {name}: **{result.total}** ({result.natural}; {bonuses}) · {Checks.OUTCOME_LABELS[result.outcome]}"
