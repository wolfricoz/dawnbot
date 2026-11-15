"""The buttons and menus under each interview question in DMs, for character and species interviews.

What each step offers and what a press means lives in classes/characters/Controls.py; a press is handled as if the
player had typed it. The items are dynamic (registered with bot.add_dynamic_items in setup_hook) and carry the
interview kind and step in their custom id, so they keep working after a restart and refuse once the question has
moved on.
"""
import discord

from classes.characters import Controls
from database.transactions.DraftTransactions import DraftTransactions

STYLES = {Controls.PRIMARY : discord.ButtonStyle.primary, Controls.SECONDARY : discord.ButtonStyle.secondary,
          Controls.SUCCESS : discord.ButtonStyle.success, Controls.DANGER : discord.ButtonStyle.danger}
MESSAGE_LIMIT = 2000
STALE = "That question has already been answered. Use the buttons on my newest message."


# ============================================================
def token(step: str) -> str :
	"""The step as it appears in a custom id (`field:12` has a colon, which separates the id's parts)."""
	return step.replace(":", ".")


# ============================================================
def view(draft) -> discord.ui.View | None :
	"""The components for the draft's current question, or None when it has none."""
	controls = Controls.build(draft)
	if controls is None or not (controls.menus or controls.buttons) :
		return None
	result = discord.ui.View(timeout=None)
	for row, menu in enumerate(controls.menus) :
		options = [discord.SelectOption(label=option.label, value=option.value, description=option.description,
		                                default=option.default) for option in menu.options]
		result.add_item(InterviewSelect(controls.kind, token(controls.step), menu.name, options, menu.placeholder,
		                                row=row))
	for button in controls.buttons :
		result.add_item(InterviewButton(controls.kind, token(controls.step), button.action, button.label,
		                                STYLES[button.style], row=len(controls.menus)))
	return result


# ============================================================
async def _press(interaction: discord.Interaction, kind: str, step: str, action: str | None = None,
                 menu: str | None = None, value: str | None = None) -> None :
	"""Answers the interview with what the press stands for, then sends the reply as a typed answer would get."""
	from classes.characters.CharacterFlow import CharacterFlow
	from classes.species.SpeciesFlow import SpeciesFlow
	from classes.species.SpeciesInterview import KINDS as SPECIES_KINDS

	draft = DraftTransactions().get(interaction.user.id)
	resolved = None
	if draft is not None and draft.kind == kind and token(draft.step) == step :
		resolved = Controls.resolve(draft, kind, draft.step, action, menu, value)
	if resolved is None :
		await interaction.response.edit_message(view=None)
		return await interaction.followup.send(STALE, ephemeral=True)
	text, echo = resolved
	# The pressed message keeps its question, loses its controls, and shows what was picked.
	content = interaction.message.content or ""
	if len(content) + len(echo) + 6 <= MESSAGE_LIMIT :
		content += f"\n-# → {echo}"
	await interaction.response.edit_message(content=content, view=None)
	if draft.kind in SPECIES_KINDS :
		await SpeciesFlow.answer_text(interaction.client, interaction.user, draft, text, interaction.message.id)
	else :
		await CharacterFlow.answer_text(interaction.client, interaction.user, draft, text, interaction.message.id)


class InterviewButton(discord.ui.DynamicItem[discord.ui.Button],
                      template=r"iv:(?P<kind>[a-z_]+):(?P<step>[\w.]+):(?P<action>[a-z_]+)") :

	def __init__(self, kind: str, step: str, action: str, label: str = "-",
	             style: discord.ButtonStyle = discord.ButtonStyle.secondary, row: int | None = None) :
		super().__init__(discord.ui.Button(label=label, style=style, custom_id=f"iv:{kind}:{step}:{action}"), row=row)
		self.kind, self.step, self.action = kind, step, action

	# ============================================================
	@classmethod
	async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match) :
		return cls(match["kind"], match["step"], match["action"])

	# ============================================================
	async def callback(self, interaction: discord.Interaction) :
		await _press(interaction, self.kind, self.step, action=self.action)


class InterviewSelect(discord.ui.DynamicItem[discord.ui.Select],
                      template=r"ivm:(?P<kind>[a-z_]+):(?P<step>[\w.]+):(?P<menu>[a-z0-9]+)") :

	def __init__(self, kind: str, step: str, menu: str, options: list[discord.SelectOption] | None = None,
	             placeholder: str | None = None, row: int | None = None) :
		super().__init__(discord.ui.Select(custom_id=f"ivm:{kind}:{step}:{menu}", placeholder=placeholder,
		                                   options=options or [discord.SelectOption(label="-", value="-")]), row=row)
		self.kind, self.step, self.menu = kind, step, menu

	# ============================================================
	@classmethod
	async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Select, match) :
		return cls(match["kind"], match["step"], match["menu"])

	# ============================================================
	async def callback(self, interaction: discord.Interaction) :
		values = (interaction.data or {}).get("values") or []
		if not values :
			return await interaction.response.defer()
		await _press(interaction, self.kind, self.step, menu=self.menu, value=values[0])
