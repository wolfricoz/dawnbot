"""Travel: /travel sends a character from where it is to another location, with an encounter roll on dangerous routes.
Needs TRAVEL on (/config roleplay). See design/roleplay-tools.md, section 5.
"""
import discord
from discord import app_commands
from discord.ext import commands

from classes.combat.AutoComplete import AutoComplete
from classes.world.TravelFlow import TravelFlow


@app_commands.guild_only()
class Travel(commands.Cog) :
	"""Travel between locations, with encounters on dangerous roads."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@app_commands.command(name="travel", description="Sends your character to another location")
	@app_commands.autocomplete(character=AutoComplete().approved_character)
	@app_commands.describe(character="Your character", destination="The location's channel")
	async def travel(self, interaction: discord.Interaction, character: str, destination: discord.TextChannel) :
		"""
		Sends a character from this channel's location (or where it last posted) to another. A departure line is
		posted here and an arrival line there: right away with manual time, or after the route's travel time when
		in-world time flows. On a dangerous route (or to a dangerous place) the character rolls d20 + Luck modifier
		against 8 + 2 x danger; a failure rolls the route's (or destination's) encounter table at the destination.
		Characters can still post anywhere while on the road.
		"""
		await TravelFlow.travel(interaction, character, destination)


async def setup(bot) :
	await bot.add_cog(Travel(bot))
