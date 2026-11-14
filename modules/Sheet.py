import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.characters.Card import chunk_text
from classes.characters.Sheet import CHOICE, INFO, MAX_FIELDS, Sheet as CharacterSheet, TYPES
from classes.kernel.ServerSync import sync_server
from database.transactions.SheetFieldTransactions import SheetFieldTransactions
from views.buttons.Confirm import ask, double_confirm

TYPE_CHOICES = [Choice(name=name, value=name) for name in TYPES]


@app_commands.guild_only()
class Sheet(commands.GroupCog, name="Sheet", group_name="sheet") :
	"""The server's character sheet: the questions members answer when they create a character."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	async def _labels(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		fields = SheetFieldTransactions().get_all(interaction.guild_id)
		return [Choice(name=field.label, value=field.label) for field in fields
		        if current.lower() in field.label.lower()][:25]

	# ============================================================
	@staticmethod
	def _split_choices(choices: str | None) -> list[str] | None :
		if choices is None :
			return None
		return [choice.strip() for choice in choices.split(",") if choice.strip()]

	# ============================================================
	@app_commands.command(name="add")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.choices(type=TYPE_CHOICES)
	async def add(self, interaction: discord.Interaction, label: app_commands.Range[str, 1, 100], type: Choice[str],
	              section: app_commands.Range[str, 1, 100] = None, required: bool = False,
	              help: app_commands.Range[str, 1, 1500] = None, choices: app_commands.Range[str, 1, 1500] = None,
	              max_length: int = None, min_value: int = None, max_value: int = None,
	              position: app_commands.Range[int, 1, 100] = None) :
		"""
		Adds a question to the character sheet. Types: short (a line of text), long (paragraphs), number, choice
		(members pick one of the options you give in `choices`, separated by commas) and info (asks nothing; its
		`help` text is shown as a note before the next question). `section` is the heading the question is grouped
		under, `help` a hint shown with the question. Existing characters are asked a new required question the next
		time they are edited.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		sync_server(interaction.guild)
		options = self._split_choices(choices) if type.value == CHOICE else None
		if type.value == INFO and not help :
			return await interaction.followup.send("An info note needs its text in `help`.")
		problem = CharacterSheet.validate_definition(type.value, max_length, min_value, max_value, options)
		if problem :
			return await interaction.followup.send(problem)
		if len(SheetFieldTransactions().get_all(interaction.guild_id)) >= MAX_FIELDS :
			return await interaction.followup.send(f"A sheet can have at most {MAX_FIELDS} questions.")
		field = SheetFieldTransactions().add(interaction.guild_id, label, position, section=section, type=type.value,
		                                     required=required and type.value != INFO, help=help, choices=options,
		                                     max_length=max_length, min_value=min_value, max_value=max_value)
		if field is None :
			return await interaction.followup.send(f"The sheet already has a question called {label}.")
		logging.info(f"{interaction.user.name} added sheet question {label} in {interaction.guild.name}")
		await interaction.followup.send(f"Added {label} to the sheet at position {field.position}.")

	# ============================================================
	@app_commands.command(name="edit")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.autocomplete(label=_labels)
	async def edit(self, interaction: discord.Interaction, label: str,
	               new_label: app_commands.Range[str, 1, 100] = None, section: app_commands.Range[str, 1, 100] = None,
	               required: bool = None, help: app_commands.Range[str, 1, 1500] = None,
	               choices: app_commands.Range[str, 1, 1500] = None, max_length: int = None, min_value: int = None,
	               max_value: int = None) :
		"""
		Changes a question on the character sheet; options you leave out keep their value. The type cannot be
		changed: remove the question and add a new one instead. Answers characters already gave are kept.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		field = SheetFieldTransactions().find(interaction.guild_id, label)
		if field is None :
			return await interaction.followup.send(f"The sheet has no question called {label}.")
		options = self._split_choices(choices) if choices is not None else field.choices
		problem = CharacterSheet.validate_definition(
			field.type, max_length if max_length is not None else field.max_length,
			min_value if min_value is not None else field.min_value,
			max_value if max_value is not None else field.max_value, options)
		if problem :
			return await interaction.followup.send(problem)
		if new_label is not None and new_label.lower() != field.label.lower() \
				and SheetFieldTransactions().find(interaction.guild_id, new_label) is not None :
			return await interaction.followup.send(f"The sheet already has a question called {new_label}.")
		updates = {"label" : new_label, "section" : section, "required" : required, "help" : help,
		           "choices" : options if choices is not None else None, "max_length" : max_length,
		           "min_value" : min_value, "max_value" : max_value}
		if field.type == INFO :
			updates["required"] = None
		SheetFieldTransactions().update(field.id, **{key : value for key, value in updates.items()
		                                             if value is not None})
		await interaction.followup.send(f"Updated {new_label or field.label}.")

	# ============================================================
	@app_commands.command(name="remove")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.autocomplete(label=_labels)
	async def remove(self, interaction: discord.Interaction, label: str) :
		"""
		Removes a question from the character sheet. Answers characters already gave stay on their sheets, as
		fields of their own.

		**Permissions:**
		- `Manage Server`
		"""
		field = SheetFieldTransactions().find(interaction.guild_id, label)
		if field is None :
			return await interaction.response.send_message(f"The sheet has no question called {label}.",
			                                               ephemeral=True)
		if not await ask(interaction, f"Remove **{field.label}** from the character sheet?", "Remove") :
			return
		SheetFieldTransactions().remove(interaction.guild_id, field.label)
		logging.info(f"{interaction.user.name} removed sheet question {field.label} in {interaction.guild.name}")
		await interaction.followup.send(f"Removed {field.label} from the sheet.", ephemeral=True)

	# ============================================================
	@app_commands.command(name="move")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.autocomplete(label=_labels)
	async def move(self, interaction: discord.Interaction, label: str, position: app_commands.Range[int, 1, 100]) :
		"""
		Moves a question to another position on the sheet; position 1 is asked first.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		if not SheetFieldTransactions().move(interaction.guild_id, label, position) :
			return await interaction.followup.send(f"The sheet has no question called {label}.")
		field = SheetFieldTransactions().find(interaction.guild_id, label)
		await interaction.followup.send(f"Moved {field.label} to position {field.position}.")

	# ============================================================
	@app_commands.command(name="view")
	async def view(self, interaction: discord.Interaction) :
		"""
		Shows the server's character sheet: every question in the order it is asked, with its type and limits.
		"""
		await interaction.response.defer(ephemeral=True)
		fields = SheetFieldTransactions().get_all(interaction.guild_id)
		if not fields :
			return await interaction.followup.send(
				"The sheet is empty: members are only asked for a name, prefix or suffix, picture and stats.")
		lines, section = [], None
		for field in fields :
			if field.section != section :
				section = field.section
				lines.append(f"\n**__{section or 'No section'}__**")
			details = [field.type]
			if field.type != INFO :
				details.append("required" if field.required else "optional")
			if field.type == CHOICE :
				details.append(" / ".join(field.choices or []))
			if field.max_length :
				details.append(f"max {field.max_length} characters")
			if field.min_value is not None :
				details.append(f"min {field.min_value}")
			if field.max_value is not None :
				details.append(f"max {field.max_value}")
			lines.append(f"{field.position}. **{field.label}** ({', '.join(details)})")
			if field.help :
				lines.append(f"-# {' '.join(field.help.split())[:300]}")
		for chunk in chunk_text("\n".join(lines).strip(), 4000) :
			await interaction.followup.send(embed=discord.Embed(title="Character sheet", description=chunk),
			                                ephemeral=True)

	# ============================================================
	@app_commands.command(name="reset")
	@app_commands.checks.has_permissions(manage_guild=True)
	async def reset(self, interaction: discord.Interaction) :
		"""
		Replaces the whole character sheet with the default one. Answers characters already gave stay on their
		sheets, as fields of their own.

		**Permissions:**
		- `Manage Server`
		"""
		if not await double_confirm(interaction,
		                            "Replace this server's character sheet with the default one?",
		                            "Every question you added or changed will be gone. Are you sure?") :
			return
		sync_server(interaction.guild)
		CharacterSheet.reset(interaction.guild_id)
		logging.info(f"{interaction.user.name} reset the sheet of {interaction.guild.name}")
		await interaction.followup.send("The character sheet is back to the default.", ephemeral=True)


async def setup(bot) :
	await bot.add_cog(Sheet(bot))
