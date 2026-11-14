import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext.commands import Bot, GroupCog
from discord_py_utilities.messages import send_response

from classes.kernel.AccessControl import AccessControl
from classes.kernel.ConfigData import ConfigData
from data.env.loader import load_environment
from database.transactions.StaffTransactions import StaffTransactions
from project.data import BOT_NAME


class Dev(GroupCog, name="Dev", group_name="dev") :
	"""Developer and bot-owner commands."""

	def __init__(self, bot: Bot) :
		self.bot = bot

	# ============================================================
	@app_commands.command(name="reload", description="[DEV] Reloads the .env file")
	@AccessControl().check_access("dev")
	async def reload_env(self, interaction: discord.Interaction) :
		"""
		[DEV] Reloads the environment variables from the .env file.

		**Permissions:**
		- `Developer`
		"""
		load_environment(override=True)
		await send_response(interaction, "The environment file has been reloaded.", ephemeral=True)

	# ============================================================
	@app_commands.command(name="reload_modules", description="[DEV] Reloads every cog and syncs the commands")
	@AccessControl().check_access("dev")
	async def reload_modules(self, interaction: discord.Interaction) :
		"""
		[DEV] Reloads every loaded module, listener and task, then syncs the slash commands.

		**Permissions:**
		- `Developer`
		"""
		await interaction.response.defer(ephemeral=True)
		reloaded = []
		for extension in list(self.bot.extensions) :
			await self.bot.reload_extension(extension)
			reloaded.append(extension)
		await self.bot.tree.sync()
		await interaction.followup.send(f"Modules reloaded: {', '.join(reloaded)}")

	# ============================================================
	@app_commands.command(name="add_staff", description=f"[DEV] Adds a user to the {BOT_NAME} staff team.")
	@app_commands.choices(role=[Choice(name=x, value=x.lower()) for x in ["Dev", "Rep"]])
	async def add_staff(self, interaction: discord.Interaction, user: discord.User, role: Choice[str]) :
		"""
		[DEV] Adds a user to the bot staff with a specified role.

		**Permissions:**
		- `Bot Owner`
		"""
		if not AccessControl().access_owner(interaction.user.id) :
			return await send_response(interaction, "You do not have permission to add staff members")
		StaffTransactions().add(user.id, role.value)
		AccessControl().reload()
		await send_response(interaction, f"Staff member {user.mention} successfully added as a `{role.name}`!")

	# ============================================================
	@app_commands.command(name="remove_staff", description=f"[DEV] Removes a staff member from the {BOT_NAME} team.")
	@AccessControl().check_access("dev")
	async def remove_staff(self, interaction: discord.Interaction, user: discord.User) :
		"""
		[DEV] Removes a user from the bot staff.

		**Permissions:**
		- `Developer`
		"""
		StaffTransactions().delete(user.id)
		AccessControl().reload()
		await send_response(interaction, f"Staff member {user.mention} successfully removed!")

	# ============================================================
	@app_commands.command(name="stop", description="[DEV] Shuts down the bot. Only the bot owner can use this.")
	async def quit(self, interaction: discord.Interaction) :
		"""
		[DEV] Shuts down the bot.

		**Permissions:**
		- `Bot Owner`
		"""
		if not AccessControl().access_owner(interaction.user.id) :
			return await send_response(interaction, "You do not have permission to stop the bot")
		await send_response(interaction, "Shutting down", ephemeral=True)
		await self.bot.close()

	# ============================================================
	@app_commands.command(name="leave_server", description="[DEV] Leave a server")
	@AccessControl().check_access("dev")
	async def leave_server(self, interaction: discord.Interaction, guildid: str) :
		"""
		[DEV] Makes the bot leave a server.

		**Permissions:**
		- `Developer`
		"""
		guild = self.bot.get_guild(int(guildid)) if guildid.isnumeric() else None
		if guild is None :
			return await send_response(interaction, "Server not found", ephemeral=True)
		await guild.leave()
		await send_response(interaction, f"Left {guild}")

	# ============================================================
	@app_commands.command(name="getlog", description="[DEV] Sends today's log file")
	@AccessControl().check_access("dev")
	async def getlog(self, interaction: discord.Interaction) :
		"""
		[DEV] Sends today's log file.

		**Permissions:**
		- `Developer`
		"""
		from modules.logs import logfile
		await send_response(interaction, "Here's the log file.", file=discord.File(logfile, "log.txt"), ephemeral=True)

	# ============================================================
	@app_commands.command(name="migrate_config", description="[DEV] Imports leftover jsons/*.json configs")
	@AccessControl().check_access("dev")
	async def migrate_config(self, interaction: discord.Interaction) :
		"""
		[DEV] Imports any jsons/<guild_id>.json config that was not imported at start-up.

		**Permissions:**
		- `Developer`
		"""
		imported = ConfigData().migrate()
		await send_response(interaction, f"Imported {imported} config file(s).", ephemeral=True)


async def setup(bot: Bot) :
	await bot.add_cog(Dev(bot))
