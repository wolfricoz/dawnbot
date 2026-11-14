"""Game master tools: giving and taking characters' gear and currency. GMs are staff (Manage Messages)."""
import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.gear.Gear import Gear
from database.database import CharacterGear, Characters, GearItems
from database.transactions.CharacterGearTransactions import BROKEN, CharacterGearTransactions, LOST
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from modules.Currency import balance_text
from modules.Gear import entry_choices, find_entry, refresh_post, unmet_warning


@app_commands.guild_only()
@app_commands.default_permissions(manage_messages=True)
class GM(commands.GroupCog, name="GM", group_name="gm") :

	gear = app_commands.Group(name="gear", description="Give or take characters' gear")
	currency = app_commands.Group(name="currency", description="Give or take characters' currency")

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# == autocomplete ==

	# ============================================================
	async def _characters(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		member = interaction.namespace.member
		if member is None :
			return []
		return [Choice(name=character.name, value=character.name)
		        for character in CharacterTransactions().get_all(member.id, interaction.guild_id)
		        if current.lower() in character.name.lower()][:25]

	# ============================================================
	async def _catalog(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		return [Choice(name=item.name[:100], value=item.name[:100])
		        for item in GearItemTransactions().get_all(interaction.guild_id)
		        if current.lower() in item.name.lower()][:25]

	# ============================================================
	async def _owned(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		member, name = interaction.namespace.member, interaction.namespace.character
		if member is None or not name :
			return []
		character = CharacterTransactions().get(member.id, interaction.guild_id, name)
		if character is None :
			return []
		return entry_choices(CharacterGearTransactions().get_all(character.id), current)

	# == helpers ==

	# ============================================================
	async def _character(self, interaction: discord.Interaction, member: discord.Member,
	                     character: str) -> Characters | None :
		record = CharacterTransactions().get(member.id, interaction.guild_id, character)
		if record is None :
			await interaction.followup.send(f"{member.display_name} has no character called {character}.",
			                                ephemeral=True)
		return record

	# ============================================================
	async def _entry(self, interaction: discord.Interaction, member: discord.Member, character: str,
	                 item: str) -> tuple[Characters | None, CharacterGear | None] :
		record = await self._character(interaction, member, character)
		if record is None :
			return None, None
		entry = find_entry(CharacterGearTransactions().get_all(record.id), item)
		if entry is None :
			await interaction.followup.send(f"{record.name} doesn't own {item}.", ephemeral=True)
		return record, entry

	# ============================================================
	async def _mark(self, interaction: discord.Interaction, member: discord.Member, character: str, item: str,
	                status: str) -> None :
		await interaction.response.defer(ephemeral=True)
		record, entry = await self._entry(interaction, member, character, item)
		if entry is None :
			return
		_, problem = Gear.set_status(entry, status, interaction.user.id)
		if problem :
			return await interaction.followup.send(problem, ephemeral=True)
		logging.info(f"GM {interaction.user.name} marked gear {entry.id} ({entry.name}) of character {record.id} "
		             f"{status} in {interaction.guild.name}")
		await interaction.followup.send(f"{record.name}'s **{entry.name}** is now {status}.", ephemeral=True)
		await refresh_post(self.bot, record.id)

	# == gear ==

	# ============================================================
	@gear.command(name="grant")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(character=_characters, item=_catalog)
	async def gear_grant(self, interaction: discord.Interaction, member: discord.Member, character: str, item: str) :
		"""
		Gives a member's character an item from the catalog for free, including event and staff-only items that
		aren't sold in the shop. Requirements like server level or roles don't apply.

		**Permissions:**
		- `Manage Messages`
		"""
		await interaction.response.defer(ephemeral=True)
		record = await self._character(interaction, member, character)
		if record is None :
			return
		catalog_item: GearItems | None = GearItemTransactions().find(interaction.guild_id, item)
		if catalog_item is None :
			return await interaction.followup.send(f"The catalog has no item called {item}.", ephemeral=True)
		entry = Gear.grant(record, catalog_item, interaction.user.id)
		if entry is None :
			return await interaction.followup.send("Something went wrong, please try again.", ephemeral=True)
		logging.info(f"GM {interaction.user.name} granted {catalog_item.name} to character {record.id} "
		             f"in {interaction.guild.name}")
		await interaction.followup.send(f"Gave {record.name} **{catalog_item.name}**."
		                                + unmet_warning(record, catalog_item), ephemeral=True)
		await refresh_post(self.bot, record.id)

	# ============================================================
	@gear.command(name="take")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(character=_characters, item=_owned)
	async def gear_take(self, interaction: discord.Interaction, member: discord.Member, character: str, item: str) :
		"""
		Removes an item from a member's character entirely, as if it never had it, for fixing mistakes. Nothing is
		refunded. To take gear away in the story, use /gm gear lose or /gm gear break instead.

		**Permissions:**
		- `Manage Messages`
		"""
		await interaction.response.defer(ephemeral=True)
		record, entry = await self._entry(interaction, member, character, item)
		if entry is None :
			return
		Gear.take(entry)
		logging.info(f"GM {interaction.user.name} took gear {entry.id} ({entry.name}) from character {record.id} "
		             f"in {interaction.guild.name}")
		await interaction.followup.send(f"Removed **{entry.name}** from {record.name}.", ephemeral=True)
		await refresh_post(self.bot, record.id)

	# ============================================================
	@gear.command(name="lose")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(character=_characters, item=_owned)
	async def gear_lose(self, interaction: discord.Interaction, member: discord.Member, character: str, item: str) :
		"""
		Marks an item of a member's character as lost. It leaves the inventory but stays in its history.

		**Permissions:**
		- `Manage Messages`
		"""
		await self._mark(interaction, member, character, item, LOST)

	# ============================================================
	@gear.command(name="break")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(character=_characters, item=_owned)
	async def gear_break(self, interaction: discord.Interaction, member: discord.Member, character: str, item: str) :
		"""
		Marks an item of a member's character as broken. It leaves the inventory but stays in its history.

		**Permissions:**
		- `Manage Messages`
		"""
		await self._mark(interaction, member, character, item, BROKEN)

	# == currency ==

	# ============================================================
	@currency.command(name="give")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(character=_characters)
	async def currency_give(self, interaction: discord.Interaction, member: discord.Member, character: str,
	                        amount: app_commands.Range[int, 1, 1000000000],
	                        note: app_commands.Range[str, 1, 200] = None) :
		"""
		Gives a member's character currency, for example as an event reward. The optional `note` shows in the
		character's /currency history.

		**Permissions:**
		- `Manage Messages`
		"""
		await interaction.response.defer(ephemeral=True)
		record = await self._character(interaction, member, character)
		if record is None :
			return
		updated, problem = Gear.give_currency(record, amount, interaction.user.id, note)
		if problem :
			return await interaction.followup.send(problem, ephemeral=True)
		guild_id = interaction.guild_id
		logging.info(f"GM {interaction.user.name} gave {amount} currency to character {record.id} "
		             f"in {interaction.guild.name}: {note or ''}")
		await interaction.followup.send(f"Gave {record.name} {balance_text(guild_id, amount)}; it now has "
		                                f"{balance_text(guild_id, updated.currency)}.", ephemeral=True)
		await refresh_post(self.bot, record.id)

	# ============================================================
	@currency.command(name="take")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(character=_characters)
	async def currency_take(self, interaction: discord.Interaction, member: discord.Member, character: str,
	                        amount: app_commands.Range[int, 1, 1000000000],
	                        note: app_commands.Range[str, 1, 200] = None) :
		"""
		Takes currency from a member's character, for example as a fine. A character can't go below 0. The optional
		`note` shows in the character's /currency history.

		**Permissions:**
		- `Manage Messages`
		"""
		await interaction.response.defer(ephemeral=True)
		record = await self._character(interaction, member, character)
		if record is None :
			return
		updated, problem = Gear.take_currency(record, amount, interaction.user.id, note)
		if problem :
			return await interaction.followup.send(problem, ephemeral=True)
		guild_id = interaction.guild_id
		logging.info(f"GM {interaction.user.name} took {amount} currency from character {record.id} "
		             f"in {interaction.guild.name}: {note or ''}")
		await interaction.followup.send(f"Took {balance_text(guild_id, amount)} from {record.name}; it now has "
		                                f"{balance_text(guild_id, updated.currency)}.", ephemeral=True)
		await refresh_post(self.bot, record.id)


async def setup(bot) :
	await bot.add_cog(GM(bot))
