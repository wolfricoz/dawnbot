import discord
from discord import app_commands
from discord.ext import commands

from classes.kernel.AccessControl import AccessControl
from classes.progression.Progression import Progression
from database.transactions.ExperienceTransactions import ExperienceTransactions
from database.transactions.LevelTransactions import LevelTransactions


class Experience(commands.Cog) :
	"""XP commands. Members earn XP by posting in the XP channels set with /config channel and /config forum."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@app_commands.command(name="recount")
	@AccessControl().check_access("dev")
	async def recount(self, interaction: discord.Interaction) :
		"""
		Resets everyone's XP in this server and counts every XP channel again.

		**Permissions:**
		- `Developer`
		"""
		await interaction.response.defer()
		message = await interaction.channel.send("Resetting users")

		async def progress(text: str) :
			await message.edit(content=text)

		await Progression.recount(interaction.guild, on_progress=progress)
		await interaction.followup.send("Finished recounting")

	# ============================================================
	@app_commands.command(name="checkxp")
	async def checkxp(self, interaction: discord.Interaction) :
		"""
		Shows your XP and how much you need for the next level role.
		"""
		await interaction.response.defer()
		user = ExperienceTransactions().get(interaction.user.id, interaction.guild.id)
		role_id, xp_required = LevelTransactions().next_level(interaction.guild.id, user.xp)
		role = interaction.guild.get_role(role_id) if role_id else None
		if role is None :
			description = "This server has no level roles yet."
		elif xp_required is None :
			description = f"You have reached the highest level, {role.name}!"
		else :
			description = f"You need {xp_required - user.xp} to reach {role.name}"
		embed = discord.Embed(title=f"{interaction.user.name}'s level", description=description)
		embed.set_footer(text=f"Current xp: {user.xp}. You've sent {user.messages} messages")
		await interaction.followup.send(embed=embed)

	# ============================================================
	@app_commands.command(name="setxp")
	@app_commands.checks.has_permissions(manage_guild=True)
	async def setxp(self, interaction: discord.Interaction, member: discord.Member, xp: int) :
		"""
		Sets a member's XP.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		ExperienceTransactions().set_xp(member.id, interaction.guild.id, xp)
		await interaction.followup.send(f"xp of {member.mention} set to {xp}")

	# ============================================================
	@app_commands.command(name="addxp")
	@app_commands.checks.has_permissions(manage_guild=True)
	async def addxp(self, interaction: discord.Interaction, member: discord.Member, xp: int) :
		"""
		Adds XP to a member.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		ExperienceTransactions().add_xp(member.id, interaction.guild.id, xp, count_message=False)
		await interaction.followup.send(f"added {xp} to {member.mention}")

	# ============================================================
	@app_commands.command(name="removexp")
	@app_commands.checks.has_permissions(manage_guild=True)
	async def removexp(self, interaction: discord.Interaction, member: discord.Member, xp: int) :
		"""
		Removes XP from a member.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		ExperienceTransactions().remove_xp(member.id, interaction.guild.id, xp)
		await interaction.followup.send(f"Removed {xp} from {member.mention}")


async def setup(bot) :
	await bot.add_cog(Experience(bot))
