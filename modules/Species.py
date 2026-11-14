import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.characters.Access import Access
from classes.characters.Choices import Choices
from classes.characters.CharacterFlow import CharacterFlow
from classes.kernel.ConfigData import ConfigData
from classes.species.SpeciesFlow import SpeciesFlow
from database.database import Species as SpeciesRow
from database.transactions.SpeciesTransactions import APPROVED, DENIED, PENDING, SpeciesTransactions
from resources.configs.ConfigMapping import ConfigMapping
from views.buttons.Confirm import ask

STATE_LABELS = {PENDING : "waiting for review", DENIED : "denied"}


@app_commands.guild_only()
class Species(commands.GroupCog, name="Species", group_name="species") :


	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	async def _names(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		"""Approved species, plus the member's own and (for staff) every species waiting for review."""
		staff = interaction.user.guild_permissions.manage_messages
		names = [species.name for species in SpeciesTransactions().get_all(interaction.guild_id)
		         if species.state == APPROVED or staff or species.creator_uid == interaction.user.id]
		return [Choice(name=name, value=name) for name in names if current.lower() in name.lower()][:25]

	# ============================================================
	async def _find(self, interaction: discord.Interaction, name: str) -> SpeciesRow | None :
		species = SpeciesTransactions().find(interaction.guild_id, name)
		if species is None or (species.state != APPROVED and species.creator_uid != interaction.user.id
		                       and not interaction.user.guild_permissions.manage_messages) :
			await CharacterFlow.respond(interaction, f"This server has no species called {name}.")
			return None
		return species

	# ============================================================
	@app_commands.command(name="create", description="Creates a species; I ask the questions in your DMs")
	async def create(self, interaction: discord.Interaction) :
		"""
		Starts creating a species. The bot asks in your DMs for its name, description, benefits and drawbacks, and how
		it changes the SPECIAL stats: its own highest and lowest values per stat, which have to balance out, and
		changes to the starting stats. Staff review it; once approved, anyone can pick it for their characters.
		"""
		await interaction.response.defer(ephemeral=True)
		who = str(ConfigData().get_key(interaction.guild_id, ConfigMapping.SPECIES_CREATION)).lower()
		if who == "off" :
			return await interaction.followup.send("This server does not take new species.")
		if who == "staff" and not interaction.user.guild_permissions.manage_messages :
			return await interaction.followup.send("On this server, only staff create species.")
		if ConfigData().get_int(interaction.guild_id, ConfigMapping.CHARACTER_REVIEW) is None :
			return await interaction.followup.send(
				"This server has not set up reviews yet. Staff can set the review channel with "
				"`/config singlechannels` (option `character_review`).")
		await SpeciesFlow.begin(interaction)

	# ============================================================
	@app_commands.command(name="edit", description="Changes a species you made; staff review the changes")
	@app_commands.autocomplete(name=_names)
	async def edit(self, interaction: discord.Interaction, name: str) :
		"""
		Changes a species you made (staff can change any species). The bot shows the current answers in your DMs.
		Changes to an approved species are reviewed before they apply. Characters keep the stats they have.
		"""
		await interaction.response.defer(ephemeral=True)
		if (species := await self._find(interaction, name)) is None :
			return
		if species.creator_uid != interaction.user.id and not interaction.user.guild_permissions.manage_messages :
			return await interaction.followup.send(f"Only the creator of {species.name} or staff can change it.")
		await SpeciesFlow.begin(interaction, species)

	# ============================================================
	@app_commands.command(name="list", description="Lists the species characters can be")
	async def list_species(self, interaction: discord.Interaction) :
		"""
		Lists the server's approved species, marking the ones that are restricted for you. Your own species that are
		waiting for review or were denied are listed too.
		"""
		await interaction.response.defer(ephemeral=True)
		access = Access.of(interaction.user)
		open_to_you = {species.id for species in Choices.species(interaction.guild_id, access)}
		lines = []
		for species in SpeciesTransactions().get_all(interaction.guild_id) :
			if species.state == APPROVED :
				requirements = Access.for_species(species)
				if Access.hidden(requirements) and not access.staff :
					continue
				note = "" if species.id in open_to_you else f" (restricted: {access.check(requirements)})"
				link = f" · <#{species.forum_thread_id}>" if species.forum_thread_id else ""
				lines.append(f"**{species.name}**{note}{link}")
			elif species.creator_uid == interaction.user.id or access.staff :
				lines.append(f"**{species.name}** ({STATE_LABELS.get(species.state, species.state)})")
		if not lines :
			return await interaction.followup.send("This server has no species yet.")
		await interaction.followup.send(embed=discord.Embed(title="Species", description="\n".join(lines)[:4000]))

	# ============================================================
	@app_commands.command(name="view", description="Shows a species")
	@app_commands.autocomplete(name=_names)
	async def view(self, interaction: discord.Interaction, name: str) :
		"""
		Shows a species: its description, benefits, drawbacks and how it changes the SPECIAL stats.
		"""
		await interaction.response.defer(ephemeral=True)
		if (species := await self._find(interaction, name)) is None :
			return
		await interaction.followup.send(embed=SpeciesFlow.embed(species))

	# ============================================================
	@app_commands.command(name="delete", description="Deletes a species that no character is")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(name=_names)
	async def delete(self, interaction: discord.Interaction, name: str) :
		"""
		Deletes a species and its post. A species that characters are cannot be deleted.

		**Permissions:**
		- `Manage Messages`
		"""
		species = SpeciesTransactions().find(interaction.guild_id, name)
		if species is None :
			return await CharacterFlow.respond(interaction, f"This server has no species called {name}.")
		users = SpeciesTransactions().users(species.id)
		if users :
			return await CharacterFlow.respond(interaction, f"{users} character{'s are' if users != 1 else ' is'} "
			                                                f"{species.name}, so it cannot be deleted.")
		if not await ask(interaction, f"Delete the species **{species.name}**? This cannot be undone.", "Delete") :
			return
		await SpeciesFlow.remove_post(self.bot, species)
		SpeciesTransactions().delete(species.id)
		logging.info(f"{interaction.user.name} deleted species {species.name} in {interaction.guild.name}")
		await interaction.followup.send(f"The species {species.name} was deleted.", ephemeral=True)


async def setup(bot) :
	await bot.add_cog(Species(bot))
