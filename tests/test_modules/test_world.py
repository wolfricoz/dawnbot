import random
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from classes.kernel.ConfigData import ConfigData
from classes.world import Calendar, Weather
from classes.world.Calendar import Date
from classes.world.WorldFlow import WorldFlow
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.ProxyTransactions import ProxyTransactions
from database.transactions.WorldTransactions import WorldTransactions
from resources.configs.ConfigMapping import ConfigMapping
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID

GREGORIAN = Calendar.PRESETS["gregorian"]
MONTHS, WEEKDAYS = GREGORIAN["months"], GREGORIAN["weekdays"]


class FixedRng :
	def __init__(self, *values) :
		self.values = list(values)

	def randint(self, low, high) :
		return self.values.pop(0)


class TestCalendar(unittest.TestCase) :

	def test_ordinals_round_trip(self) :
		for date in (Date(2026, 1, 1), Date(2026, 3, 1), Date(2026, 12, 31), Date(-3, 7, 15), Date(0, 1, 1)) :
			self.assertEqual(Calendar.from_ordinal(MONTHS, Calendar.ordinal(MONTHS, date)), date)
		self.assertEqual(Calendar.year_length(MONTHS), 365)

	def test_advance(self) :
		date = Date(2026, 1, 31, 5)
		self.assertEqual(Calendar.advance(MONTHS, WEEKDAYS, date, 1, "part"), Date(2026, 2, 1, 0))
		self.assertEqual(Calendar.advance(MONTHS, WEEKDAYS, date, -6, "part"), Date(2026, 1, 30, 5))
		self.assertEqual(Calendar.advance(MONTHS, WEEKDAYS, date, 1, "day"), Date(2026, 2, 1, 5))
		self.assertEqual(Calendar.advance(MONTHS, WEEKDAYS, date, 2, "week"), Date(2026, 2, 14, 5))
		self.assertEqual(Calendar.advance(MONTHS, WEEKDAYS, date, 1, "month"), Date(2026, 2, 28, 5))
		self.assertEqual(Calendar.advance(MONTHS, WEEKDAYS, date, -2, "month"), Date(2025, 11, 30, 5))
		self.assertEqual(Calendar.advance(MONTHS, WEEKDAYS, date, 3, "year"), Date(2029, 1, 31, 5))

	def test_weekday_season_and_moon(self) :
		monday = Date(2026, 1, 5)
		day_after = Calendar.advance(MONTHS, WEEKDAYS, monday, 1, "day")
		self.assertEqual(WEEKDAYS.index(Calendar.weekday(MONTHS, WEEKDAYS, day_after)),
		                 (WEEKDAYS.index(Calendar.weekday(MONTHS, WEEKDAYS, monday)) + 1) % 7)
		self.assertEqual(Calendar.season(MONTHS, Date(2026, 7, 1)), "summer")
		self.assertIsNone(Calendar.moon(None, 10))
		self.assertEqual(Calendar.moon(28, 0)[1], "New moon")
		self.assertEqual(Calendar.moon(28, 14)[1], "Full moon")
		text = Calendar.full_text(MONTHS, WEEKDAYS, Date(2026, 7, 4, 1), "AD", 29)
		self.assertIn("Morning", text)
		self.assertIn("July 4, 2026 AD", text)
		self.assertIn("Summer", text)

	def test_custom_months(self) :
		months, problem = Calendar.parse_months("Frost: 30: winter\nThaw: 31\nSun: 20: summer\nFall: 10")
		self.assertIsNone(problem)
		self.assertEqual([month["days"] for month in months], [30, 31, 20, 10])
		self.assertEqual(months[1]["season"], "summer")
		self.assertEqual(months[3]["season"], "winter")
		self.assertIsNotNone(Calendar.parse_months("Frost")[1])
		self.assertIsNotNone(Calendar.parse_months("Frost: 0")[1])
		self.assertIsNotNone(Calendar.parse_months("Frost: 10: monsoon")[1])
		self.assertIsNotNone(Calendar.parse_months("")[1])
		self.assertEqual(Calendar.parse_weekdays(" a, b ,, c"), ["a", "b", "c"])
		self.assertEqual(Calendar.parse_months(Calendar.months_text(MONTHS))[0], MONTHS)

	def test_flow(self) :
		self.assertIsNone(Calendar.flow_ratio("manual"))
		self.assertEqual(Calendar.flow_ratio("2:1"), 2)
		self.assertEqual(Calendar.flow_ratio("1:4"), 0.25)
		self.assertEqual(Calendar.parts_elapsed(1, 24), 6)
		self.assertEqual(Calendar.parts_elapsed(1, 3.9), 0)
		self.assertEqual(Calendar.real_hours_per_part(2), 2)


class TestWeather(unittest.TestCase) :

	def test_steps_stay_next_to_the_current_weather(self) :
		rng = random.Random(3)
		keys = Weather.keys(Weather.TEMPERATE)
		current = "rain"
		for _ in range(300) :
			following = Weather.roll(Weather.TEMPERATE, "autumn", current, rng)
			self.assertLessEqual(abs(keys.index(following) - keys.index(current)), 1)
			current = following

	def test_seasons_rule_out_weather(self) :
		rng = random.Random(5)
		summer = {Weather.roll(Weather.TEMPERATE, "summer", None, rng) for _ in range(300)}
		self.assertNotIn("blizzard", summer)
		self.assertNotIn("snow", summer)
		# A blizzard in summer has no fitting neighbours, so any summer weather can follow.
		self.assertIn(Weather.roll(Weather.TEMPERATE, "summer", "blizzard", rng), Weather.keys(Weather.TEMPERATE))

	def test_effects(self) :
		self.assertEqual(Weather.modifier(Weather.TEMPERATE, "fog", "perception"), -2)
		self.assertEqual(Weather.modifier(Weather.TEMPERATE, "fog", "strength"), 0)
		self.assertIn("-2 Perception", Weather.text(Weather.TEMPERATE, "fog"))
		self.assertEqual(Weather.text(Weather.NONE, "indoors"), "🏠 Indoors")
		for climate in Weather.CLIMATES :
			for season in Weather.ALL :
				self.assertIn(Weather.roll(climate, season, None, random.Random(1)), Weather.keys(climate))


class TestWorld(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()

	def test_setup_and_move(self) :
		calendar, problem = WorldFlow.setup(GUILD_ID, "fantasy", year=1203, month=3, day=12)
		self.assertIsNone(problem)
		self.assertIn("Seedtide 12, 1203 AR", WorldFlow.date_line(GUILD_ID))
		self.assertIsNotNone(WorldFlow.setup(GUILD_ID, "fantasy", month=3, day=31)[1])
		WorldTransactions().add_event(GUILD_ID, name="Feast", month=3, day=14, description="Pies")
		character = self.add_character(birthday={"month" : 3, "day" : 13})
		old, new, lines = WorldFlow.move(GUILD_ID, 2, "day")
		self.assertEqual((new.month, new.day), (3, 14))
		self.assertEqual(len(lines), 2)
		self.assertTrue(any("Feast" in line for line in lines))
		self.assertTrue(any(character.name in line for line in lines))
		# Moving back and forward again doesn't announce the feast twice in the same year.
		WorldFlow.move(GUILD_ID, -1, "day")
		lines = WorldFlow.move(GUILD_ID, 1, "day")[2]
		self.assertFalse(any("Feast" in line for line in lines))
		self.assertIsNone(WorldFlow.set_date(GUILD_ID, Date(1210, 1, 1, 0)))
		self.assertIsNotNone(WorldFlow.set_date(GUILD_ID, Date(1210, 13, 1, 0)))

	def test_flowing_time(self) :
		start = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
		WorldFlow.setup(GUILD_ID, "gregorian", year=2026, month=1, day=1)
		WorldTransactions().save_calendar(GUILD_ID, last_tick=start)
		self.assertIsNone(WorldFlow.tick(GUILD_ID, start + timedelta(hours=10)))
		ConfigData().add_key(GUILD_ID, ConfigMapping.TIME_FLOW, "2:1", overwrite=True)
		WorldFlow.tick(GUILD_ID, start + timedelta(hours=13))
		calendar = WorldTransactions().calendar(GUILD_ID)
		# 13 real hours at 2 days a day is 6.5 parts: 6 move (a full day), the half part waits.
		self.assertEqual((calendar.day, calendar.part), (2, 1))
		self.assertEqual(calendar.last_tick, start + timedelta(hours=12))

	def test_weather_keeps_until_stale(self) :
		now = datetime(2026, 7, 1, tzinfo=timezone.utc)
		first = WorldFlow.weather(GUILD_ID, None, now, random.Random(1))
		self.assertEqual(first, WorldFlow.weather(GUILD_ID, None, now + timedelta(hours=11), random.Random(2)))
		state = WorldTransactions().weather(GUILD_ID, None)
		WorldFlow.weather(GUILD_ID, None, now + timedelta(hours=13), random.Random(2))
		self.assertGreater(WorldTransactions().weather(GUILD_ID, None).since, state.since)
		inside = WorldTransactions().save_location(GUILD_ID, 10, name="Tavern", indoor=True)
		self.assertEqual(WorldFlow.weather(GUILD_ID, inside, now), (Weather.NONE, "indoors"))

	def test_check_bonus(self) :
		region = WorldTransactions().add_region(GUILD_ID, "Moors", climate=Weather.TEMPERATE)
		outside = WorldTransactions().save_location(GUILD_ID, 20, name="Moor", region_id=region.id)
		inside = WorldTransactions().save_location(GUILD_ID, 21, name="Hut", region_id=region.id, indoor=True)
		WorldFlow.force_weather(GUILD_ID, region.id, Weather.TEMPERATE, "fog")
		bonus = WorldFlow.check_bonus(GUILD_ID, 20, None, "perception")
		self.assertEqual(bonus.value, -2)
		self.assertIsNone(WorldFlow.check_bonus(GUILD_ID, 20, None, "strength"))
		self.assertIsNone(WorldFlow.check_bonus(GUILD_ID, 21, None, "perception"))
		# A thread in the location's channel counts as the location.
		self.assertEqual(WorldFlow.check_bonus(GUILD_ID, 999, 20, "perception").value, -2)
		ConfigData().add_key(GUILD_ID, ConfigMapping.WEATHER_EFFECTS, "DISABLED", overwrite=True)
		self.assertIsNone(WorldFlow.check_bonus(GUILD_ID, 20, None, "perception"))
		self.assertIsNotNone(outside)
		self.assertIsNotNone(inside)

	def test_presence(self) :
		square = WorldTransactions().save_location(GUILD_ID, 30, name="Square")
		WorldTransactions().save_location(GUILD_ID, 31, name="Docks")
		walker = self.add_character("Walker")
		sitter = self.add_character("Sitter")
		ProxyTransactions().log([1], walker.id, USER_ID, GUILD_ID, 31, 400, True, 1, 1)
		ProxyTransactions().log([2], walker.id, USER_ID, GUILD_ID, 30, 400, True, 1, 1)
		ProxyTransactions().log([3], sitter.id, USER_ID, GUILD_ID, 31, 400, True, 1, 1)
		guild = SimpleNamespace(id=GUILD_ID, get_channel_or_thread=lambda channel_id : None)
		self.assertEqual([character.name for character in WorldFlow.who_is_at(guild, square)], ["Walker"])
		self.assertEqual(WorldFlow.where_is(guild, sitter.id).name, "Docks")
		CharacterTransactions().update(walker.id, state="retired")
		self.assertEqual(WorldFlow.who_is_at(guild, square), [])

	def test_routes(self) :
		town = WorldTransactions().save_location(GUILD_ID, 40, name="Town")
		woods = WorldTransactions().save_location(GUILD_ID, 41, name="Woods")
		cave = WorldTransactions().save_location(GUILD_ID, 42, name="Cave")
		WorldTransactions().add_route(GUILD_ID, town.id, woods.id, hours=6, danger=2, two_way=True)
		WorldTransactions().add_route(GUILD_ID, woods.id, cave.id, hours=1, danger=4, two_way=False)
		self.assertEqual(WorldTransactions().route(woods.id, town.id).hours, 6)
		self.assertIsNotNone(WorldTransactions().route(woods.id, cave.id))
		self.assertIsNone(WorldTransactions().route(cave.id, woods.id))

	def test_encounters_and_arrival(self) :
		self.assertEqual(WorldFlow.encounter_roll(5, 0), (0, 0, False))
		# Danger 3: 14 to pass. Luck 7 adds 2.
		self.assertEqual(WorldFlow.encounter_roll(7, 3, rng=FixedRng(12)), (12, 14, False))
		self.assertEqual(WorldFlow.encounter_roll(7, 3, rng=FixedRng(11)), (11, 13, True))
		now = datetime(2026, 1, 1, tzinfo=timezone.utc)
		self.assertEqual(WorldFlow.arrival_time(GUILD_ID, 12, now), now)
		ConfigData().add_key(GUILD_ID, ConfigMapping.TIME_FLOW, "4:1", overwrite=True)
		self.assertEqual(WorldFlow.arrival_time(GUILD_ID, 12, now), now + timedelta(hours=3))
		character = self.add_character()
		town = WorldTransactions().save_location(GUILD_ID, 50, name="Town")
		WorldTransactions().add_travel(GUILD_ID, character.id, None, town.id, now + timedelta(hours=1))
		self.assertIsNotNone(WorldTransactions().travelling(character.id))
		self.assertEqual(WorldTransactions().arrivals(now), [])
		self.assertEqual(len(WorldTransactions().arrivals(now + timedelta(hours=2))), 1)
