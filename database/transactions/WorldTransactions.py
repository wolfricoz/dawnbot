from datetime import datetime

from sqlalchemy import Select, func, or_

from database.database import CalendarEvents, Calendars, Locations, Regions, Routes, Travels, WeatherStates
from database.transactions.DatabaseTransactions import DatabaseTransactions


class WorldTransactions(DatabaseTransactions) :
	"""The in-world calendar and its events, regions, locations, routes, weather and travellers."""

	# == generic ==

	# ============================================================
	def _get(self, model, record_id: int | None) :
		if record_id is None :
			return None
		with self.createsession() as session :
			return session.scalar(Select(model).where(model.id == record_id))

	# ============================================================
	def _add(self, model, **fields) :
		with self.createsession() as session :
			record = model(**{key : value for key, value in fields.items() if hasattr(model, key)})
			session.add(record)
			self.commit(session)
			return record if record.id is not None else None

	# ============================================================
	def _update(self, model, record_id: int, **fields) :
		with self.createsession() as session :
			record = session.scalar(Select(model).where(model.id == record_id))
			if record is None :
				return None
			for key, value in fields.items() :
				if hasattr(model, key) and key != "id" :
					setattr(record, key, value)
			self.commit(session)
			return record

	# ============================================================
	def _delete(self, model, record_id: int) -> bool :
		with self.createsession() as session :
			record = session.scalar(Select(model).where(model.id == record_id))
			if record is None :
				return False
			session.delete(record)
			self.commit(session)
			return True

	# == calendar ==

	# ============================================================
	def calendar(self, guild_id: int) -> Calendars | None :
		with self.createsession() as session :
			return session.scalar(Select(Calendars).where(Calendars.guild_id == guild_id))

	# ============================================================
	def calendars(self) -> list[Calendars] :
		with self.createsession() as session :
			return list(session.scalars(Select(Calendars)).all())

	# ============================================================
	def save_calendar(self, guild_id: int, **fields) -> Calendars | None :
		"""Creates the server's calendar or changes it."""
		current = self.calendar(guild_id)
		if current is None :
			return self._add(Calendars, guild_id=guild_id, **fields)
		return self._update(Calendars, current.id, **fields)

	# ============================================================
	def events(self, guild_id: int) -> list[CalendarEvents] :
		with self.createsession() as session :
			return list(session.scalars(Select(CalendarEvents).where(CalendarEvents.guild_id == guild_id)
			                            .order_by(CalendarEvents.month, CalendarEvents.day)).all())

	# ============================================================
	def add_event(self, guild_id: int, **fields) -> CalendarEvents | None :
		return self._add(CalendarEvents, guild_id=guild_id, **fields)

	# ============================================================
	def update_event(self, event_id: int, **fields) -> CalendarEvents | None :
		return self._update(CalendarEvents, event_id, **fields)

	# ============================================================
	def find_event(self, guild_id: int, name: str) -> CalendarEvents | None :
		with self.createsession() as session :
			return session.scalar(Select(CalendarEvents).where(CalendarEvents.guild_id == guild_id,
			                                                   func.lower(CalendarEvents.name) == name.lower()))

	# ============================================================
	def delete_event(self, event_id: int) -> bool :
		return self._delete(CalendarEvents, event_id)

	# == regions ==

	# ============================================================
	def regions(self, guild_id: int) -> list[Regions] :
		with self.createsession() as session :
			return list(session.scalars(Select(Regions).where(Regions.guild_id == guild_id)
			                            .order_by(func.lower(Regions.name))).all())

	# ============================================================
	def region(self, region_id: int | None) -> Regions | None :
		return self._get(Regions, region_id)

	# ============================================================
	def find_region(self, guild_id: int, name: str) -> Regions | None :
		with self.createsession() as session :
			return session.scalar(Select(Regions).where(Regions.guild_id == guild_id,
			                                            func.lower(Regions.name) == (name or "").strip().lower()))

	# ============================================================
	def add_region(self, guild_id: int, name: str, **fields) -> Regions | None :
		if self.find_region(guild_id, name) is not None :
			return None
		return self._add(Regions, guild_id=guild_id, name=name, **fields)

	# ============================================================
	def update_region(self, region_id: int, **fields) -> Regions | None :
		return self._update(Regions, region_id, **fields)

	# ============================================================
	def delete_region(self, region_id: int) -> bool :
		return self._delete(Regions, region_id)

	# == locations ==

	# ============================================================
	def locations(self, guild_id: int) -> list[Locations] :
		with self.createsession() as session :
			return list(session.scalars(Select(Locations).where(Locations.guild_id == guild_id)
			                            .order_by(func.lower(Locations.name))).all())

	# ============================================================
	def location(self, location_id: int | None) -> Locations | None :
		return self._get(Locations, location_id)

	# ============================================================
	def location_of(self, channel_id: int | None) -> Locations | None :
		if channel_id is None :
			return None
		with self.createsession() as session :
			return session.scalar(Select(Locations).where(Locations.channel_id == channel_id))

	# ============================================================
	def save_location(self, guild_id: int, channel_id: int, **fields) -> Locations | None :
		current = self.location_of(channel_id)
		if current is None :
			return self._add(Locations, guild_id=guild_id, channel_id=channel_id, **fields)
		return self._update(Locations, current.id, **fields)

	# ============================================================
	def delete_location(self, location_id: int) -> bool :
		return self._delete(Locations, location_id)

	# == routes ==

	# ============================================================
	def routes(self, guild_id: int) -> list[Routes] :
		with self.createsession() as session :
			return list(session.scalars(Select(Routes).where(Routes.guild_id == guild_id).order_by(Routes.id)).all())

	# ============================================================
	def route(self, from_id: int, to_id: int) -> Routes | None :
		"""The route from one location to another: a one-way route that way, or a two-way route either way."""
		with self.createsession() as session :
			return session.scalar(Select(Routes).where(or_(
				(Routes.from_id == from_id) & (Routes.to_id == to_id),
				(Routes.from_id == to_id) & (Routes.to_id == from_id) & Routes.two_way.is_(True))))

	# ============================================================
	def add_route(self, guild_id: int, from_id: int, to_id: int, **fields) -> Routes | None :
		return self._add(Routes, guild_id=guild_id, from_id=from_id, to_id=to_id, **fields)

	# ============================================================
	def delete_route(self, route_id: int) -> bool :
		return self._delete(Routes, route_id)

	# == weather ==

	# ============================================================
	def weather(self, guild_id: int, region_id: int | None) -> WeatherStates | None :
		with self.createsession() as session :
			query = Select(WeatherStates).where(WeatherStates.guild_id == guild_id)
			query = query.where(WeatherStates.region_id.is_(None) if region_id is None else
			                    WeatherStates.region_id == region_id)
			return session.scalar(query)

	# ============================================================
	def save_weather(self, guild_id: int, region_id: int | None, **fields) -> WeatherStates | None :
		current = self.weather(guild_id, region_id)
		if current is None :
			return self._add(WeatherStates, guild_id=guild_id, region_id=region_id, **fields)
		return self._update(WeatherStates, current.id, **fields)

	# == travel ==

	# ============================================================
	def add_travel(self, guild_id: int, character_id: int, from_id: int | None, to_id: int, arrive_at: datetime,
	               encounter: dict | None = None) -> Travels | None :
		return self._add(Travels, guild_id=guild_id, character_id=character_id, from_id=from_id, to_id=to_id,
		                 arrive_at=arrive_at, encounter=encounter)

	# ============================================================
	def travelling(self, character_id: int) -> Travels | None :
		with self.createsession() as session :
			return session.scalar(Select(Travels).where(Travels.character_id == character_id,
			                                            Travels.state == "travelling"))

	# ============================================================
	def arrivals(self, now: datetime) -> list[Travels] :
		with self.createsession() as session :
			return list(session.scalars(Select(Travels).where(Travels.state == "travelling",
			                                                  Travels.arrive_at <= now)).all())

	# ============================================================
	def arrive(self, travel_id: int) -> Travels | None :
		return self._update(Travels, travel_id, state="arrived")
