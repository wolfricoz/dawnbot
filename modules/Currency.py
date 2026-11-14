import discord
from discord import app_commands
from discord.ext import commands

from classes.kernel.ConfigData import ConfigData
from database.transactions.ExperienceTransactions import ExperienceTransactions
from resources.configs.ConfigMapping import ConfigMapping


class Currency(commands.Cog) :
	"""Currency commands. Members earn currency by posting in the XP channels."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@app_commands.command(name="checkcurrency")
	async def checkcurrency(self, interaction: discord.Interaction) :
		"""
		Shows how much currency you have.
		"""
		await interaction.response.defer()
		user = ExperienceTransactions().get(interaction.user.id, interaction.guild.id)
		embed = discord.Embed(title=f"{interaction.user.name}'s currency",
		                      description=f"You currently have {user.currency} currency.")
		embed.set_footer(text=f"Current currency: {user.currency}.")
		await interaction.followup.send(embed=embed)

	# ============================================================
	@app_commands.command(name="getcurrency")
	async def getcurrency(self, interaction: discord.Interaction) :
		"""
		Shows how much currency you have, using the server's currency name.
		"""
		await interaction.response.defer()
		user = ExperienceTransactions().get(interaction.user.id, interaction.guild.id)
		currency_name = ConfigData().get_key(interaction.guild.id, ConfigMapping.CURRENCY_NAME)
		embed = discord.Embed(title=f"{interaction.user.name}'s currency",
		                      description=f"You currently have {user.currency} {currency_name}.")
		embed.set_footer(text=f"Current currency: {user.currency}.")
		await interaction.followup.send(embed=embed)

	# ============================================================
	@app_commands.command(name="setcurrency")
	@app_commands.checks.has_permissions(manage_guild=True)
	async def setcurrency(self, interaction: discord.Interaction, member: discord.Member, currency: int) :
		"""
		Sets a member's currency.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		ExperienceTransactions().set_currency(member.id, interaction.guild.id, currency)
		await interaction.followup.send(f"Currency of {member.mention} set to {currency}")

	# ============================================================
	@app_commands.command(name="addcurrency")
	@app_commands.checks.has_permissions(manage_guild=True)
	async def addcurrency(self, interaction: discord.Interaction, member: discord.Member, currency: int) :
		"""
		Adds currency to a member.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		ExperienceTransactions().add_currency(member.id, interaction.guild.id, currency)
		await interaction.followup.send(f"Added {currency} to {member.mention}")

	# ============================================================
	@app_commands.command(name="removecurrency")
	@app_commands.checks.has_permissions(manage_guild=True)
	async def removecurrency(self, interaction: discord.Interaction, member: discord.Member, currency: int) :
		"""
		Removes currency from a member.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		ExperienceTransactions().remove_currency(member.id, interaction.guild.id, currency)
		await interaction.followup.send(f"Removed {currency} from {member.mention}")


async def setup(bot) :
	await bot.add_cog(Currency(bot))
