"""Weather (design/roleplay-tools.md, section 4): what each climate can have in each season, how it changes, and what
it does to outdoor checks. No Discord or database here.

Each climate is a ladder of weather from fair to foul. The next weather is one step up or down the ladder from the
current one (or stays), weighted by how likely each is in the season, so it never jumps from a blizzard to a heatwave.
"""
import random
from dataclasses import dataclass, field

TEMPERATE = "temperate"
ARID = "arid"
ARCTIC = "arctic"
TROPICAL = "tropical"
COASTAL = "coastal"
NONE = "none"
CLIMATES = [TEMPERATE, ARID, ARCTIC, TROPICAL, COASTAL, NONE]


@dataclass
class Kind :
	key: str
	name: str
	emoji: str
	# {stat: modifier} for checks rolled outdoors.
	effects: dict = field(default_factory=dict)
	# {season: weight}; a season left out has weight 0.
	weights: dict = field(default_factory=dict)


ALL = {"spring" : 1, "summer" : 1, "autumn" : 1, "winter" : 1}

LADDERS = {
	TEMPERATE : [
		Kind("heatwave", "Heatwave", "🔥", {"endurance" : -2}, {"summer" : 2}),
		Kind("clear", "Clear skies", "☀️", {}, {"spring" : 4, "summer" : 6, "autumn" : 3, "winter" : 3}),
		Kind("cloudy", "Cloudy", "⛅", {}, {"spring" : 4, "summer" : 3, "autumn" : 4, "winter" : 4}),
		Kind("fog", "Fog", "🌫️", {"perception" : -2}, {"spring" : 2, "summer" : 1, "autumn" : 3, "winter" : 2}),
		Kind("rain", "Rain", "🌧️", {}, {"spring" : 4, "summer" : 2, "autumn" : 4, "winter" : 2}),
		Kind("heavy_rain", "Heavy rain", "🌧️", {"perception" : -2}, {"spring" : 2, "summer" : 1, "autumn" : 3,
		                                                                "winter" : 1}),
		Kind("storm", "Thunderstorm", "⛈️", {"agility" : -2}, {"spring" : 1, "summer" : 2, "autumn" : 2}),
		Kind("snow", "Snow", "🌨️", {}, {"autumn" : 1, "winter" : 4}),
		Kind("blizzard", "Blizzard", "❄️", {"endurance" : -2, "perception" : -2}, {"winter" : 2}),
	],
	ARID : [
		Kind("scorching", "Scorching heat", "🔥", {"endurance" : -2}, {"spring" : 2, "summer" : 6, "autumn" : 2}),
		Kind("clear", "Clear skies", "☀️", {}, {"spring" : 6, "summer" : 4, "autumn" : 6, "winter" : 6}),
		Kind("hazy", "Hazy", "🌤️", {}, ALL),
		Kind("windy", "Dry wind", "💨", {}, {"spring" : 3, "summer" : 2, "autumn" : 3, "winter" : 2}),
		Kind("sandstorm", "Sandstorm", "🌪️", {"perception" : -2, "agility" : -2}, {"spring" : 1, "summer" : 2,
		                                                                          "autumn" : 1}),
		Kind("cold_night", "Bitter cold", "🥶", {"endurance" : -2}, {"winter" : 3, "autumn" : 1}),
	],
	ARCTIC : [
		Kind("clear", "Clear and cold", "☀️", {}, {"spring" : 3, "summer" : 6, "autumn" : 3, "winter" : 2}),
		Kind("overcast", "Overcast", "☁️", {}, ALL),
		Kind("light_snow", "Light snow", "🌨️", {}, {"spring" : 3, "summer" : 2, "autumn" : 3, "winter" : 3}),
		Kind("snow", "Heavy snow", "🌨️", {"agility" : -2}, {"spring" : 2, "autumn" : 2, "winter" : 3}),
		Kind("blizzard", "Blizzard", "❄️", {"endurance" : -2, "perception" : -2}, {"spring" : 1, "autumn" : 1,
		                                                                          "winter" : 3}),
		Kind("whiteout", "Whiteout", "🌫️", {"perception" : -4}, {"winter" : 1}),
	],
	TROPICAL : [
		Kind("hot", "Hot sun", "🔥", {"endurance" : -2}, {"summer" : 3, "spring" : 1}),
		Kind("clear", "Clear skies", "☀️", {}, {"spring" : 4, "summer" : 3, "autumn" : 3, "winter" : 5}),
		Kind("humid", "Humid", "🌤️", {}, ALL),
		Kind("cloudy", "Cloudy", "⛅", {}, ALL),
		Kind("rain", "Warm rain", "🌧️", {}, {"spring" : 3, "summer" : 4, "autumn" : 3, "winter" : 2}),
		Kind("downpour", "Downpour", "🌧️", {"perception" : -2}, {"spring" : 1, "summer" : 3, "autumn" : 2}),
		Kind("monsoon", "Monsoon storm", "⛈️", {"agility" : -2, "perception" : -2}, {"summer" : 2, "autumn" : 1}),
	],
	COASTAL : [
		Kind("clear", "Clear skies", "☀️", {}, {"spring" : 4, "summer" : 6, "autumn" : 3, "winter" : 3}),
		Kind("breezy", "Sea breeze", "🌬️", {}, ALL),
		Kind("fog", "Sea fog", "🌫️", {"perception" : -2}, {"spring" : 3, "summer" : 1, "autumn" : 3, "winter" : 2}),
		Kind("rain", "Rain", "🌧️", {}, {"spring" : 3, "summer" : 2, "autumn" : 4, "winter" : 4}),
		Kind("gale", "Gale", "💨", {"agility" : -2}, {"spring" : 1, "autumn" : 2, "winter" : 3}),
		Kind("storm", "Storm", "⛈️", {"agility" : -2, "perception" : -2}, {"autumn" : 1, "winter" : 2}),
	],
	NONE : [Kind("indoors", "Indoors", "🏠", {}, ALL)],
}


# ============================================================
def ladder(climate: str | None) -> list[Kind] :
	return LADDERS.get(climate or TEMPERATE, LADDERS[TEMPERATE])


# ============================================================
def find(climate: str | None, key: str | None) -> Kind | None :
	for kind in ladder(climate) :
		if kind.key == key :
			return kind
	return None


# ============================================================
def keys(climate: str | None) -> list[str] :
	return [kind.key for kind in ladder(climate)]


# ============================================================
def roll(climate: str | None, season: str, current: str | None = None, rng: random.Random | None = None) -> str :
	"""The next weather: a step up or down the ladder from the current one (or the same), weighted by the season.
	Without a current weather (or when none of its neighbours fit the season), any weather of the season can come."""
	rng = rng or random
	kinds = ladder(climate)
	index = next((position for position, kind in enumerate(kinds) if kind.key == current), None)
	candidates = kinds if index is None else kinds[max(0, index - 1) :index + 2]
	weights = [kind.weights.get(season, 0) for kind in candidates]
	if not any(weights) :
		candidates = kinds
		weights = [kind.weights.get(season, 0) for kind in candidates]
	if not any(weights) :
		return kinds[0].key
	return rng.choices(candidates, weights=weights)[0].key


# ============================================================
def text(climate: str | None, key: str | None) -> str :
	"""`🌫️ Fog (-2 Perception outdoors)`"""
	kind = find(climate, key)
	if kind is None :
		return "Unknown weather"
	effects = ", ".join(f"{value:+d} {stat.capitalize()}" for stat, value in kind.effects.items())
	return f"{kind.emoji} {kind.name}" + (f" ({effects} outdoors)" if effects else "")


# ============================================================
def modifier(climate: str | None, key: str | None, stat: str) -> int :
	kind = find(climate, key)
	return int(kind.effects.get(stat, 0)) if kind else 0
