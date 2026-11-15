"""Small building blocks for the combat menus: a one-select view and a modal with text fields, each calling back with
what was picked or typed."""
from typing import Awaitable, Callable

import discord

OPTION_LIMIT = 25
LABEL_LIMIT = 100


class Option :
	"""One entry of a select menu."""

	def __init__(self, label: str, value: str, description: str | None = None, default: bool = False) :
		self.label = label[:LABEL_LIMIT]
		self.value = str(value)[:LABEL_LIMIT]
		self.description = description[:LABEL_LIMIT] if description else None
		self.default = default


class PickSelect(discord.ui.Select) :

	def __init__(self, options: list[Option], placeholder: str, on_pick, min_values: int = 1, max_values: int = 1) :
		options = options[:OPTION_LIMIT]
		super().__init__(placeholder=placeholder[:150], min_values=min(min_values, len(options)),
		                 max_values=max(1, min(max_values, len(options))),
		                 options=[discord.SelectOption(label=option.label, value=option.value,
		                                               description=option.description, default=option.default)
		                          for option in options])
		self.on_pick = on_pick

	# ============================================================
	async def callback(self, interaction: discord.Interaction) :
		self.view.stop()
		await self.on_pick(interaction, list(self.values))


class PickView(discord.ui.View) :
	"""A view with one select menu; only the user who opened it can use it."""

	def __init__(self, user_id: int, options: list[Option], placeholder: str,
	             on_pick: Callable[[discord.Interaction, list[str]], Awaitable[None]], min_values: int = 1,
	             max_values: int = 1, timeout: float = 300) :
		super().__init__(timeout=timeout)
		self.user_id = user_id
		self.add_item(PickSelect(options, placeholder, on_pick, min_values, max_values))

	# ============================================================
	async def interaction_check(self, interaction: discord.Interaction) -> bool :
		return interaction.user.id == self.user_id


# ============================================================
async def pick(interaction: discord.Interaction, text: str, options: list[Option], placeholder: str,
               on_pick: Callable[[discord.Interaction, list[str]], Awaitable[None]], max_values: int = 1) -> None :
	"""Shows a private select menu; tells the user when there is nothing to pick."""
	if not options :
		return await reply(interaction, "There is nothing to pick here.")
	view = PickView(interaction.user.id, options, placeholder, on_pick, max_values=max_values)
	if interaction.response.is_done() :
		await interaction.followup.send(text, view=view, ephemeral=True)
	else :
		await interaction.response.send_message(text, view=view, ephemeral=True)


# ============================================================
async def reply(interaction: discord.Interaction, text: str) -> None :
	"""Answers privately, whether or not the interaction was answered before."""
	if interaction.response.is_done() :
		await interaction.followup.send(text[:2000], ephemeral=True)
	else :
		await interaction.response.send_message(text[:2000], ephemeral=True)


class Field :
	"""One text input of a form."""

	def __init__(self, label: str, placeholder: str | None = None, default: str | None = None, long: bool = False,
	             required: bool = True, max_length: int = 200) :
		self.label = label[:45]
		self.placeholder = placeholder[:100] if placeholder else None
		self.default = default
		self.long = long
		self.required = required
		self.max_length = max_length


class Form(discord.ui.Modal) :
	"""A modal with text fields; on_submit gets the values in order."""

	def __init__(self, title: str, fields: list[Field],
	             on_submit: Callable[[discord.Interaction, list[str]], Awaitable[None]]) :
		super().__init__(title=title[:45])
		self.handler = on_submit
		self.inputs = []
		for field in fields[:5] :
			text_input = discord.ui.TextInput(label=field.label, placeholder=field.placeholder, default=field.default,
			                                  style=discord.TextStyle.paragraph if field.long else
			                                  discord.TextStyle.short,
			                                  required=field.required, max_length=field.max_length)
			self.inputs.append(text_input)
			self.add_item(text_input)

	# ============================================================
	async def on_submit(self, interaction: discord.Interaction) :
		await self.handler(interaction, [text_input.value for text_input in self.inputs])


# ============================================================
def number(text: str | None) -> int | None :
	"""A whole number typed into a form (like 5, -3 or +4), or None."""
	try :
		return int(str(text).strip().replace("+", ""))
	except (TypeError, ValueError) :
		return None
