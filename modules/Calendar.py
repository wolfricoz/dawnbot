"""The in-world calendar: setting it up, holidays and birthdays. In-world time itself is moved with /time.

A calendar comes from a preset (Gregorian, or a fantasy year of twelve 30-day months) or is typed in: months with their
days and seasons, weekday names, an era label and an optional moon. Events and character birthdays are announced in the
announcement channel when their day comes. See design/roleplay-tools.md, section 4.
"""
import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.combat.AutoComplete import AutoComplete
from classes.world import Calendar as CalendarRules
from classes.world.WorldFlow import WorldFlow
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.WorldTransactions import WorldTransactions
from views.combat.Pickers import reply

PRESET_CHOICES = [Choice(name="Gregorian: January to December", value="gregorian"),
                  Choice(name="Fantasy: twelve months of 30 days", value="fantasy"),
                  Choice(name="Custom: type the months yourself", value="custom")]
NO_CALENDAR = "This server has no calendar yet; staff set one up with /calendar setup."


class CustomCalendar(discord.ui.Modal) :
	"""Months and weekdays of a custom calendar."""

	def __init__(self, on_submit, months: str | None = None, weekdays: str | None = None) :
		super().__init__(title="Custom calendar")
		self.handler = on_submit
		self.months = discord.ui.TextInput(label="Months: Name: days: season, one per line",
		                                   style=discord.TextStyle.paragraph, max_length=1500, default=months,
		                                   placeholder="Frostmoon: 30: winter\nThaw: 31: spring")
		self.weekdays = discord.ui.TextInput(label="Weekdays, separated by commas", required=False, max_length=300,
		                                     default=weekdays, placeholder="Moonday, Forgeday, Windsday")
		self.add_item(self.months)
		self.add_item(self.weekdays)

	# ============================================================
	async def on_submit(self, interaction: discord.Interaction) :
		await self.handler(interaction, self.months.value, self.weekdays.value)


@app_commands.guild_only()
class Calendar(commands.GroupCog, name="Calendar", group_name="calendar") :
	"""The in-world calendar: set it up, add holidays and set birthdays."""

	event = app_commands.Group(name="event", description="Holidays and events on the in-world calendar")

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@app_commands.command(name="setup", description="Sets up (or replaces) the server's in-world calendar")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.choices(preset=PRESET_CHOICES)
	@app_commands.describe(preset="A ready-made calendar, or custom to type the months",
	                       year="The starting year", month="The starting month (a number)",
	                       day="The starting day", era="A label after the year, like AR",
	                       moon_cycle="Days from one full moon to the next (0 for no moon)")
	async def setup_calendar(self, interaction: discord.Interaction, preset: Choice[str],
	                         year: app_commands.Range[int, -100000, 100000] = 1,
	                         month: app_commands.Range[int, 1, CalendarRules.MAX_MONTHS] = 1,
	                         day: app_commands.Range[int, 1, CalendarRules.MAX_MONTH_DAYS] = 1,
	                         era: app_commands.Range[str, 1, 32] = None,
	                         moon_cycle: app_commands.Range[int, 0, 400] = None) :
		"""
		Sets up the calendar the server's in-world dates use, starting at the date given (at morning). A custom
		calendar opens a form for the months (`Name: days: season`, one per line; the season can be left out) and the
		weekday names. Setting it up again replaces the calendar and its date; events stay.

		**Permissions:**
		- `Manage Server`
		"""
		guild_id = interaction.guild_id

		async def save(save_interaction: discord.Interaction, preset_name: str | None, months=None, weekdays=None) :
			calendar, problem = WorldFlow.setup(guild_id, preset_name, months, weekdays, era, year, month, day,
			                                    moon_cycle)
			if problem :
				return await reply(save_interaction, problem)
			await reply(save_interaction, f"📅 Calendar set. It is now {WorldFlow.date_line(guild_id)}.")

		if preset.value != "custom" :
			return await save(interaction, preset.value)

		async def typed(form_interaction: discord.Interaction, months_text: str, weekdays_text: str) :
			months, problem = CalendarRules.parse_months(months_text)
			if problem :
				return await reply(form_interaction, problem)
			await save(form_interaction, None, months, CalendarRules.parse_weekdays(weekdays_text))

		current = WorldTransactions().calendar(guild_id)
		await interaction.response.send_modal(CustomCalendar(
			typed, CalendarRules.months_text(current.months) if current else None,
			", ".join(current.weekdays) if current else None))

	# ============================================================
	@app_commands.command(name="view", description="Shows the in-world calendar and today's date")
	async def view(self, interaction: discord.Interaction) :
		"""
		Shows the calendar's months with their days and seasons, the weekdays and today's in-world date.
		"""
		calendar = WorldTransactions().calendar(interaction.guild_id)
		if calendar is None :
			return await reply(interaction, NO_CALENDAR)
		months = "\n".join(f"{index}. **{month['name']}** · {month['days']} days · {month['season']}"
		                   for index, month in enumerate(calendar.months, start=1))
		embed = discord.Embed(title="📅 Calendar", description=WorldFlow.date_line(interaction.guild_id),
		                      colour=discord.Colour.dark_teal())
		embed.add_field(name="Months", value=months[:1024], inline=False)
		if calendar.weekdays :
			embed.add_field(name="Weekdays", value=", ".join(calendar.weekdays)[:1024], inline=False)
		await interaction.response.send_message(embed=embed, ephemeral=True)

	# ============================================================
	@event.command(name="add", description="Adds a holiday or event to the calendar")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.describe(name="What it is called", month="The month (a number)", day="The day",
	                       year="Only in this year (leave empty for every year)", description="What happens")
	async def event_add(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 100],
	                    month: app_commands.Range[int, 1, CalendarRules.MAX_MONTHS],
	                    day: app_commands.Range[int, 1, CalendarRules.MAX_MONTH_DAYS],
	                    year: int = None, description: app_commands.Range[str, 1, 500] = None) :
		"""
		Adds an event, announced in the announcement channel when the in-world date reaches it.

		**Permissions:**
		- `Manage Messages`
		"""
		calendar = WorldTransactions().calendar(interaction.guild_id)
		if calendar is None :
			return await reply(interaction, NO_CALENDAR)
		if not CalendarRules.valid(calendar.months, CalendarRules.Date(year or 1, month, day)) :
			return await reply(interaction, "That day isn't on this server's calendar.")
		if WorldTransactions().find_event(interaction.guild_id, name) is not None :
			return await reply(interaction, f"There already is an event called {name}.")
		WorldTransactions().add_event(interaction.guild_id, name=name, month=month, day=day, year=year,
		                              description=description)
		date = CalendarRules.date_text(calendar.months, CalendarRules.Date(year or calendar.year, month, day),
		                          calendar.era if year else None)
		await reply(interaction, f"🎉 Added **{name}** on {date if year else date.rsplit(',', 1)[0]}"
		                         f"{'' if year else ', every year'}.")

	# ============================================================
	@event.command(name="remove", description="Removes an event from the calendar")
	@app_commands.checks.has_permissions(manage_messages=True)
	async def event_remove(self, interaction: discord.Interaction, name: str) :
		"""
		Removes an event.

		**Permissions:**
		- `Manage Messages`
		"""
		event = WorldTransactions().find_event(interaction.guild_id, name)
		if event is None :
			return await reply(interaction, f"There is no event called {name}.")
		WorldTransactions().delete_event(event.id)
		await reply(interaction, f"Removed **{event.name}**.")

	# ============================================================
	@event.command(name="list", description="Lists the calendar's events")
	async def event_list(self, interaction: discord.Interaction) :
		"""
		Lists the holidays and events on the calendar.
		"""
		calendar = WorldTransactions().calendar(interaction.guild_id)
		events = WorldTransactions().events(interaction.guild_id)
		if calendar is None or not events :
			return await reply(interaction, NO_CALENDAR if calendar is None else "The calendar has no events yet.")
		lines = []
		for event in events :
			month = calendar.months[event.month - 1]["name"] if event.month <= len(calendar.months) else event.month
			when = f"{month} {event.day}" + (f", {event.year}" if event.year is not None else "")
			lines.append(f"**{event.name}** · {when}{f' · {event.description[:80]}' if event.description else ''}")
		await reply(interaction, "\n".join(lines)[:2000])

	# ============================================================
	@app_commands.command(name="birthday", description="Sets your character's in-world birthday")
	@app_commands.autocomplete(character=AutoComplete().character)
	@app_commands.describe(character="Your character", month="The month (a number)", day="The day")
	async def birthday(self, interaction: discord.Interaction, character: str,
	                   month: app_commands.Range[int, 1, CalendarRules.MAX_MONTHS],
	                   day: app_commands.Range[int, 1, CalendarRules.MAX_MONTH_DAYS]) :
		"""
		Sets the in-world day your character was born; it is announced every year when that day comes.
		"""
		calendar = WorldTransactions().calendar(interaction.guild_id)
		if calendar is None :
			return await reply(interaction, NO_CALENDAR)
		record = CharacterTransactions().get(interaction.user.id, interaction.guild_id, character)
		if record is None :
			return await reply(interaction, f"You have no character called {character}.")
		if not CalendarRules.valid(calendar.months, CalendarRules.Date(1, month, day)) :
			return await reply(interaction, "That day isn't on this server's calendar.")
		CharacterTransactions().update(record.id, birthday={"month" : month, "day" : day})
		name = calendar.months[month - 1]["name"]
		note = "" if record.state == APPROVED else " It is announced once the character is approved."
		await reply(interaction, f"🎂 {record.name}'s birthday is {name} {day}.{note}")


async def setup(bot) :
	await bot.add_cog(Calendar(bot))
