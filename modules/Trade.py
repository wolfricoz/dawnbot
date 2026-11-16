"""Trading between characters of different players: a trade window where each side offers items and currency, and the
swap happens once both accept. Your own characters can't trade with each other.
"""
import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.combat.AutoComplete import AutoComplete
from classes.economy.TradeFlow import TradeFlow
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions


@app_commands.guild_only()
class Trade(commands.Cog) :
	"""Trade items and currency with another player's character."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	async def _theirs(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		member = interaction.namespace.member
		if member is None :
			return []
		return [Choice(name=character.name, value=character.name)
		        for character in CharacterTransactions().get_all(member.id, interaction.guild_id, states=[APPROVED])
		        if current.lower() in character.name.lower()][:25]

	# ============================================================
	@app_commands.command(name="trade", description="Opens a trade window with another player's character")
	@app_commands.autocomplete(character=AutoComplete().approved_character, theirs=_theirs)
	@app_commands.describe(character="Your character", member="The other player",
	                       theirs="The other player's character")
	async def trade(self, interaction: discord.Interaction, character: str, member: discord.Member, theirs: str) :
		"""
		Opens a trade window here between your character and another player's. Each of you offers items (equipped
		items have to be put away first) and currency, then both press Accept; any change clears both accepts, and
		the bot swaps everything at once. The window expires after 10 minutes without a press. Every trade is in the
		currency history of both characters.
		"""
		await TradeFlow.start(interaction, character, member, theirs)


async def setup(bot) :
	await bot.add_cog(Trade(bot))
