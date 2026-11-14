import discord
from discord import app_commands
from discord.ext import commands

from database.transactions.ExperienceTransactions import ExperienceTransactions
from database.transactions.LevelTransactions import LevelTransactions


class User(commands.GroupCog, name="User", group_name="user") :
	"""Your progression in this server."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@app_commands.command(name="stats")
	async def stats(self, interaction: discord.Interaction) :
		"""
		Shows your XP, message count and the next level role. Currency belongs to characters; see /currency.
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

		embed = discord.Embed(title=f"{interaction.user.name}'s level\n"
		                            f"Current XP: {user.xp}\n"
		                            f"Messages sent: {user.messages}\n",
		                      description=description)
		embed.set_footer(text=f"Current xp: {user.xp}. You've sent {user.messages} messages")
		await interaction.followup.send(embed=embed)


async def setup(bot) :
	await bot.add_cog(User(bot))
