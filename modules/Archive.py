import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands
from discord_py_utilities.messages import send_response

from classes.setup.Safeguards import missing_permissions, owner_error
from classes.setup.ServerSetup import ServerSetup
from classes.support.PermissionNotice import PermissionNotice
from views.buttons.Confirm import double_confirm

ALL_ARCHIVES = "all"


class Archive(commands.GroupCog, name="Archive", group_name="archive") :
	"""The archive holds channels set aside by /template apply. Archived channels are named
	"<old category>・<channel>" and hidden from everyone until they are restored."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	async def archive_autocomplete(self, interaction: discord.Interaction, current: str) :
		choices = [Choice(name="All archives", value=ALL_ARCHIVES)]
		choices += [Choice(name=f"{category.name} ({len(category.channels)} channels)", value=str(category.id))
		            for category in ServerSetup.archive_categories(interaction.guild)
		            if current.lower() in category.name.lower()]
		return choices[:25]

	# ============================================================
	@app_commands.command(name="restore", description="Moves archived channels back to the categories they came from")
	@app_commands.autocomplete(archive=archive_autocomplete)
	@app_commands.checks.has_permissions(administrator=True)
	async def restore(self, interaction: discord.Interaction, archive: str = ALL_ARCHIVES) :
		"""
		Moves archived channels back to the category named at the start of their name (recreating it if it is gone),
		gives them their old name and restores who could see them. Restores one archive category, or all of them.

		**Permissions:**
		- `Administrator`
		"""
		guild = interaction.guild
		category = None
		if archive != ALL_ARCHIVES :
			category = guild.get_channel(int(archive)) if archive.isnumeric() else None
			if not isinstance(category, discord.CategoryChannel) or not ServerSetup.is_archive(category) :
				return await send_response(interaction, "That is not an archive category.", ephemeral=True)
		elif not ServerSetup.archive_categories(guild) :
			return await send_response(interaction, "There is nothing in the archive.", ephemeral=True)
		if missing := missing_permissions(guild) :
			await PermissionNotice().notify(guild, missing, source="command", user=interaction.user)
			return await send_response(interaction, "I'm missing the permissions to move channels; "
			                                        "a notice with the details has been sent.", ephemeral=True)

		await interaction.response.defer(ephemeral=True)
		restored, from_name = await ServerSetup.restore(guild, category)
		logging.info(f"{interaction.user} restored {restored} archived channels in {guild.name}")
		message = f"Restored {restored} channel(s)."
		if from_name :
			message += (f" {from_name} had no stored record, so they were placed by the category in their name and "
			            f"now follow that category's permissions; check who can see them.")
		await interaction.followup.send(message, ephemeral=True)

	# ============================================================
	@app_commands.command(name="purge", description="Deletes ALL archived channels; this can NOT be undone")
	async def purge(self, interaction: discord.Interaction) :
		"""
		Permanently deletes every archive category and the channels in it, after asking twice.

		**Permissions:**
		- `Server Owner`
		"""
		if error := owner_error(interaction) :
			return await send_response(interaction, error, ephemeral=True)
		archives = ServerSetup.archive_categories(interaction.guild)
		count = sum(len(category.channels) for category in archives)
		if not archives :
			return await send_response(interaction, "There is nothing in the archive.", ephemeral=True)
		confirmed = await double_confirm(
			interaction,
			f"Purge the archive of **{interaction.guild.name}**? {count} channel(s) in {len(archives)} archive "
			f"category(ies) will be deleted.",
			"**Are you sure?** Deleted channels and their messages can NOT be recovered.")
		if not confirmed :
			return await interaction.followup.send("Cancelled, nothing was deleted.", ephemeral=True)
		deleted = await ServerSetup.purge(interaction.guild)
		logging.info(f"{interaction.user} purged {deleted} archived channels in {interaction.guild.name}")
		await interaction.followup.send(f"Archive purged: {deleted} channel(s) deleted.", ephemeral=True)


async def setup(bot) :
	await bot.add_cog(Archive(bot))
