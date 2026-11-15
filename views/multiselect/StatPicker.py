"""The SPECIAL picker in DMs: one menu per stat, a running count of points left, and Confirm / Reset / Reroll.

The rules are in classes/characters/StatPanel.py. The menus and buttons are dynamic items (registered with
bot.add_dynamic_items in setup_hook) that find the player's draft by who pressed them, so they keep working after a
restart. Seven menus need more rows than a classic message has, so the picker is a components v2 layout.
"""
import logging

import discord

from classes.characters import StatPanel
from classes.characters.Special import ROLLED, STATS, Special
from database.transactions.DraftTransactions import DraftTransactions

COLOUR = discord.Colour.blurple()


# ============================================================
def build(draft, note: str | None = None) -> discord.ui.LayoutView :
	"""The picker for the draft as it is now; note is shown under the heading, for example why a pick was refused."""
	state = StatPanel.state(draft)
	text = StatPanel.header(draft)
	if note :
		text += f"\n**{note}**"
	container = discord.ui.Container(accent_colour=COLOUR)
	container.add_item(discord.ui.TextDisplay(text))
	for stat in STATS :
		options = [discord.SelectOption(label=option.label, value=option.value, description=option.description,
		                                default=option.default) for option in state.options[stat]]
		placeholder = f"{stat.capitalize()}: pick a value"
		row = discord.ui.ActionRow()
		row.add_item(StatSelect(stat, options or [discord.SelectOption(label="Nothing left to place", value="-1")],
		                        placeholder))
		container.add_item(row)
	buttons = discord.ui.ActionRow()
	buttons.add_item(StatButton("confirm", disabled=not state.complete))
	buttons.add_item(StatButton("reset"))
	if state.method == ROLLED :
		buttons.add_item(StatButton("reroll"))
	container.add_item(buttons)
	view = discord.ui.LayoutView(timeout=None)
	view.add_item(container)
	return view


# ============================================================
def closed(text: str) -> discord.ui.LayoutView :
	"""The picker once it is done with: just a line of text, no menus."""
	view = discord.ui.LayoutView(timeout=None)
	view.add_item(discord.ui.Container(discord.ui.TextDisplay(text), accent_colour=COLOUR))
	return view


# ============================================================
async def send(user: discord.abc.Messageable, draft) -> None :
	"""Sends the picker under the stats question."""
	try :
		await user.send(view=build(draft))
	except discord.HTTPException as e :
		logging.warning(f"Could not send the stat picker to {user}: {e}")


# ============================================================
async def _open_draft(interaction: discord.Interaction) :
	"""The presser's draft when it is at the stats step; otherwise closes this picker and returns None."""
	draft = DraftTransactions().get(interaction.user.id)
	if StatPanel.is_open(draft) :
		return draft
	await interaction.response.edit_message(view=closed("This picker is no longer in use."))
	return None


class StatSelect(discord.ui.DynamicItem[discord.ui.Select], template=r"stat_pick:(?P<stat>[a-z]+)") :

	def __init__(self, stat: str, options: list[discord.SelectOption] | None = None,
	             placeholder: str | None = None) :
		super().__init__(discord.ui.Select(custom_id=f"stat_pick:{stat}", placeholder=placeholder,
		                                   options=options or [discord.SelectOption(label="-", value="-1")]))
		self.stat = stat

	# ============================================================
	@classmethod
	async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Select, match) :
		return cls(match["stat"])

	# ============================================================
	async def callback(self, interaction: discord.Interaction) :
		draft = await _open_draft(interaction)
		if draft is None :
			return
		values = (interaction.data or {}).get("values") or []
		problem = StatPanel.choose(draft, self.stat, values[0]) if values and values[0] != "-1" else None
		await interaction.response.edit_message(view=build(draft, problem))


class StatButton(discord.ui.DynamicItem[discord.ui.Button], template=r"stat_btn:(?P<action>confirm|reset|reroll)") :
	LABELS = {"confirm" : ("Confirm", discord.ButtonStyle.success), "reset" : ("Reset", discord.ButtonStyle.secondary),
	          "reroll" : ("Reroll", discord.ButtonStyle.primary)}

	def __init__(self, action: str, disabled: bool = False) :
		label, style = self.LABELS[action]
		super().__init__(discord.ui.Button(label=label, style=style, custom_id=f"stat_btn:{action}",
		                                   disabled=disabled))
		self.action = action

	# ============================================================
	@classmethod
	async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match) :
		return cls(match["action"])

	# ============================================================
	async def callback(self, interaction: discord.Interaction) :
		draft = await _open_draft(interaction)
		if draft is None :
			return
		if self.action == "reset" :
			StatPanel.reset(draft)
			return await interaction.response.edit_message(view=build(draft))
		if self.action == "reroll" :
			StatPanel.reroll(draft)
			return await interaction.response.edit_message(view=build(draft))

		values = StatPanel.answer_text(draft)
		if values is None :
			return await interaction.response.edit_message(view=build(draft, "Place every value first."))
		from classes.characters.CharacterFlow import CharacterFlow
		from classes.characters.Interview import Interview

		reply = await Interview.answer(draft, values)
		if StatPanel.is_open(draft) :
			# The interview refused the values; say why and keep the picker.
			return await interaction.response.edit_message(view=build(draft, reply.text.split("\n")[0]))
		stats = draft.answers.get("stats") or {}
		await interaction.response.edit_message(view=closed(f"SPECIAL saved: {Special.summary(stats)}"))
		await CharacterFlow.deliver(interaction.client, interaction.user, reply, step_before="stats")
