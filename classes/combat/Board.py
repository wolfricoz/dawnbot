"""The board: the pinned message in a fight's thread that shows the sides, HP, AP, AC, conditions, whose turn it is
and the timer."""
import discord

from classes.combat import Conditions as C, Passives
from classes.combat.Engine import Engine
from classes.combat.State import ACTIVE, ASYNC, Combatant, DEAD, DOWNED, DYING, ENDED, FLED, Fight, PAUSED, PENDING, \
	REMOVED, SETUP, STABLE

FIELD_LIMIT = 1024
BAR_WIDTH = 8
STATE_ICONS = {DOWNED : "💀", DYING : "⚰️", STABLE : "🩹", FLED : "🏃", DEAD : "✝️", REMOVED : "➖"}
COLORS = {PENDING : discord.Color.light_grey(), SETUP : discord.Color.blurple(), ACTIVE : discord.Color.red(),
          PAUSED : discord.Color.orange(), ENDED : discord.Color.dark_grey()}


# ============================================================
def hp_bar(hp: int, hp_max: int) -> str :
	if hp_max <= 0 :
		return ""
	filled = max(0, min(BAR_WIDTH, round(BAR_WIDTH * hp / hp_max)))
	if hp > 0 and filled == 0 :
		filled = 1
	return "▰" * filled + "▱" * (BAR_WIDTH - filled)


# ============================================================
def combatant_line(combatant: Combatant, fight: Fight, engine: Engine) -> str :
	if combatant.state in STATE_ICONS :
		icon = STATE_ICONS[combatant.state]
	elif fight.state == ACTIVE and combatant in engine.actors() :
		icon = "⏳"
	elif fight.state == ACTIVE and combatant.acted :
		icon = "✅"
	else :
		icon = "▫️"
	who = f"**{combatant.name}**"
	if combatant.stats.get("legendary") :
		who = f"🌟 {who}"
	line = f"{icon} {who} ❤️ {combatant.hp}/{combatant.hp_max} {hp_bar(combatant.hp, combatant.hp_max)}"
	if combatant.in_fight :
		line += f" · AC {engine.effective_ac(combatant)}"
		if fight.state == ACTIVE and combatant in engine.actors() :
			line += f" · AP {combatant.ap}/{combatant.ap_max}"
	notes = [C.text(combatant.conditions)] + passive_notes(combatant)
	notes = [note for note in notes if note]
	if notes :
		line += f"\n-# {' · '.join(notes)}"
	return line


# ============================================================
def passive_notes(combatant: Combatant) -> list[str] :
	"""Stacks gained and last stands used, like `⚡ Spellfed 3/5`."""
	notes = []
	state = combatant.stats.get("passive_state") or {}
	for passive in combatant.passives :
		kept = state.get(str(passive["id"])) or {}
		tier = Passives.index(passive["tier"])
		if passive.get("type") == Passives.STACKS and kept.get("stacks") :
			notes.append(f"⚡ {passive['name']} {kept['stacks']}/{Passives.MAX_STACKS[tier]}")
		elif passive.get("trigger") == Passives.LAST_STAND and kept.get("uses") :
			left = Passives.LAST_STAND_USES[tier] - int(kept["uses"])
			notes.append(f"🛡️ {passive['name']}: {left} left")
	return notes


# ============================================================
def status_text(fight: Fight, engine: Engine) -> str :
	if fight.state == PENDING :
		challenge = fight.challenge or {}
		return f"⚔️ <@{challenge.get('challenger_uid')}> challenged <@{challenge.get('target_uid')}>. Waiting for an answer."
	if fight.state == SETUP :
		return "Getting ready. Press **Join** to bring a character; the GM starts the fight from **GM**."
	if fight.state == PAUSED :
		return f"⏸️ Paused in round {fight.round}."
	if fight.state == ENDED :
		side = fight.side(fight.winner_side_id)
		return f"🏁 The fight is over after {fight.round} round{'s' if fight.round != 1 else ''}. " \
		       + (f"**{side.name}** won." if side else "Nobody won.")
	unit = engine.unit()
	if fight.pacing == ASYNC and fight.order and fight.turn_index < len(fight.order) :
		side = fight.side(fight.order[fight.turn_index])
		who = side.name if side else "?"
	else :
		who = unit[0].name if unit else "?"
	text = f"**Round {fight.round}** · {who}'s turn"
	if fight.deadline is not None :
		text += f" · ends <t:{int(fight.deadline.timestamp())}:R>"
	return text


# ============================================================
def side_text(lines: list[str]) -> str :
	"""The lines joined, cut short with a count of the rest when they don't fit in a field."""
	text, shown = "", 0
	for line in lines :
		candidate = f"{text}\n{line}" if text else line
		if len(candidate) > FIELD_LIMIT - 30 :
			break
		text, shown = candidate, shown + 1
	if shown < len(lines) :
		text += f"\n… and {len(lines) - shown} more"
	return text or "Nobody yet."


# ============================================================
def embed(fight: Fight, engine: Engine) -> discord.Embed :
	result = discord.Embed(title=f"⚔️ {fight.title}"[:256], color=COLORS.get(fight.state, discord.Color.red()))
	gms = ", ".join(f"<@{uid}>" for uid in [fight.gm_uid] + list(fight.co_gms or []))
	result.description = f"{status_text(fight, engine)}\nGM: {gms}"
	for side in fight.sides :
		members = fight.members(side.id, include_out=True)
		lines = [combatant_line(combatant, fight, engine) for combatant in members]
		marker = " 🏆" if fight.state == ENDED and fight.winner_side_id == side.id else ""
		result.add_field(name=f"{side.name}{marker}"[:256], value=side_text(lines), inline=False)
	if fight.pending :
		lines = [f"#{entry['number']}: {entry['text'][:80]}" for entry in fight.pending]
		result.add_field(name="Waiting for the GM", value=side_text(lines), inline=False)
	footer = f"{'Async' if fight.pacing == ASYNC else 'Live'} · {'PvP' if fight.kind == 'pvp' else 'PvE'}"
	if fight.lethal :
		footer += " · ☠️ Lethal"
	if fight.late_join and fight.state in (ACTIVE, PAUSED) :
		footer += " · late joins allowed"
	result.set_footer(text=f"{footer} · fight {fight.id}")
	return result
