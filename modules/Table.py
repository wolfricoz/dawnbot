"""Roll tables: loot, encounters, names, plot hooks. Staff (Manage Messages) make and import them; anyone rolls.

Entries are pasted one per line: `01-05: text` for a table rolled over ranges, `3x text` (or plain text) for one rolled
by weight. `{2d6}` in an entry is rolled when it comes up and `[[Other table]]` rolls that table in its place. Actions
after the text (`| item: Arming Sword`, `| currency: 2d6`, `| xp: 50`, `| npc: 1d4 Grey Wolf`) put Grant and Start
fight buttons on the roll's card. The rules live in classes/tables/Tables.py; see design/roleplay-tools.md, section 9.
"""
import io
import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.combat.AutoComplete import AutoComplete
from classes.tables import TablePacks, Tables
from classes.tables.TableFlow import EVERYONE, STAFF, TableFlow
from database.database import RollTables
from database.transactions.RollTableTransactions import RollTableTransactions
from views.buttons.Confirm import ask
from views.combat.Pickers import reply

VISIBILITY_CHOICES = [Choice(name="Everyone can see and roll it", value=EVERYONE),
                      Choice(name="Only staff can see and roll it", value=STAFF)]
FILE_LIMIT = 100_000
MODAL_LIMIT = 4000
DESCRIPTION_LIMIT = 1000
FORMAT_HELP = ("One entry per line: `01-05: text` (ranges) or `3x text` / `text` (weights). `{2d6}` rolls dice, "
               "`[[Table]]` rolls another table, and `| item: Name`, `| currency: 2d6`, `| xp: 50`, `| npc: 1d4 Name` "
               "add rewards and NPCs.")


# ============================================================
async def table_autocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	return [Choice(name=table.name[:100], value=table.name[:100])
	        for table in RollTableTransactions().get_all(interaction.guild_id)
	        if TableFlow.visible(table, interaction.user) and current.lower() in table.name.lower()][:25]


# ============================================================
async def pack_autocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	return [Choice(name=title[:100], value=name) for name, title in TablePacks.available()
	        if current.lower() in name or current.lower() in title.lower()][:25]


# ============================================================
async def read_file(attachment: discord.Attachment) -> tuple[str | None, str | None] :
	"""The text of an uploaded .txt file, or None and why it can't be used."""
	if attachment.size > FILE_LIMIT :
		return None, f"The file is too big; keep it under {FILE_LIMIT // 1000} KB."
	try :
		data = await attachment.read()
		return data.decode("utf-8-sig"), None
	except (discord.HTTPException, UnicodeDecodeError) :
		return None, "I couldn't read that file; upload plain text (UTF-8)."


# ============================================================
def as_file(text: str, name: str) -> discord.File :
	safe = "".join(character if character.isalnum() or character in "-_" else "_" for character in name)[:60]
	return discord.File(io.BytesIO(text.encode("utf-8")), filename=f"{safe or 'table'}.txt")


class EntriesForm(discord.ui.Modal) :
	"""The description and entries of a table."""

	def __init__(self, title: str, on_submit, description: str | None = None, entries: str | None = None) :
		super().__init__(title=title[:45])
		self.handler = on_submit
		self.description = discord.ui.TextInput(label="Description (optional)", style=discord.TextStyle.paragraph,
		                                        required=False, max_length=DESCRIPTION_LIMIT, default=description)
		self.entries = discord.ui.TextInput(label="Entries, one per line", style=discord.TextStyle.paragraph,
		                                    max_length=MODAL_LIMIT, default=entries,
		                                    placeholder="01-10: A few coins | currency: 2d6\n11-20: [[Trinkets]]")
		self.add_item(self.description)
		self.add_item(self.entries)

	# ============================================================
	async def on_submit(self, interaction: discord.Interaction) :
		await self.handler(interaction, self.description.value, self.entries.value)


@app_commands.guild_only()
class Table(commands.GroupCog, name="Table", group_name="table") :
	"""Roll tables for loot, encounters, names and plot hooks; staff make them, anyone rolls."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	async def _problems(self, interaction: discord.Interaction, parsed: Tables.Parsed, text: str) -> None :
		"""Tells staff what is wrong and gives their text back as a file, so nothing they typed is lost."""
		errors = "\n".join(f"- {error}" for error in parsed.errors[:15])
		more = f"\n…and {len(parsed.errors) - 15} more." if len(parsed.errors) > 15 else ""
		message = f"The table wasn't saved:\n{errors}{more}\n\n{FORMAT_HELP}\nYour text is attached."
		if interaction.response.is_done() :
			await interaction.followup.send(message[:2000], file=as_file(text, "entries"), ephemeral=True)
		else :
			await interaction.response.send_message(message[:2000], file=as_file(text, "entries"), ephemeral=True)

	# ============================================================
	def _saved_text(self, guild_id: int, table: RollTables, entries, verb: str) -> str :
		missing = TablePacks.missing_references(guild_id, entries)
		text = f"{verb} **{table.name}**: {len(entries)} entries, rolled on " \
		       f"{'weights' if table.dice == Tables.WEIGHTS else table.dice}."
		if missing :
			text += f"\n⚠️ This server has no {', '.join(missing)}; those actions are skipped until they exist."
		return text

	# ============================================================
	@app_commands.command(name="create", description="Creates a roll table")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.choices(visibility=VISIBILITY_CHOICES)
	@app_commands.describe(name="The table's name, used to roll it and in [[name]]",
	                       luck="Rolling as a character shifts the roll by 2 x their Luck modifier toward the end",
	                       visibility="Who can see and roll it (default everyone)",
	                       file="A .txt file with the entries, for tables too long for the form")
	async def create(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 100], luck: bool = False,
	                 visibility: Choice[str] = None, file: discord.Attachment = None) :
		"""
		Creates a table. Without a file, a form asks for the description and the entries (up to 4000 characters).

		Entries go one per line:
		- `01-05: A rusty key` gives an entry a range; the table rolls 1dN up to the highest number. Ranges must cover
		  every number without overlapping.
		- `3x A rusty key` gives it a weight; plain lines weigh 1. Ranges and weights can't be mixed.
		- `{2d6}` is rolled when the entry comes up; `[[Other table]]` rolls that table in its place (3 deep at most).
		- `| item: Arming Sword`, `| currency: 2d6`, `| xp: 50` and `| npc: 1d4 Grey Wolf` after the text add actions:
		  staff press **Grant** to give the rewards to a character, and **Start fight** opens a fight with the NPCs.
		- Lines starting with `#` are skipped.

		Luck-touched tables (`luck`) put the best results at the high end: rolling as a character moves the roll by
		twice their Luck modifier.

		**Permissions:**
		- `Manage Messages`
		"""
		guild_id = interaction.guild_id
		if RollTableTransactions().find(guild_id, name) is not None :
			return await reply(interaction, f"There already is a table called {name}; use /table edit.")
		visibility_value = visibility.value if visibility else EVERYONE

		async def save(save_interaction: discord.Interaction, description: str | None, text: str) :
			parsed = Tables.parse(text)
			if parsed.errors :
				return await self._problems(save_interaction, parsed, text)
			table = RollTableTransactions().add(guild_id, name.strip(), parsed.entries,
			                                    description=(description or "").strip() or None, dice=parsed.dice,
			                                    luck=luck, visibility=visibility_value,
			                                    creator_uid=save_interaction.user.id)
			if table is None :
				return await reply(save_interaction, f"There already is a table called {name}.")
			logging.info(f"{save_interaction.user.name} created table {table.id} in {save_interaction.guild.name}")
			await reply(save_interaction, self._saved_text(guild_id, table, parsed.entries, "Created"))

		if file is not None :
			text, problem = await read_file(file)
			if problem :
				return await reply(interaction, problem)
			return await save(interaction, None, text)
		await interaction.response.send_modal(EntriesForm(f"New table: {name}", save))

	# ============================================================
	@app_commands.command(name="edit", description="Changes a roll table")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(table=table_autocomplete)
	@app_commands.choices(visibility=VISIBILITY_CHOICES)
	@app_commands.describe(table="The table to change",
	                       name="A new name",
	                       luck="Whether rolling as a character shifts the roll by their Luck",
	                       visibility="Who can see and roll it",
	                       file="A .txt file whose entries replace the table's (skips the form)")
	async def edit(self, interaction: discord.Interaction, table: str, name: app_commands.Range[str, 1, 100] = None,
	               luck: bool = None, visibility: Choice[str] = None, file: discord.Attachment = None) :
		"""
		Opens the table's description and entries in a form to change them, and applies the options. A table whose
		entries don't fit the form (4000 characters) can be changed with a file: get it with /table export, change it
		and upload it here.

		**Permissions:**
		- `Manage Messages`
		"""
		guild_id = interaction.guild_id
		record = RollTableTransactions().find(guild_id, table)
		if record is None :
			return await reply(interaction, f"There is no table called {table}.")
		if name and name.strip().lower() != record.name.lower() and RollTableTransactions().find(guild_id, name) :
			return await reply(interaction, f"There already is a table called {name}.")
		changes = {key : value for key, value in (("name", name.strip() if name else None), ("luck", luck),
		                                          ("visibility", visibility.value if visibility else None))
		           if value is not None}

		async def save(save_interaction: discord.Interaction, description: str | None, text: str,
		               keep_description: bool = False) :
			parsed = Tables.parse(text)
			if parsed.errors :
				return await self._problems(save_interaction, parsed, text)
			fields = dict(changes, dice=parsed.dice)
			if not keep_description :
				fields["description"] = (description or "").strip() or None
			updated = RollTableTransactions().update(record.id, entries=parsed.entries, **fields)
			await reply(save_interaction, self._saved_text(guild_id, updated, parsed.entries, "Saved"))

		if file is not None :
			text, problem = await read_file(file)
			if problem :
				return await reply(interaction, problem)
			return await save(interaction, None, text, keep_description=True)
		current = Tables.export(RollTableTransactions().entries(record.id), record.dice)
		if len(current) > MODAL_LIMIT :
			if changes :
				RollTableTransactions().update(record.id, **changes)
			return await reply(interaction, f"{'Saved the options. ' if changes else ''}The entries are too long for "
			                                f"the form; use /table export, change the file and upload it with "
			                                f"/table edit file:.")
		await interaction.response.send_modal(EntriesForm(f"Edit table: {record.name}", save, record.description,
		                                                  current))

	# ============================================================
	@app_commands.command(name="remove", description="Deletes a roll table")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(table=table_autocomplete)
	async def remove(self, interaction: discord.Interaction, table: str) :
		"""
		Deletes a table after asking. Tables that roll it with [[name]] show its name instead from then on.

		**Permissions:**
		- `Manage Messages`
		"""
		record = RollTableTransactions().find(interaction.guild_id, table)
		if record is None :
			return await reply(interaction, f"There is no table called {table}.")
		if not await ask(interaction, f"Delete the table **{record.name}**? This can't be undone.", "Delete") :
			return await reply(interaction, "Nothing was deleted.")
		RollTableTransactions().delete(record.id)
		await reply(interaction, f"Deleted **{record.name}**.")

	# ============================================================
	@app_commands.command(name="list", description="Lists the server's roll tables")
	async def list_tables(self, interaction: discord.Interaction) :
		"""
		Lists the tables you can roll, with how many entries each has. Staff also see staff-only tables (🔒).
		"""
		tables = [table for table in RollTableTransactions().get_all(interaction.guild_id)
		          if TableFlow.visible(table, interaction.user)]
		if not tables :
			return await reply(interaction, "This server has no roll tables yet. Staff can add them with /table create "
			                                "or /table import.")
		lines = []
		for table in tables :
			count = len(RollTableTransactions().entries(table.id))
			marks = ("🔒 " if table.visibility == STAFF else "") + ("🍀 " if table.luck else "")
			description = f" · {table.description[:80]}" if table.description else ""
			lines.append(f"{marks}**{table.name}** ({count} entries){description}")
		await self._send_lines(interaction, lines)

	# ============================================================
	async def _send_lines(self, interaction: discord.Interaction, lines: list[str]) -> None :
		chunks, current = [], ""
		for line in lines :
			if len(current) + len(line) + 1 > 1900 :
				chunks.append(current)
				current = ""
			current += line + "\n"
		chunks.append(current)
		for chunk in chunks[:10] :
			await reply(interaction, chunk)

	# ============================================================
	@app_commands.command(name="view", description="Shows a roll table's entries")
	@app_commands.autocomplete(table=table_autocomplete)
	async def view(self, interaction: discord.Interaction, table: str) :
		"""
		Shows a table's description and entries, written the way /table create reads them.
		"""
		record = RollTableTransactions().find(interaction.guild_id, table)
		if record is None or not TableFlow.visible(record, interaction.user) :
			return await reply(interaction, f"There is no table called {table}.")
		entries = RollTableTransactions().entries(record.id)
		dice = "weights" if record.dice == Tables.WEIGHTS else record.dice
		head = f"**{record.name}** · rolled on {dice}{' · Luck-touched 🍀' if record.luck else ''}"
		if record.description :
			head += f"\n{record.description}"
		lines = [head] + [f"`{line}`" for line in Tables.export(entries, record.dice).splitlines()]
		await self._send_lines(interaction, lines)

	# ============================================================
	@app_commands.command(name="roll", description="Rolls on a table")
	@app_commands.autocomplete(table=table_autocomplete, character=AutoComplete().approved_character)
	@app_commands.describe(table="The table to roll",
	                       character="Roll as one of your characters (Luck counts on Luck-touched tables)",
	                       secret="Only you see the result, with a button to show it")
	async def roll(self, interaction: discord.Interaction, table: str, character: str = None, secret: bool = False) :
		"""
		Rolls on a table and posts the result. Rewards in the result get a **Grant** button (staff give them to a
		character) and NPCs a **Start fight** button, which opens a fight with them from the bestiary. A secret roll
		only shows you the result, and is copied to the GM roll log when the server has one.
		"""
		await TableFlow.roll(interaction, table, character, secret)

	# ============================================================
	@app_commands.command(name="import", description="Copies a table pack into this server")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(pack=pack_autocomplete)
	@app_commands.describe(pack="The pack to copy, like fantasy")
	async def import_pack(self, interaction: discord.Interaction, pack: str) :
		"""
		Copies a ready-made pack of tables into this server. Tables whose names the server already has are skipped.
		The fantasy pack's loot and encounters use the fantasy gear pack's items and bestiary; import those with
		/armory import and /bestiary import.

		**Permissions:**
		- `Manage Messages`
		"""
		try :
			added, skipped, missing = TablePacks.import_into(interaction.guild_id, pack, interaction.user.id)
		except ValueError as e :
			return await reply(interaction, str(e))
		lines = [f"Imported {len(added)} tables: {', '.join(table.name for table in added) or 'none'}."]
		if skipped :
			lines.append(f"Skipped (already here): {', '.join(skipped)}.")
		if missing :
			lines.append(f"⚠️ This server has no {', '.join(missing[:15])}"
			             f"{' and more' if len(missing) > 15 else ''}; those actions are skipped until they exist.")
		await reply(interaction, "\n".join(lines))

	# ============================================================
	@app_commands.command(name="export", description="Gives you a roll table as a text file")
	@app_commands.autocomplete(table=table_autocomplete)
	async def export(self, interaction: discord.Interaction, table: str) :
		"""
		Sends you the table's entries as a .txt file, written the way /table create reads them: a backup, a way to copy
		a table to another server, or a way to edit a long table with /table edit file:.
		"""
		record = RollTableTransactions().find(interaction.guild_id, table)
		if record is None or not TableFlow.visible(record, interaction.user) :
			return await reply(interaction, f"There is no table called {table}.")
		text = Tables.export(RollTableTransactions().entries(record.id), record.dice)
		await interaction.response.send_message(f"**{record.name}**", file=as_file(text, record.name), ephemeral=True)


async def setup(bot) :
	await bot.add_cog(Table(bot))
