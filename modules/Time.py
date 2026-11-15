"""In-world time: what day and time it is, and moving it. With TIME_FLOW set to a ratio (/config roleplay), time also
moves by itself. Events and birthdays on the days passed are announced. See design/roleplay-tools.md, section 4.
"""
import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.kernel.GMRole import gm_only
from classes.world import Calendar, Weather
from classes.world.Calendar import Date
from classes.world.WorldFlow import WorldFlow
from views.combat.Pickers import reply

UNIT_CHOICES = [Choice(name=f"{unit.capitalize()}s" if unit != "part" else "Parts of the day (6 per day)", value=unit)
                for unit in Calendar.UNITS]
PART_CHOICES = [Choice(name=part.capitalize(), value=index) for index, part in enumerate(Calendar.PARTS)]
NO_CALENDAR = "This server has no calendar yet; staff set one up with /calendar setup."


# ============================================================
def weather_line(guild_id: int, channel) -> str :
	location = WorldFlow.location_here(channel)
	climate, key = WorldFlow.weather(guild_id, location)
	where = f" at {location.name}" if location else ""
	return f"Weather{where}: {Weather.text(climate, key)}"


@app_commands.guild_only()
class Time(commands.GroupCog, name="Time", group_name="time") :
	"""In-world time: see the date and time, and move it forward or back."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@app_commands.command(name="now", description="Shows the in-world date, time, season and weather")
	async def now(self, interaction: discord.Interaction) :
		"""
		Shows the in-world date and time of day, the season, the moon, and the weather where this channel is.
		"""
		line = WorldFlow.date_line(interaction.guild_id)
		if line is None :
			return await reply(interaction, NO_CALENDAR)
		await interaction.response.send_message(f"{line}\n{weather_line(interaction.guild_id, interaction.channel)}",
		                                        ephemeral=True)

	# ============================================================
	@app_commands.command(name="advance", description="Moves in-world time forward (or back with a negative amount)")
	@gm_only()
	@app_commands.choices(unit=UNIT_CHOICES)
	@app_commands.describe(amount="How much; negative moves time back", unit="Parts of the day, days, weeks, months "
	                                                                          "or years")
	async def advance(self, interaction: discord.Interaction, amount: app_commands.Range[int, -1000, 1000],
	                  unit: Choice[str]) :
		"""
		Moves in-world time. Events and birthdays on the days passed (up to a week of them) are announced in the
		announcement channel.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		moved = WorldFlow.move(interaction.guild_id, amount, unit.value)
		if moved is None :
			return await reply(interaction, NO_CALENDAR)
		_, _, lines = moved
		await interaction.response.send_message(f"⏳ Time moves on. It is now {WorldFlow.date_line(interaction.guild_id)}.")
		await WorldFlow.announce(interaction.client, interaction.guild_id, lines)

	# ============================================================
	@app_commands.command(name="set", description="Sets the in-world date and time of day")
	@gm_only()
	@app_commands.choices(part=PART_CHOICES)
	@app_commands.describe(year="The year", month="The month (a number)", day="The day", part="The time of day")
	async def set_date(self, interaction: discord.Interaction, year: app_commands.Range[int, -100000, 100000],
	                   month: app_commands.Range[int, 1, Calendar.MAX_MONTHS],
	                   day: app_commands.Range[int, 1, Calendar.MAX_MONTH_DAYS], part: Choice[int] = None) :
		"""
		Jumps to a date without announcing the events in between.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		problem = WorldFlow.set_date(interaction.guild_id, Date(year, month, day, part.value if part else 1))
		if problem :
			return await reply(interaction, problem)
		await interaction.response.send_message(f"📅 It is now {WorldFlow.date_line(interaction.guild_id)}.")


async def setup(bot) :
	await bot.add_cog(Time(bot))
