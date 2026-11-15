"""The world's moving parts (design/roleplay-tools.md, sections 4 and 5): the server's calendar and moving time, the
events and birthdays a new day brings, the weather where a channel is, who is at a location, and travel.
"""
import logging
import random
from datetime import datetime, timedelta, timezone

import discord

from classes.combat import Rules
from classes.combat.Rules import Bonus
from classes.kernel import RoleplaySettings
from classes.world import Calendar, Weather
from classes.world.Calendar import Date
from database.database import Calendars, Locations
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.ProxyTransactions import ProxyTransactions
from database.transactions.WorldTransactions import WorldTransactions
from resources.configs.ConfigMapping import ConfigMapping

# A long stretch of moved time announces at most this many days of events and birthdays.
MAX_ANNOUNCED_DAYS = 7
# The real months' seasons, for weather on servers without a calendar.
REAL_SEASONS = {12 : "winter", 1 : "winter", 2 : "winter", 3 : "spring", 4 : "spring", 5 : "spring", 6 : "summer",
                7 : "summer", 8 : "summer", 9 : "autumn", 10 : "autumn", 11 : "autumn"}


class WorldFlow :

	# == calendar ==

	# ============================================================
	@staticmethod
	def today(calendar: Calendars) -> Date :
		return Date(calendar.year, calendar.month, calendar.day, calendar.part)

	# ============================================================
	@staticmethod
	def date_line(guild_id: int) -> str | None :
		"""The in-world date and time, or None without a calendar."""
		calendar = WorldTransactions().calendar(guild_id)
		if calendar is None :
			return None
		return Calendar.full_text(calendar.months, calendar.weekdays, WorldFlow.today(calendar), calendar.era,
		                          calendar.moon_cycle)

	# ============================================================
	@staticmethod
	def short_date(guild_id: int) -> str | None :
		"""`Seedtide 12, 1203 AR`, or None without a calendar."""
		calendar = WorldTransactions().calendar(guild_id)
		if calendar is None :
			return None
		return Calendar.date_text(calendar.months, WorldFlow.today(calendar), calendar.era)

	# ============================================================
	@staticmethod
	def world_date(guild_id: int) -> dict | None :
		"""The in-world date as {"year", "month", "day", "part", "text"}, for records."""
		calendar = WorldTransactions().calendar(guild_id)
		if calendar is None :
			return None
		today = WorldFlow.today(calendar)
		return {"year" : today.year, "month" : today.month, "day" : today.day, "part" : today.part,
		        "text" : Calendar.date_text(calendar.months, today, calendar.era)}

	# ============================================================
	@staticmethod
	def setup(guild_id: int, preset: str | None, months: list[dict] | None = None, weekdays: list[str] | None = None,
	          era: str | None = None, year: int = 1, month: int = 1, day: int = 1,
	          moon_cycle: int | None = None) -> tuple[Calendars | None, str | None] :
		"""Sets up (or replaces) the server's calendar. Returns it, or None and the problem."""
		if preset :
			data = Calendar.PRESETS.get(preset)
			if data is None :
				return None, f"There is no calendar preset called {preset}."
			months = months or data["months"]
			weekdays = weekdays if weekdays is not None else data["weekdays"]
			era = era if era is not None else data["era"]
			moon_cycle = moon_cycle if moon_cycle is not None else data["moon_cycle"]
		if not months :
			return None, "The calendar needs months."
		date = Date(year, month, day, 1)
		if not Calendar.valid(months, date) :
			return None, f"{year}-{month}-{day} is not a date on that calendar."
		calendar = WorldTransactions().save_calendar(guild_id, preset=preset or "custom", months=months,
		                                             weekdays=weekdays or [], era=(era or None),
		                                             year=year, month=month, day=day, part=1,
		                                             moon_cycle=moon_cycle or None,
		                                             last_tick=datetime.now(timezone.utc))
		return calendar, None

	# ============================================================
	@staticmethod
	def move(guild_id: int, amount: int, unit: str) -> tuple[Date, Date, list[str]] | None :
		"""Moves the server's in-world time. Returns the old and new date and what the new days bring (events and
		birthdays), or None without a calendar."""
		calendar = WorldTransactions().calendar(guild_id)
		if calendar is None :
			return None
		old = WorldFlow.today(calendar)
		new = Calendar.advance(calendar.months, calendar.weekdays, old, amount, unit)
		WorldTransactions().save_calendar(guild_id, year=new.year, month=new.month, day=new.day, part=new.part)
		return old, new, WorldFlow.new_days(guild_id, calendar, old, new)

	# ============================================================
	@staticmethod
	def set_date(guild_id: int, date: Date) -> str | None :
		"""Sets the in-world date. Returns the problem, or None."""
		calendar = WorldTransactions().calendar(guild_id)
		if calendar is None :
			return "This server has no calendar yet; set one up with /calendar setup."
		if not Calendar.valid(calendar.months, date) :
			return "That date isn't on this server's calendar."
		WorldTransactions().save_calendar(guild_id, year=date.year, month=date.month, day=date.day, part=date.part)
		return None

	# ============================================================
	@staticmethod
	def new_days(guild_id: int, calendar: Calendars, old: Date, new: Date) -> list[str] :
		"""The events and birthdays of the days from the day after old up to new (at most a week of them)."""
		start, end = Calendar.ordinal(calendar.months, old) + 1, Calendar.ordinal(calendar.months, new)
		if end < start :
			return []
		lines = []
		characters = None
		for number in range(max(start, end - MAX_ANNOUNCED_DAYS + 1), end + 1) :
			date = Calendar.from_ordinal(calendar.months, number)
			for event in WorldTransactions().events(guild_id) :
				if event.month != date.month or event.day != date.day :
					continue
				if event.year is not None and event.year != date.year :
					continue
				if event.last_year == date.year :
					continue
				WorldTransactions().update_event(event.id, last_year=date.year)
				lines.append(f"🎉 **{event.name}** ({Calendar.date_text(calendar.months, date, calendar.era)})"
				             f"{f': {event.description}' if event.description else ''}")
			if characters is None :
				characters = [character for character in CharacterTransactions().get_in_guild(guild_id)
				              if character.state == APPROVED and character.birthday]
			for character in characters :
				if character.birthday.get("month") == date.month and character.birthday.get("day") == date.day :
					lines.append(f"🎂 It is **{character.name}**'s birthday (<@{character.uid}>)!")
		return lines

	# ============================================================
	@staticmethod
	def tick(guild_id: int, now: datetime | None = None) -> list[str] | None :
		"""Moves flowing time for one server. Returns what new days bring, or None when time didn't move."""
		now = now or datetime.now(timezone.utc)
		calendar = WorldTransactions().calendar(guild_id)
		if calendar is None :
			return None
		ratio = Calendar.flow_ratio(RoleplaySettings.text(guild_id, ConfigMapping.TIME_FLOW))
		if ratio is None :
			return None
		last = calendar.last_tick or now
		parts = Calendar.parts_elapsed(ratio, (now - last).total_seconds() / 3600)
		if parts <= 0 :
			if calendar.last_tick is None :
				WorldTransactions().save_calendar(guild_id, last_tick=now)
			return None
		consumed = timedelta(hours=parts * Calendar.real_hours_per_part(ratio))
		old = WorldFlow.today(calendar)
		new = Calendar.advance(calendar.months, calendar.weekdays, old, parts, "part")
		WorldTransactions().save_calendar(guild_id, year=new.year, month=new.month, day=new.day, part=new.part,
		                                  last_tick=last + consumed)
		return WorldFlow.new_days(guild_id, calendar, old, new)

	# == weather ==

	# ============================================================
	@staticmethod
	def season(guild_id: int, now: datetime | None = None) -> str :
		calendar = WorldTransactions().calendar(guild_id)
		if calendar is None :
			return REAL_SEASONS[(now or datetime.now(timezone.utc)).month]
		return Calendar.season(calendar.months, WorldFlow.today(calendar))

	# ============================================================
	@staticmethod
	def climate_of(location: Locations | None, region=None) -> str :
		if location is not None and location.indoor :
			return Weather.NONE
		if location is not None and location.climate :
			return location.climate
		if region is not None :
			return region.climate
		return Weather.TEMPERATE

	# ============================================================
	@staticmethod
	def weather(guild_id: int, location: Locations | None = None, now: datetime | None = None,
	            rng: random.Random | None = None) -> tuple[str, str] :
		"""The weather at a location (or the server's own weather): (climate, weather key). Rolled again when it is
		stale: once per in-world day when time flows, otherwise every WEATHER_HOURS real hours."""
		now = now or datetime.now(timezone.utc)
		region = WorldTransactions().region(location.region_id) if location is not None else None
		climate = WorldFlow.climate_of(location, region)
		if climate == Weather.NONE :
			return Weather.NONE, "indoors"
		# The region's weather follows the region's climate; a location with its own climate gets its own reading.
		region_climate = region.climate if region is not None else (location.climate if location and location.climate
		                                                            else Weather.TEMPERATE)
		state = WorldTransactions().weather(guild_id, region.id if region else None)
		calendar = WorldTransactions().calendar(guild_id)
		flowing = calendar is not None and \
		          Calendar.flow_ratio(RoleplaySettings.text(guild_id, ConfigMapping.TIME_FLOW)) is not None
		world_day = Calendar.ordinal(calendar.months, WorldFlow.today(calendar)) if calendar else None
		stale = state is None or state.climate != region_climate
		if not stale and flowing :
			stale = state.world_day != world_day
		elif not stale :
			hours = RoleplaySettings.number(guild_id, ConfigMapping.WEATHER_HOURS)
			since = state.since if state.since.tzinfo else state.since.replace(tzinfo=timezone.utc)
			stale = now - since >= timedelta(hours=hours)
		if stale :
			key = Weather.roll(region_climate, WorldFlow.season(guild_id, now),
			                   state.weather if state and state.climate == region_climate else None, rng)
			state = WorldTransactions().save_weather(guild_id, region.id if region else None, climate=region_climate,
			                                         weather=key, forced=False, world_day=world_day, since=now)
		if climate != region_climate :
			# A location whose climate differs from its region's: read the region's weather on its own ladder by
			# position, so a storm in the region is still foul weather here.
			ladder, own = Weather.keys(region_climate), Weather.keys(climate)
			position = ladder.index(state.weather) / max(1, len(ladder) - 1) if state.weather in ladder else 0.3
			return climate, own[round(position * (len(own) - 1))]
		return climate, state.weather

	# ============================================================
	@staticmethod
	def force_weather(guild_id: int, region_id: int | None, climate: str, key: str) -> None :
		calendar = WorldTransactions().calendar(guild_id)
		world_day = Calendar.ordinal(calendar.months, WorldFlow.today(calendar)) if calendar else None
		WorldTransactions().save_weather(guild_id, region_id, climate=climate, weather=key, forced=True,
		                                 world_day=world_day, since=datetime.now(timezone.utc))

	# == locations ==

	# ============================================================
	@staticmethod
	def location_here(channel) -> Locations | None :
		"""The location of a channel, or of the channel a thread is in."""
		if channel is None :
			return None
		location = WorldTransactions().location_of(channel.id)
		parent_id = getattr(channel, "parent_id", None)
		if location is None and parent_id :
			location = WorldTransactions().location_of(parent_id)
		return location

	# ============================================================
	@staticmethod
	def location_by_ids(channel_id: int | None, parent_id: int | None = None) -> Locations | None :
		location = WorldTransactions().location_of(channel_id)
		if location is None and parent_id :
			location = WorldTransactions().location_of(parent_id)
		return location

	# ============================================================
	@staticmethod
	def check_bonus(guild_id: int, channel_id: int | None, parent_id: int | None, stat: str) -> Bonus | None :
		"""The weather's modifier on a check rolled in a channel, when weather effects are on and it is outdoors."""
		if not RoleplaySettings.toggle(guild_id, ConfigMapping.WEATHER_EFFECTS) :
			return None
		location = WorldFlow.location_by_ids(channel_id, parent_id)
		if location is None or location.indoor :
			return None
		climate, key = WorldFlow.weather(guild_id, location)
		value = Weather.modifier(climate, key, stat)
		if not value :
			return None
		kind = Weather.find(climate, key)
		return Bonus(f"Weather ({kind.name if kind else key})", value)

	# ============================================================
	@staticmethod
	def presence(guild: discord.Guild) -> dict[int, Locations] :
		"""Where each character is: the location of its last post, if that was in the last PRESENCE_DAYS days."""
		since = datetime.now(timezone.utc) - timedelta(days=RoleplaySettings.number(guild.id,
		                                                                            ConfigMapping.PRESENCE_DAYS))
		found = {}
		for character_id, channel_id in ProxyTransactions().last_channels(guild.id, since).items() :
			channel = guild.get_channel_or_thread(channel_id)
			location = WorldTransactions().location_of(channel_id)
			if location is None and channel is not None :
				location = WorldFlow.location_here(channel)
			if location is not None :
				found[character_id] = location
		return found

	# ============================================================
	@staticmethod
	def who_is_at(guild: discord.Guild, location: Locations) -> list :
		characters = []
		for character_id, place in WorldFlow.presence(guild).items() :
			if place.id != location.id :
				continue
			character = CharacterTransactions().get_by_id(character_id)
			if character is not None and character.state == APPROVED :
				characters.append(character)
		return characters

	# ============================================================
	@staticmethod
	def where_is(guild: discord.Guild, character_id: int) -> Locations | None :
		return WorldFlow.presence(guild).get(character_id)

	# == travel ==

	# ============================================================
	@staticmethod
	def encounter_roll(luck: int, danger: int, base: int = 5, rng: random.Random | None = None) -> tuple[int, int,
	bool] :
		"""`d20 + Luck modifier` against `8 + 2 × danger`. Returns the natural roll, the total and whether there is an
		encounter (the roll failed). No danger means no roll and no encounter."""
		if danger <= 0 :
			return 0, 0, False
		natural = (rng or random).randint(1, 20)
		total = natural + Rules.modifier(luck, base)
		return natural, total, total < 8 + 2 * danger

	# ============================================================
	@staticmethod
	def arrival_time(guild_id: int, hours: int, now: datetime | None = None) -> datetime :
		"""When a journey of hours in-world hours ends in real time: right away with manual time, otherwise scaled by
		TIME_FLOW."""
		now = now or datetime.now(timezone.utc)
		ratio = Calendar.flow_ratio(RoleplaySettings.text(guild_id, ConfigMapping.TIME_FLOW))
		if ratio is None or hours <= 0 :
			return now
		return now + timedelta(hours=hours / ratio)

	# ============================================================
	@staticmethod
	async def announce(bot: discord.Client, guild_id: int, lines: list[str]) -> None :
		"""Posts a new day's events and birthdays to the announcement channel."""
		if not lines :
			return
		from classes.kernel.ConfigData import ConfigData

		guild = bot.get_guild(guild_id)
		if guild is None :
			return
		channel = await ConfigData().get_channel(guild, ConfigMapping.ANNOUNCEMENT, optional=True)
		if channel is None :
			return
		try :
			await channel.send("\n".join(lines)[:2000], allowed_mentions=discord.AllowedMentions(users=True))
		except discord.HTTPException as e :
			logging.warning(f"Could not announce the new day in {guild.name}: {e}")
