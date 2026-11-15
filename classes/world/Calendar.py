"""The in-world calendar (design/roleplay-tools.md, section 4): presets, date arithmetic, seasons, moon phases and how
a date is written. No Discord or database here; a date is (year, month, day, part) with month and day counting from 1
and part the time of day (0 dawn to 5 night).
"""
from dataclasses import dataclass

PARTS = ["dawn", "morning", "midday", "afternoon", "dusk", "night"]
PART_EMOJI = ["🌅", "🌤️", "☀️", "🌇", "🌆", "🌙"]
SEASONS = ["spring", "summer", "autumn", "winter"]
SEASON_EMOJI = {"spring" : "🌱", "summer" : "🌻", "autumn" : "🍂", "winter" : "❄️"}
MOON_PHASES = [("🌑", "New moon"), ("🌒", "Waxing crescent"), ("🌓", "First quarter"), ("🌔", "Waxing gibbous"),
               ("🌕", "Full moon"), ("🌖", "Waning gibbous"), ("🌗", "Last quarter"), ("🌘", "Waning crescent")]
UNITS = ["part", "day", "week", "month", "year"]
MAX_MONTHS = 24
MAX_MONTH_DAYS = 100
MAX_WEEKDAYS = 14
NAME_LIMIT = 30

PRESETS = {
	"gregorian" : {
		"months" : [{"name" : "January", "days" : 31, "season" : "winter"},
		            {"name" : "February", "days" : 28, "season" : "winter"},
		            {"name" : "March", "days" : 31, "season" : "spring"},
		            {"name" : "April", "days" : 30, "season" : "spring"},
		            {"name" : "May", "days" : 31, "season" : "spring"},
		            {"name" : "June", "days" : 30, "season" : "summer"},
		            {"name" : "July", "days" : 31, "season" : "summer"},
		            {"name" : "August", "days" : 31, "season" : "summer"},
		            {"name" : "September", "days" : 30, "season" : "autumn"},
		            {"name" : "October", "days" : 31, "season" : "autumn"},
		            {"name" : "November", "days" : 30, "season" : "autumn"},
		            {"name" : "December", "days" : 31, "season" : "winter"}],
		"weekdays" : ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
		"era" : None,
		"moon_cycle" : 29,
	},
	"fantasy" : {
		"months" : [{"name" : "Deepfrost", "days" : 30, "season" : "winter"},
		            {"name" : "Thawing", "days" : 30, "season" : "winter"},
		            {"name" : "Seedtide", "days" : 30, "season" : "spring"},
		            {"name" : "Rainmoon", "days" : 30, "season" : "spring"},
		            {"name" : "Blossom", "days" : 30, "season" : "spring"},
		            {"name" : "Highsun", "days" : 30, "season" : "summer"},
		            {"name" : "Goldfield", "days" : 30, "season" : "summer"},
		            {"name" : "Harvest", "days" : 30, "season" : "summer"},
		            {"name" : "Leaffall", "days" : 30, "season" : "autumn"},
		            {"name" : "Emberwane", "days" : 30, "season" : "autumn"},
		            {"name" : "Mistmoon", "days" : 30, "season" : "autumn"},
		            {"name" : "Longnight", "days" : 30, "season" : "winter"}],
		"weekdays" : ["Moonday", "Forgeday", "Windsday", "Hearthday", "Starday", "Marketday", "Restday"],
		"era" : "AR",
		"moon_cycle" : 28,
	},
}


@dataclass
class Date :
	year: int
	month: int
	day: int
	part: int = 1


# ============================================================
def year_length(months: list[dict]) -> int :
	return sum(int(month["days"]) for month in months)


# ============================================================
def ordinal(months: list[dict], date: Date) -> int :
	"""Days since day 1 of month 1 of year 0 (the year can go below 0)."""
	before = sum(int(month["days"]) for month in months[:date.month - 1])
	return date.year * year_length(months) + before + date.day - 1


# ============================================================
def from_ordinal(months: list[dict], number: int, part: int = 1) -> Date :
	length = year_length(months)
	year, rest = divmod(number, length)
	for index, month in enumerate(months) :
		if rest < int(month["days"]) :
			return Date(year, index + 1, rest + 1, part)
		rest -= int(month["days"])
	return Date(year, len(months), int(months[-1]["days"]), part)


# ============================================================
def advance(months: list[dict], weekdays: list[str], date: Date, amount: int, unit: str) -> Date :
	"""Moves a date by an amount (which may be negative) of parts, days, weeks, months or years. Moving by months or
	years keeps the day, or the last day of a shorter month."""
	if unit == "part" :
		total = date.part + amount
		days, part = divmod(total, len(PARTS))
		return from_ordinal(months, ordinal(months, date) + days, part)
	if unit in ("day", "week") :
		days = amount * (max(1, len(weekdays)) if unit == "week" else 1)
		return from_ordinal(months, ordinal(months, date) + days, date.part)
	if unit == "month" :
		index = (date.year * len(months) + date.month - 1) + amount
		year, month = divmod(index, len(months))
		day = min(date.day, int(months[month]["days"]))
		return Date(year, month + 1, day, date.part)
	if unit == "year" :
		return Date(date.year + amount, date.month, min(date.day, int(months[date.month - 1]["days"])), date.part)
	raise ValueError(f"Unknown unit {unit}")


# ============================================================
def weekday(months: list[dict], weekdays: list[str], date: Date) -> str | None :
	if not weekdays :
		return None
	return weekdays[ordinal(months, date) % len(weekdays)]


# ============================================================
def season(months: list[dict], date: Date) -> str :
	return str(months[date.month - 1].get("season") or "spring")


# ============================================================
def moon(cycle: int | None, day_number: int) -> tuple[str, str] | None :
	"""The moon's phase (emoji, name) on an in-world day, or None without a moon."""
	if not cycle :
		return None
	position = (day_number % cycle) / cycle
	return MOON_PHASES[int(position * len(MOON_PHASES) + 0.5) % len(MOON_PHASES)]


# ============================================================
def date_text(months: list[dict], date: Date, era: str | None = None) -> str :
	"""`Seedtide 12, 1203 AR`"""
	name = months[date.month - 1]["name"]
	return f"{name} {date.day}, {date.year}{f' {era}' if era else ''}"


# ============================================================
def full_text(months: list[dict], weekdays: list[str], date: Date, era: str | None = None,
              moon_cycle: int | None = None) -> str :
	"""`🌤️ Morning, Starday, Seedtide 12, 1203 AR · 🌱 Spring · 🌔 Waxing gibbous`"""
	day_name = weekday(months, weekdays, date)
	parts = [f"{PART_EMOJI[date.part]} {PARTS[date.part].capitalize()}, {f'{day_name}, ' if day_name else ''}"
	         f"{date_text(months, date, era)}"]
	current = season(months, date)
	parts.append(f"{SEASON_EMOJI.get(current, '')} {current.capitalize()}")
	phase = moon(moon_cycle, ordinal(months, date))
	if phase :
		parts.append(f"{phase[0]} {phase[1]}")
	return " · ".join(parts)


# ============================================================
def valid(months: list[dict], date: Date) -> bool :
	return 1 <= date.month <= len(months) and 1 <= date.day <= int(months[date.month - 1]["days"]) and \
		0 <= date.part < len(PARTS)


# ============================================================
def parse_months(text: str) -> tuple[list[dict] | None, str | None] :
	"""Months typed one per line as `Name: days: season` (season optional). Returns them, or None and the problem."""
	months = []
	for number, line in enumerate((text or "").splitlines(), start=1) :
		if not line.strip() :
			continue
		parts = [part.strip() for part in line.split(":")]
		if len(parts) < 2 or not parts[0] :
			return None, f"Line {number}: write `Name: days` or `Name: days: season`."
		try :
			days = int(parts[1])
		except ValueError :
			return None, f"Line {number}: {parts[1]} is not a number of days."
		if not 1 <= days <= MAX_MONTH_DAYS :
			return None, f"Line {number}: a month has 1 to {MAX_MONTH_DAYS} days."
		chosen = parts[2].lower() if len(parts) > 2 and parts[2] else None
		if chosen is not None and chosen not in SEASONS :
			return None, f"Line {number}: the season is one of {', '.join(SEASONS)}."
		months.append({"name" : parts[0][:NAME_LIMIT], "days" : days, "season" : chosen})
	if not months :
		return None, "Give at least one month."
	if len(months) > MAX_MONTHS :
		return None, f"A calendar has at most {MAX_MONTHS} months."
	# Months without a season get one by where they fall in the year.
	for index, month in enumerate(months) :
		if month["season"] is None :
			month["season"] = SEASONS[int(index / len(months) * len(SEASONS))]
	return months, None


# ============================================================
def parse_weekdays(text: str) -> list[str] :
	return [name.strip()[:NAME_LIMIT] for name in (text or "").split(",") if name.strip()][:MAX_WEEKDAYS]


# ============================================================
def months_text(months: list[dict]) -> str :
	return "\n".join(f"{month['name']}: {month['days']}: {month['season']}" for month in months)


# ============================================================
def flow_ratio(flow: str | None) -> float | None :
	"""In-world days per real day for a TIME_FLOW value (`2:1` → 2.0, `1:4` → 0.25), or None for manual time."""
	if not flow or flow == "manual" or ":" not in flow :
		return None
	world, real = flow.split(":", 1)
	try :
		world_days, real_days = float(world), float(real)
	except ValueError :
		return None
	return world_days / real_days if world_days > 0 and real_days > 0 else None


# ============================================================
def parts_elapsed(ratio: float, real_hours: float) -> int :
	"""How many parts of the day pass in-world in real_hours at a ratio."""
	return int(real_hours * ratio * len(PARTS) / 24)


# ============================================================
def real_hours_per_part(ratio: float) -> float :
	return 24 / (ratio * len(PARTS))
