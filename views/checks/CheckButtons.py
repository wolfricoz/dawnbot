"""The buttons under a check's card. They carry the check's id in their custom id, so they keep working after a restart
(registered with bot.add_dynamic_items in setup_hook). Also the short-lived views for helping and revealing."""
from typing import Awaitable, Callable

import discord

from classes.checks.Checks import CLOSED, SECRET
from database.database import Checks as CheckRecord

ROLL = "roll"
HELP = "help"
RESULTS = "results"
CLOSE = "close"


class CheckButton(discord.ui.DynamicItem[discord.ui.Button],
                  template=r"check:(?P<check>\d+):(?P<action>roll|help|results|close)") :

	def __init__(self, check_id: int, action: str, label: str | None = None,
	             style: discord.ButtonStyle = discord.ButtonStyle.secondary, emoji: str | None = None) :
		super().__init__(discord.ui.Button(label=label or action.capitalize(), style=style, emoji=emoji,
		                                   custom_id=f"check:{check_id}:{action}"))
		self.check_id = check_id
		self.action = action

	# ============================================================
	@classmethod
	async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match) :
		return cls(int(match["check"]), match["action"])

	# ============================================================
	async def callback(self, interaction: discord.Interaction) :
		from classes.checks.CheckFlow import CheckFlow

		handlers = {ROLL : CheckFlow.start_roll, HELP : CheckFlow.start_help, RESULTS : CheckFlow.results,
		            CLOSE : CheckFlow.close}
		await handlers[self.action](interaction, self.check_id)


# ============================================================
def card_view(check: CheckRecord) -> discord.ui.View | None :
	from classes.checks.CheckCard import is_character_duel

	view = discord.ui.View(timeout=None)
	if check.state == CLOSED :
		if check.visibility != SECRET :
			return None
		view.add_item(CheckButton(check.id, RESULTS, "Results", emoji="📋"))
		return view
	view.add_item(CheckButton(check.id, ROLL, "Roll", discord.ButtonStyle.primary, "🎲"))
	if not is_character_duel(check) :
		view.add_item(CheckButton(check.id, HELP, "Help", emoji="🤝"))
	if check.visibility == SECRET :
		view.add_item(CheckButton(check.id, RESULTS, "Results", emoji="📋"))
	view.add_item(CheckButton(check.id, CLOSE, "Close", discord.ButtonStyle.danger))
	return view


class HelpTargetView(discord.ui.View) :
	"""Picks the member a character helps."""

	def __init__(self, user_id: int, on_pick: Callable[[discord.Interaction, discord.abc.User], Awaitable[None]]) :
		super().__init__(timeout=300)
		self.user_id = user_id
		self.on_pick = on_pick
		select = discord.ui.UserSelect(placeholder="Pick the member you help")
		select.callback = self.picked
		self.select = select
		self.add_item(select)

	# ============================================================
	async def interaction_check(self, interaction: discord.Interaction) -> bool :
		return interaction.user.id == self.user_id

	# ============================================================
	async def picked(self, interaction: discord.Interaction) :
		self.stop()
		await self.on_pick(interaction, self.select.values[0])


class RevealView(discord.ui.View) :
	"""The Reveal button under a passive check's private results."""

	def __init__(self, user_id: int, on_press: Callable[[discord.Interaction], Awaitable[None]]) :
		# Private messages can only be answered for 15 minutes.
		super().__init__(timeout=840)
		self.user_id = user_id
		self.on_press = on_press

	# ============================================================
	async def interaction_check(self, interaction: discord.Interaction) -> bool :
		return interaction.user.id == self.user_id

	# ============================================================
	@discord.ui.button(label="Reveal to those who passed", style=discord.ButtonStyle.primary, emoji="👁️")
	async def reveal(self, interaction: discord.Interaction, button: discord.ui.Button) :
		await self.on_press(interaction)
