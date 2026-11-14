import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands
from discord_py_utilities.messages import send_response

from classes.setup.Safeguards import MAX_MEMBERS, missing_permissions, owner_error, template_error
from classes.setup.ServerSetup import ServerSetup
from classes.support.PermissionNotice import PermissionNotice
from database.transactions.TemplateTransactions import MAX_TEMPLATES, TemplateTransactions
from views.buttons.Confirm import double_confirm


class Template(commands.GroupCog, name="Template", group_name="template") :
	"""Save a server's categories and channels as a template and apply it to a new server.

	Applying a template archives the existing channels (see /archive) and is limited to the server owner, to servers
	with at most 10 members, and asks for confirmation twice.
	"""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	async def template_autocomplete(self, interaction: discord.Interaction, current: str) :
		names = TemplateTransactions().get_names(interaction.user.id)
		return [Choice(name=name, value=name) for name in names if current.lower() in name.lower()][:25]

	# ============================================================
	@app_commands.command(name="register", description="Saves this server's categories and channels as a template")
	async def register(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 100]) :
		"""
		Saves this server's categories and channels (not their messages or permissions) as one of your templates.

		**Permissions:**
		- `Server Owner`
		"""
		if error := owner_error(interaction) :
			return await send_response(interaction, error, ephemeral=True)
		count = TemplateTransactions().count(interaction.user.id)
		if count >= MAX_TEMPLATES :
			return await send_response(interaction, f"You have reached the maximum number of templates ({MAX_TEMPLATES})",
			                           ephemeral=True)
		data = ServerSetup.capture(interaction.guild)
		if TemplateTransactions().add(interaction.user.id, interaction.guild.id, name, data) is None :
			return await send_response(interaction, f"Template '{name}' already exists", ephemeral=True)
		await send_response(interaction,
		                    f"Template '{name.lower()}' created successfully! You can create {MAX_TEMPLATES - count - 1} more templates",
		                    ephemeral=True)

	# ============================================================
	@app_commands.command(name="apply", description="Archives this server's channels and builds one of your templates")
	@app_commands.autocomplete(template=template_autocomplete)
	async def apply(self, interaction: discord.Interaction, template: str) :
		"""
		Archives every channel that sits in a category, removes those categories and builds the template. Only works
		in servers with at most 10 members (bots not counted) and asks for confirmation twice. Archived channels can
		be brought back with /archive restore.

		**Permissions:**
		- `Server Owner`
		"""
		if error := template_error(interaction) :
			return await send_response(interaction, error, ephemeral=True)
		record = TemplateTransactions().get(interaction.user.id, template)
		if record is None :
			return await send_response(interaction, f"Template '{template}' does not exist", ephemeral=True)
		if missing := missing_permissions(interaction.guild) :
			await PermissionNotice().notify(interaction.guild, missing, source="command", user=interaction.user)
			return await send_response(interaction, "I'm missing the permissions to rebuild this server; "
			                                        "a notice with the details has been sent.", ephemeral=True)

		categories, channels = ServerSetup.affected(interaction.guild)
		confirmed = await double_confirm(
			interaction,
			f"Apply the `{record.name}` template to **{interaction.guild.name}**?",
			f"**Are you sure?** {len(channels)} channel(s) will be archived and {len(categories)} category(ies) "
			f"deleted before the template is built. Archived channels can be restored with /archive restore.")
		# The server may have grown while the questions were open.
		if not confirmed or template_error(interaction) :
			return await interaction.followup.send("Cancelled, nothing was changed.", ephemeral=True)

		await interaction.followup.send(f"Applying `{record.name}`...", ephemeral=True)
		archived, created = await ServerSetup.apply(interaction.guild, record.data)
		logging.info(f"{interaction.user} applied template {record.name} in {interaction.guild.name}: "
		             f"{archived} archived, {created} created")
		await interaction.followup.send(f"Template `{record.name}` applied: {archived} channel(s) archived, "
		                                f"{created} channel(s) created.", ephemeral=True)

	# ============================================================
	@app_commands.command(name="list", description="Lists your templates")
	async def list(self, interaction: discord.Interaction) :
		"""
		Lists the templates you have registered.
		"""
		names = TemplateTransactions().get_names(interaction.user.id)
		if not names :
			return await send_response(interaction, "You have no templates yet; create one with /template register.",
			                           ephemeral=True)
		await send_response(interaction, "Your templates:\n" + "\n".join(f"* {name}" for name in names), ephemeral=True)

	# ============================================================
	@app_commands.command(name="view", description="Shows the categories and channels of one of your templates")
	@app_commands.autocomplete(template=template_autocomplete)
	async def view(self, interaction: discord.Interaction, template: str) :
		"""
		Shows the categories and channels of one of your templates.
		"""
		record = TemplateTransactions().get(interaction.user.id, template)
		if record is None :
			return await send_response(interaction, f"Template '{template}' does not exist", ephemeral=True)
		embed = discord.Embed(title=f"Template '{record.name}'", description=ServerSetup.describe(record.data)[:4000])
		embed.set_footer(text=f"Can be applied to servers with at most {MAX_MEMBERS} members.")
		await send_response(interaction, " ", embed=embed, ephemeral=True)

	# ============================================================
	@app_commands.command(name="delete", description="Deletes one of your templates")
	@app_commands.autocomplete(template=template_autocomplete)
	async def delete(self, interaction: discord.Interaction, template: str) :
		"""
		Deletes one of your templates.
		"""
		if not TemplateTransactions().delete(interaction.user.id, template) :
			return await send_response(interaction, f"Template '{template}' does not exist", ephemeral=True)
		remaining = MAX_TEMPLATES - TemplateTransactions().count(interaction.user.id)
		await send_response(interaction, f"Template '{template}' deleted! You can create {remaining} more templates",
		                    ephemeral=True)


async def setup(bot) :
	await bot.add_cog(Template(bot))
