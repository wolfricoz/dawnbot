"""Stashes: a character with a rented room at a location (/merchant lodge) keeps items there. Stashed items leave the
inventory, weigh nothing and stay out of fights, and come back out at the same location.
"""
import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.combat.AutoComplete import AutoComplete
from classes.economy import Merchants as Rules
from classes.world.WorldFlow import WorldFlow
from database.transactions.CharacterGearTransactions import CharacterGearTransactions
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.MerchantTransactions import MerchantTransactions
from database.transactions.WorldTransactions import WorldTransactions
from modules.Gear import entry_choices, find_entry
from views.combat.Pickers import reply


@app_commands.guild_only()
class Stash(commands.GroupCog, name="Stash", group_name="stash") :
	"""Keep items in the stash of a room you rent."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	def _character(self, interaction: discord.Interaction, name: str | None) :
		character = CharacterTransactions().get(interaction.user.id, interaction.guild_id, name) if name else None
		return character if character is not None and character.state == APPROVED else None

	# ============================================================
	async def _carried(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		character = self._character(interaction, interaction.namespace.character)
		if character is None :
			return []
		return entry_choices([entry for entry in CharacterGearTransactions().get_all(character.id)
		                      if not entry.equipped], current)

	# ============================================================
	async def _stashed(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		character = self._character(interaction, interaction.namespace.character)
		location = WorldFlow.location_here(interaction.channel)
		if character is None or location is None :
			return []
		return entry_choices(Rules.stashed(character, location.id), current)

	# ============================================================
	async def _where(self, interaction: discord.Interaction, name: str) :
		character = self._character(interaction, name)
		location = WorldFlow.location_here(interaction.channel)
		if character is None :
			await reply(interaction, "Pick one of your approved characters.")
			return None, None
		if location is None :
			await reply(interaction, "Stashes are used in a location's channel.")
			return None, None
		return character, location

	# ============================================================
	@app_commands.command(name="put", description="Puts an item in your stash here")
	@app_commands.autocomplete(character=AutoComplete().approved_character, item=_carried)
	async def put(self, interaction: discord.Interaction, character: str, item: str) :
		"""
		Puts one of your character's items in its stash at this location. It needs a paid room here (/merchant
		lodge); equipped items have to be put away first.
		"""
		record, location = await self._where(interaction, character)
		if record is None :
			return
		entry = find_entry(CharacterGearTransactions().get_all(record.id), item)
		if entry is None :
			return await reply(interaction, f"{record.name} isn't carrying {item}.")
		problem = Rules.stash(record, entry, location.id)
		if problem :
			return await reply(interaction, problem)
		await reply(interaction, f"{record.name} stashed **{entry.name}** at {location.name}.")

	# ============================================================
	@app_commands.command(name="take", description="Takes an item out of your stash here")
	@app_commands.autocomplete(character=AutoComplete().approved_character, item=_stashed)
	async def take(self, interaction: discord.Interaction, character: str, item: str) :
		"""
		Takes an item out of your character's stash at this location. This works even after the room's rent ran
		out.
		"""
		record, location = await self._where(interaction, character)
		if record is None :
			return
		entry = find_entry(Rules.stashed(record, location.id), item)
		if entry is None :
			return await reply(interaction, f"{record.name} has no {item} stashed here.")
		problem = Rules.unstash(record, entry, location.id)
		if problem :
			return await reply(interaction, problem)
		await reply(interaction, f"{record.name} took **{entry.name}** out of the stash.")

	# ============================================================
	@app_commands.command(name="list", description="Shows what your character keeps in its stashes")
	@app_commands.autocomplete(character=AutoComplete().approved_character)
	async def list_stash(self, interaction: discord.Interaction, character: str) :
		"""
		Shows everything your character keeps in stashes, by location, and until when its rooms are paid.
		"""
		record = self._character(interaction, character)
		if record is None :
			return await reply(interaction, "Pick one of your approved characters.")
		lines = []
		rooms = {lodging.location_id : lodging for lodging in MerchantTransactions().lodgings(record.id)}
		places = {entry.stash_location_id for entry in Rules.stashed(record)} | set(rooms)
		for location_id in places :
			location = WorldTransactions().location(location_id)
			name = location.name if location else "a place that's gone"
			room = rooms.get(location_id)
			paid = f" (room paid until {discord.utils.format_dt(room.paid_until, 'd')})" if room else ""
			items = [entry.name for entry in Rules.stashed(record, location_id)]
			lines.append(f"**{name}**{paid}: {', '.join(items) or 'empty'}")
		await reply(interaction, "\n".join(lines) or f"{record.name} has no stash or room yet.")


async def setup(bot) :
	await bot.add_cog(Stash(bot))
