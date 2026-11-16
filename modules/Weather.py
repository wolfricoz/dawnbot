"""Weather: what it is like where a channel is, and setting it by hand. Weather is rolled per region from its climate
and the season, and changes a step at a time; in fog, storms and the like it changes outdoor checks (WEATHER_EFFECTS).
See design/roleplay-tools.md, section 4.
"""
import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.kernel.GMRole import gm_only
from classes.world import Weather as WeatherRules
from classes.world.WorldFlow import WorldFlow
from database.transactions.WorldTransactions import WorldTransactions
from views.combat.Pickers import reply


# ============================================================
async def region_autocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	return [Choice(name=region.name[:100], value=region.name[:100])
	        for region in WorldTransactions().regions(interaction.guild_id)
	        if current.lower() in region.name.lower()][:25]


# ============================================================
async def weather_autocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	region = WorldTransactions().find_region(interaction.guild_id, interaction.namespace.region or "")
	climate = region.climate if region else WeatherRules.TEMPERATE
	return [Choice(name=f"{kind.emoji} {kind.name}", value=kind.key) for kind in WeatherRules.ladder(climate)
	        if current.lower() in kind.name.lower()][:25]


@app_commands.guild_only()
class Weather(commands.GroupCog, name="Weather", group_name="weather") :
	"""The weather where you are, rolled per region from its climate and the season."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@app_commands.command(name="now", description="Shows the weather where a channel is")
	@app_commands.describe(channel="The channel (default: this one)")
	async def now(self, interaction: discord.Interaction, channel: discord.TextChannel = None) :
		"""
		Shows the weather at a channel's location (or the server's own weather where there is no location), with what
		it does to outdoor checks.
		"""
		channel = channel or interaction.channel
		location = WorldFlow.location_here(channel)
		climate, key = WorldFlow.weather(interaction.guild_id, location)
		where = location.name if location else "Around here"
		await interaction.response.send_message(f"**{where}:** {WeatherRules.text(climate, key)}", ephemeral=True)

	# ============================================================
	@app_commands.command(name="set", description="Sets the weather of a region (or the server's own)")
	@gm_only()
	@app_commands.autocomplete(region=region_autocomplete, weather=weather_autocomplete)
	@app_commands.describe(weather="The weather", region="The region (default: the server's weather outside any "
	                                                     "region)")
	async def set_weather(self, interaction: discord.Interaction, weather: str, region: str = None) :
		"""
		Sets the weather by hand. It keeps until the weather would normally change next.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		record = None
		if region :
			record = WorldTransactions().find_region(interaction.guild_id, region)
			if record is None :
				return await reply(interaction, f"There is no region called {region}.")
		climate = record.climate if record else WeatherRules.TEMPERATE
		if WeatherRules.find(climate, weather) is None :
			return await reply(interaction, f"{weather} isn't weather a {climate} climate has.")
		WorldFlow.force_weather(interaction.guild_id, record.id if record else None, climate, weather)
		await interaction.response.send_message(f"{WeatherRules.text(climate, weather)} over "
		                                        f"{record.name if record else 'the land'}.")


async def setup(bot) :
	await bot.add_cog(Weather(bot))
