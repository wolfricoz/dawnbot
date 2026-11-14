from enum import StrEnum


class ConfigMapping(StrEnum) :
	"""This is the mapping for the config keys, this way we can avoid typos and have a single source of truth for the config keys."""

	# === Progression ===
	XP_CHANNELS = "XP_CHANNELS"
	XP_GAIN = "XP_GAIN"
	CURRENCY_GAIN = "CURRENCY_GAIN"
	CURRENCY_NAME = "CURRENCY_NAME"
	ANNOUNCEMENT = "ANNOUNCEMENT"

	# === Roleplay ===
	TIMELINE = "TIMELINE"
	CHARACTER = "CHARACTER"

	# === Moderation ===
	MODLOG = "MODLOG"


# Keys that hold several values (one config row per value).
lists = [
	ConfigMapping.XP_CHANNELS,
]

channels = [
	ConfigMapping.ANNOUNCEMENT,
	ConfigMapping.TIMELINE,
	ConfigMapping.CHARACTER,
	ConfigMapping.MODLOG,
]

settings = [
	ConfigMapping.XP_GAIN,
	ConfigMapping.CURRENCY_GAIN,
	ConfigMapping.CURRENCY_NAME,
]

toggles = []

defaults = {
	ConfigMapping.XP_GAIN       : 5,
	ConfigMapping.CURRENCY_GAIN : 30,
	ConfigMapping.CURRENCY_NAME : "currency",
}

# Maps the keys of the old jsons/<guild_id>.json files onto config keys, used once by ConfigData.migrate().
legacy_json_keys = {
	"channels"      : ConfigMapping.XP_CHANNELS,
	"announcement"  : ConfigMapping.ANNOUNCEMENT,
	"xp_gain"       : ConfigMapping.XP_GAIN,
	"currency_gain" : ConfigMapping.CURRENCY_GAIN,
	"currency_name" : ConfigMapping.CURRENCY_NAME,
	"timeline"      : ConfigMapping.TIMELINE,
	"character"     : ConfigMapping.CHARACTER,
	"modlog"        : ConfigMapping.MODLOG,
}

docs = {
	# == progression ==
	ConfigMapping.XP_CHANNELS   : "Text channels and forums where messages earn XP and currency. Threads count when their parent channel is listed. Messages shorter than 300 characters are removed there.",
	ConfigMapping.XP_GAIN       : "How many characters a message needs per point of XP (default 5).",
	ConfigMapping.CURRENCY_GAIN : "How many characters a message needs per unit of currency (default 30).",
	ConfigMapping.CURRENCY_NAME : "The name shown for the server's currency (default 'currency').",
	ConfigMapping.ANNOUNCEMENT  : "The channel where level-up announcements are posted.",

	# == roleplay ==
	ConfigMapping.TIMELINE      : "The channel where /endscene posts scene summaries.",
	ConfigMapping.CHARACTER     : "The channel or forum for character sheets.",

	# == moderation ==
	ConfigMapping.MODLOG        : "The staff channel for bot notices, such as missing permissions.",
}
