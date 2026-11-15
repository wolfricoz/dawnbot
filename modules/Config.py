import logging

import discord
from discord import Interaction, app_commands
from discord.app_commands import Choice
from discord.ext import commands
from discord_py_utilities.messages import send_response

from classes.kernel.ConfigData import ConfigData
from classes.kernel.Queue import Queue
from classes.kernel.ServerSync import sync_server
from classes.progression.Progression import Progression
from classes.setup.BotSetup import BotSetup
from classes.setup.GuidedSetup import GuidedSetup
from classes.support.PermissionNotice import PermissionNotice, humanise
from database.transactions.LevelTransactions import LevelTransactions
from resources.configs.ConfigMapping import ConfigMapping, channels, choice_settings, number_settings, settings
from views.buttons.Confirm import ask


class Config(commands.GroupCog, name="Config", group_name="config") :
	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@staticmethod
	def _prepare(guild: discord.Guild) :
		"""Config rows reference the servers table, so make sure the guild is in it."""
		sync_server(guild)

	# ============================================================
	async def _track_channel(self, interaction: Interaction, channel: discord.TextChannel | discord.ForumChannel) -> str :
		"""Adds a channel to the XP channels and queues counting its history."""
		if not ConfigData().add_to_list(interaction.guild.id, ConfigMapping.XP_CHANNELS, channel.id) :
			return f"{channel.mention} is already an XP channel"
		Queue().add(self._count_and_report(interaction.channel, channel), priority=0)
		return f"{channel.mention} added to the XP channels; its history is being counted in the background"

	# ============================================================
	@staticmethod
	async def _count_and_report(report_channel, channel) :
		count = await Progression.count_history(channel)
		logging.info(f"Counted {count} messages in {channel.name} ({channel.guild.name})")
		try :
			await report_channel.send(f"Finished counting {count} messages in {channel.mention}", silent=True)
		except discord.HTTPException :
			pass

	# ============================================================
	@app_commands.command(name='setup')
	@app_commands.choices(mode=[
		Choice(name="guided: walks you through every channel and setting", value="guided"),
		Choice(name="auto: creates the channels for you", value="auto"),
	])
	@app_commands.checks.has_permissions(manage_guild=True)
	async def setup_command(self, interaction: Interaction, mode: Choice[str]) :
		"""
		Sets up the roleplay features: the character review, bot log, characters, species, gear, level-up and
		timeline channels, the roleplay channels and the main character, species and gear settings.

		`guided` walks you through it one step at a time: for each channel you pick one, let the bot create it, or
		skip; then you choose the settings and can import a ready-made gear pack. Every answer is saved straight away.

		`auto` creates every channel that is not set yet, in a hidden **Roleplay Staff** category, a read-only
		**Roleplay Info** category and a **Roleplay** category. Channels that are already set, or that already exist
		under the default name, are kept. Settings keep their values.

		Both end with what is still missing (such as permissions) and what to do next.

		**Permissions:**
		- `Manage Server`
		"""
		guild = interaction.guild
		self._prepare(guild)
		if mode.value == "guided" :
			return await GuidedSetup(self.bot, interaction).run()

		if missing := BotSetup.missing_auto_permissions(guild) :
			await PermissionNotice().notify(guild, missing, source="command", user=interaction.user)
			return await send_response(interaction, f"To create the channels I need {', '.join(humanise(missing))}; "
			                                        f"a notice with the details has been sent. `/config setup guided` "
			                                        f"lets you pick existing channels instead.", ephemeral=True)
		if not await ask(interaction, BotSetup.describe_plan(guild), "Set it up") :
			return await interaction.followup.send("Setup cancelled; nothing was changed.", ephemeral=True)
		try :
			report = await BotSetup.auto(guild)
		except discord.HTTPException as e :
			logging.warning(f"Auto setup stopped in {guild.name}: {e}", exc_info=True)
			return await interaction.followup.send(
				f"Setup stopped part-way because Discord refused a change: {e.text or e}. What was made so far is "
				f"kept; run it again once that is fixed.", embed=BotSetup.summary(guild), ephemeral=True)
		logging.info(f"{interaction.user.name} ran auto setup in {guild.name}")
		await interaction.followup.send(embed=BotSetup.summary(guild, report), ephemeral=True)

	# ============================================================
	@app_commands.command(name='roles')
	@app_commands.choices(option=[
		Choice(name="add", value="add"),
		Choice(name="remove", value="remove"),
		Choice(name="update", value="update"),
	])
	@app_commands.checks.has_permissions(manage_guild=True)
	async def roles(self, interaction: Interaction, option: Choice[str], role: discord.Role, xp_required: int = 0) :
		"""
		Adds, removes or updates a level role and the XP needed to reach it.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		match option.value :
			case 'add' :
				if LevelTransactions().add(interaction.guild.id, role.id, xp_required) is None :
					return await interaction.followup.send("Role already added")
				await interaction.followup.send(f"Added {role.mention} with required xp: {xp_required}")
			case 'remove' :
				if not LevelTransactions().remove(role.id) :
					return await interaction.followup.send("Role does not exist")
				await interaction.followup.send(f"Removed {role.mention}")
			case 'update' :
				if LevelTransactions().update(role.id, xp_required) is None :
					return await interaction.followup.send("Role does not exist")
				await interaction.followup.send(f"Updated {role.mention} with required xp: {xp_required}")

	# ============================================================
	@app_commands.command(name='announcement')
	@app_commands.checks.has_permissions(manage_guild=True)
	async def announcement(self, interaction: Interaction, channel: discord.TextChannel) :
		"""
		Sets the channel where level-ups are announced.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		self._prepare(interaction.guild)
		ConfigData().add_key(interaction.guild.id, ConfigMapping.ANNOUNCEMENT, channel.id, overwrite=True)
		await interaction.followup.send(f"Announcement channel set to {channel.mention}")

	# ============================================================
	@app_commands.command(name='xp_gain')
	@app_commands.checks.has_permissions(manage_guild=True)
	async def xp_per_character(self, interaction: Interaction, amount_of_characters: app_commands.Range[int, 1]) :
		"""
		Sets how many characters a message needs per point of XP.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		self._prepare(interaction.guild)
		ConfigData().add_key(interaction.guild.id, ConfigMapping.XP_GAIN, amount_of_characters, overwrite=True)
		await interaction.followup.send(f"xp_per_character set to {amount_of_characters}")

	# ============================================================
	@app_commands.command(name='currency_gain')
	@app_commands.checks.has_permissions(manage_guild=True)
	async def currency_per_character(self, interaction: Interaction,
	                                 amount_of_characters: app_commands.Range[int, 1]) :
		"""
		Sets how many characters a post made as a character needs per unit of currency for that character.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		self._prepare(interaction.guild)
		ConfigData().add_key(interaction.guild.id, ConfigMapping.CURRENCY_GAIN, amount_of_characters, overwrite=True)
		await interaction.followup.send(f"currency_per_character set to {amount_of_characters}")

	# ============================================================
	@app_commands.command(name='currency_name')
	@app_commands.checks.has_permissions(manage_guild=True)
	async def currency_name(self, interaction: Interaction, name: str) :
		"""
		Sets the name of the server's currency.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		self._prepare(interaction.guild)
		ConfigData().add_key(interaction.guild.id, ConfigMapping.CURRENCY_NAME, name, overwrite=True)
		await interaction.followup.send(f"currency name set to {name}")

	# ============================================================
	@app_commands.command(name='channel')
	@app_commands.choices(option=[
		Choice(name="add", value="add"),
		Choice(name="remove", value="remove"),
	])
	@app_commands.checks.has_permissions(manage_guild=True)
	async def channel(self, interaction: Interaction, option: Choice[str], channel: discord.TextChannel) :
		"""
		Adds or removes a text channel where messages earn XP (a roleplay channel). Posts made as a character there
		also earn the character currency.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		self._prepare(interaction.guild)
		match option.value :
			case 'add' :
				await interaction.followup.send(await self._track_channel(interaction, channel))
			case 'remove' :
				ConfigData().remove_from_list(interaction.guild.id, ConfigMapping.XP_CHANNELS, channel.id)
				await interaction.followup.send(f"{channel.mention} removed from the XP channels")

	# ============================================================
	@app_commands.command(name='singlechannels')
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.choices(option=[Choice(name=x.lower(), value=x.value) for x in
	                              [ConfigMapping.CHARACTER, ConfigMapping.CHARACTER_REVIEW, ConfigMapping.SPECIES_FORUM,
	                               ConfigMapping.GEAR_FORUM, ConfigMapping.TIMELINE, ConfigMapping.MODLOG]])
	async def singlechannels(self, interaction: Interaction, option: Choice[str],
	                         channel: discord.TextChannel | discord.ForumChannel) :
		"""
		Sets the character, character review, species forum, gear forum, timeline or modlog channel. Approved characters and
		species are posted in the character channel and the species forum (a forum gives each its own thread); new and
		edited characters and species wait for staff in the character review channel.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		self._prepare(interaction.guild)
		if option.value == ConfigMapping.CHARACTER_REVIEW and not isinstance(channel, discord.TextChannel) :
			return await interaction.followup.send("The character review channel has to be a text channel.")
		ConfigData().add_key(interaction.guild.id, option.value, channel.id, overwrite=True)
		await interaction.followup.send(f"{option.name} channel set to {channel.mention}")

	# ============================================================
	@app_commands.command(name='characters')
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.choices(option=[Choice(name=key.lower(), value=key.value) for key in number_settings])
	async def characters(self, interaction: Interaction, option: Choice[str], value: int) :
		"""
		Sets one of the numbers for characters: the character cap, the SPECIAL rules (stat_base, stat_bonus,
		stat_min, stat_max), how fast characters level (level_base, points_per_level) or the starting currency.
		Existing characters keep the stats they have.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		self._prepare(interaction.guild)
		guild_id = interaction.guild.id
		lowest, highest = number_settings[option.value]
		if not lowest <= value <= highest :
			return await interaction.followup.send(f"{option.name} has to be between {lowest} and {highest}.")
		stats = {key : ConfigData().get_int(guild_id, key) for key in
		         (ConfigMapping.STAT_MIN, ConfigMapping.STAT_BASE, ConfigMapping.STAT_MAX)}
		if option.value in stats :
			stats[option.value] = value
			if not stats[ConfigMapping.STAT_MIN] <= stats[ConfigMapping.STAT_BASE] <= stats[ConfigMapping.STAT_MAX] :
				return await interaction.followup.send(
					f"That would not fit: stat_min ({stats[ConfigMapping.STAT_MIN]}) has to be at most stat_base "
					f"({stats[ConfigMapping.STAT_BASE]}), which has to be at most stat_max "
					f"({stats[ConfigMapping.STAT_MAX]}). Change the others first.")
		ConfigData().add_key(guild_id, option.value, value, overwrite=True)
		await interaction.followup.send(f"{option.name} set to {value}")

	# ============================================================
	@app_commands.command(name='stat_method')
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.choices(method=[Choice(name=x, value=x) for x in choice_settings[ConfigMapping.STAT_METHOD]])
	async def stat_method(self, interaction: Interaction, method: Choice[str]) :
		"""
		Sets how members set their SPECIAL stats when creating a character: both (the member chooses), point_buy
		or rolled.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		self._prepare(interaction.guild)
		ConfigData().add_key(interaction.guild.id, ConfigMapping.STAT_METHOD, method.value, overwrite=True)
		await interaction.followup.send(f"stat_method set to {method.value}")

	# ============================================================
	@app_commands.command(name='proxy_outside_rp')
	@app_commands.checks.has_permissions(manage_guild=True)
	async def proxy_outside_rp(self, interaction: Interaction, enabled: bool) :
		"""
		Sets whether members can post as their characters outside the XP (roleplay) channels. Posts there earn no
		XP and have no minimum length. Off by default.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		self._prepare(interaction.guild)
		ConfigData().add_key(interaction.guild.id, ConfigMapping.PROXY_OUTSIDE_RP, "TRUE" if enabled else "FALSE",
		                     overwrite=True)
		where = "everywhere" if enabled else "only in the XP channels"
		await interaction.followup.send(f"Members can now post as their characters {where}.")

	# ============================================================
	@app_commands.command(name='species_creation')
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.choices(who=[Choice(name=x, value=x) for x in choice_settings[ConfigMapping.SPECIES_CREATION]])
	async def species_creation(self, interaction: Interaction, who: Choice[str]) :
		"""
		Sets who can create species with /species create: everyone, staff (Manage Messages) or off.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		self._prepare(interaction.guild)
		ConfigData().add_key(interaction.guild.id, ConfigMapping.SPECIES_CREATION, who.value, overwrite=True)
		await interaction.followup.send(f"species_creation set to {who.value}")

	# ============================================================
	@app_commands.command(name='economy')
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.choices(mode=[Choice(name=x, value=x) for x in choice_settings[ConfigMapping.ECONOMY]])
	async def economy(self, interaction: Interaction, mode: Choice[str]) :
		"""
		Sets whether gear costs currency: economy (characters buy gear and sell it for 30% of what they paid) or
		free (all gear costs nothing and selling returns nothing).

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		self._prepare(interaction.guild)
		ConfigData().add_key(interaction.guild.id, ConfigMapping.ECONOMY, mode.value, overwrite=True)
		await interaction.followup.send(f"economy set to {mode.value}")

	# ============================================================
	@app_commands.command(name='retire_thread')
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.choices(mode=[Choice(name=x, value=x) for x in choice_settings[ConfigMapping.RETIRE_THREAD]])
	async def retire_thread(self, interaction: Interaction, mode: Choice[str]) :
		"""
		Sets what happens to a retired character's post: lock (the forum thread is locked and archived, and opened
		again if the character returns) or delete.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		self._prepare(interaction.guild)
		ConfigData().add_key(interaction.guild.id, ConfigMapping.RETIRE_THREAD, mode.value, overwrite=True)
		await interaction.followup.send(f"retire_thread set to {mode.value}")

	# ============================================================
	@app_commands.command(name='reapproval')
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.choices(mode=[Choice(name=x, value=x) for x in choice_settings[ConfigMapping.REAPPROVAL_ON_EDIT]])
	async def reapproval(self, interaction: Interaction, mode: Choice[str]) :
		"""
		Sets which edits to an approved character need a new staff review: none, lore (name, picture and sheet
		answers) or all (also prefix, suffix and the member's own extra fields). A respec is always reviewed.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		self._prepare(interaction.guild)
		ConfigData().add_key(interaction.guild.id, ConfigMapping.REAPPROVAL_ON_EDIT, mode.value, overwrite=True)
		await interaction.followup.send(f"reapproval_on_edit set to {mode.value}")

	# ============================================================
	@app_commands.command(name='category')
	@app_commands.checks.has_permissions(manage_guild=True)
	async def category(self, interaction: Interaction, category: discord.CategoryChannel) :
		"""
		Adds every text channel and forum in a category to the XP channels.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		self._prepare(interaction.guild)
		results = []
		for channel in category.channels :
			if isinstance(channel, (discord.TextChannel, discord.ForumChannel)) :
				results.append(await self._track_channel(interaction, channel))
		await interaction.followup.send("\n".join(results) or "No text channels or forums in that category")

	# ============================================================
	@app_commands.command(name='forum')
	@app_commands.choices(option=[
		Choice(name="add", value="add"),
		Choice(name="remove", value="remove"),
	])
	@app_commands.checks.has_permissions(manage_guild=True)
	async def forum(self, interaction: Interaction, option: Choice[str], channel: discord.ForumChannel) :
		"""
		Adds or removes a forum whose posts earn XP (a roleplay forum). Posts made as a character there also earn
		the character currency.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		self._prepare(interaction.guild)
		match option.value :
			case 'add' :
				await interaction.followup.send(await self._track_channel(interaction, channel))
			case 'remove' :
				ConfigData().remove_from_list(interaction.guild.id, ConfigMapping.XP_CHANNELS, channel.id)
				await interaction.followup.send(f"{channel.mention} removed from the XP channels")

	# ============================================================
	@app_commands.command(name='view')
	@app_commands.checks.has_permissions(manage_guild=True)
	async def view(self, interaction: Interaction) :
		"""
		Shows the server's current settings.

		**Permissions:**
		- `Manage Server`
		"""
		guild = interaction.guild
		config = ConfigData()
		xp_channels = [f"<#{channel_id}>" for channel_id in config.get_list(guild.id, ConfigMapping.XP_CHANNELS)]
		lines = [f"**XP channels:** {', '.join(xp_channels) or 'none'}"]
		for key in channels :
			channel_id = config.get_int(guild.id, key)
			lines.append(f"**{key.lower()}:** {f'<#{channel_id}>' if channel_id else 'not set'}")
		for key in settings :
			# get_key reads "0" and "1" as off and on, so whole-number settings are read as numbers.
			value = config.get_int(guild.id, key) if key in number_settings else config.get_key(guild.id, key)
			lines.append(f"**{key.lower()}:** {value}")
		levels = LevelTransactions().get_all(guild.id)
		lines.append("**Level roles:** " + (
			", ".join(f"<@&{level.role_id}> ({level.xp_required} xp)" for level in levels) or "none"))
		embed = discord.Embed(title=f"{guild.name} settings", description="\n".join(lines))
		await send_response(interaction, " ", embed=embed, ephemeral=True)


async def setup(bot) :
	await bot.add_cog(Config(bot))
