from enum import StrEnum


class ConfigMapping(StrEnum) :
	"""The config keys in one place, so they are never mistyped."""

	# === Progression ===
	XP_CHANNELS = "XP_CHANNELS"
	XP_GAIN = "XP_GAIN"
	CURRENCY_GAIN = "CURRENCY_GAIN"
	CURRENCY_NAME = "CURRENCY_NAME"
	ANNOUNCEMENT = "ANNOUNCEMENT"

	# === Roleplay ===
	TIMELINE = "TIMELINE"
	CHARACTER = "CHARACTER"

	# === Characters ===
	CHARACTER_REVIEW = "CHARACTER_REVIEW"
	CHARACTER_CAP = "CHARACTER_CAP"
	REAPPROVAL_ON_EDIT = "REAPPROVAL_ON_EDIT"
	STAT_METHOD = "STAT_METHOD"
	STAT_BASE = "STAT_BASE"
	STAT_BONUS = "STAT_BONUS"
	STAT_MIN = "STAT_MIN"
	STAT_MAX = "STAT_MAX"
	LEVEL_BASE = "LEVEL_BASE"
	POINTS_PER_LEVEL = "POINTS_PER_LEVEL"
	STARTING_CURRENCY = "STARTING_CURRENCY"
	PROXY_OUTSIDE_RP = "PROXY_OUTSIDE_RP"
	SPECIES_FORUM = "SPECIES_FORUM"
	SPECIES_CREATION = "SPECIES_CREATION"
	GEAR_FORUM = "GEAR_FORUM"
	ECONOMY = "ECONOMY"
	RETIRE_THREAD = "RETIRE_THREAD"
	LEGENDARY_POINTS = "LEGENDARY_POINTS"

	# === Combat ===
	COMBAT_PACING = "COMBAT_PACING"
	COMBAT_ASYNC_TIMER = "COMBAT_ASYNC_TIMER"
	COMBAT_LIVE_TIMER = "COMBAT_LIVE_TIMER"
	COMBAT_PVP = "COMBAT_PVP"
	COMBAT_LETHAL = "COMBAT_LETHAL"
	COMBAT_LEVEL_BONUS = "COMBAT_LEVEL_BONUS"
	ABILITY_CREATION = "ABILITY_CREATION"
	ABILITY_FORUM = "ABILITY_FORUM"

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
	ConfigMapping.CHARACTER_REVIEW,
	ConfigMapping.SPECIES_FORUM,
	ConfigMapping.GEAR_FORUM,
	ConfigMapping.ABILITY_FORUM,
	ConfigMapping.MODLOG,
]

settings = [
	ConfigMapping.XP_GAIN,
	ConfigMapping.CURRENCY_GAIN,
	ConfigMapping.CURRENCY_NAME,
	ConfigMapping.CHARACTER_CAP,
	ConfigMapping.REAPPROVAL_ON_EDIT,
	ConfigMapping.STAT_METHOD,
	ConfigMapping.STAT_BASE,
	ConfigMapping.STAT_BONUS,
	ConfigMapping.STAT_MIN,
	ConfigMapping.STAT_MAX,
	ConfigMapping.LEVEL_BASE,
	ConfigMapping.POINTS_PER_LEVEL,
	ConfigMapping.STARTING_CURRENCY,
	ConfigMapping.SPECIES_CREATION,
	ConfigMapping.ECONOMY,
	ConfigMapping.RETIRE_THREAD,
	ConfigMapping.LEGENDARY_POINTS,
	ConfigMapping.COMBAT_PACING,
	ConfigMapping.COMBAT_ASYNC_TIMER,
	ConfigMapping.COMBAT_LIVE_TIMER,
	ConfigMapping.COMBAT_LETHAL,
	ConfigMapping.ABILITY_CREATION,
]

toggles = [
	ConfigMapping.PROXY_OUTSIDE_RP,
	ConfigMapping.COMBAT_PVP,
	ConfigMapping.COMBAT_LEVEL_BONUS,
]

defaults = {
	ConfigMapping.XP_GAIN            : 5,
	ConfigMapping.CURRENCY_GAIN      : 30,
	ConfigMapping.CURRENCY_NAME      : "currency",
	ConfigMapping.CHARACTER_CAP      : 3,
	ConfigMapping.REAPPROVAL_ON_EDIT : "lore",
	ConfigMapping.STAT_METHOD        : "both",
	ConfigMapping.STAT_BASE          : 5,
	ConfigMapping.STAT_BONUS         : 5,
	ConfigMapping.STAT_MIN           : 1,
	ConfigMapping.STAT_MAX           : 10,
	ConfigMapping.LEVEL_BASE         : 1000,
	ConfigMapping.POINTS_PER_LEVEL   : 1,
	ConfigMapping.STARTING_CURRENCY  : 3000,
	ConfigMapping.SPECIES_CREATION   : "everyone",
	ConfigMapping.ECONOMY            : "economy",
	ConfigMapping.RETIRE_THREAD      : "lock",
	ConfigMapping.LEGENDARY_POINTS   : 5,
	ConfigMapping.COMBAT_PACING      : "async",
	ConfigMapping.COMBAT_ASYNC_TIMER : 12,
	ConfigMapping.COMBAT_LIVE_TIMER  : 3,
	ConfigMapping.COMBAT_PVP         : "ENABLED",
	ConfigMapping.COMBAT_LETHAL      : "gm",
	ConfigMapping.COMBAT_LEVEL_BONUS : "DISABLED",
	ConfigMapping.ABILITY_CREATION   : "everyone",
}

# Settings that are whole numbers, with the lowest and highest value /config accepts.
number_settings = {
	ConfigMapping.CHARACTER_CAP     : (1, 50),
	ConfigMapping.STAT_BASE         : (-2, 13),
	ConfigMapping.STAT_BONUS        : (0, 100),
	ConfigMapping.STAT_MIN          : (-2, 13),
	ConfigMapping.STAT_MAX          : (-2, 13),
	ConfigMapping.LEVEL_BASE        : (1, 1000000),
	ConfigMapping.POINTS_PER_LEVEL  : (0, 10),
	ConfigMapping.STARTING_CURRENCY : (0, 1000000000),
	ConfigMapping.LEGENDARY_POINTS  : (0, 50),
	ConfigMapping.COMBAT_ASYNC_TIMER : (1, 168),
	ConfigMapping.COMBAT_LIVE_TIMER : (1, 60),
}

# Settings with a fixed set of values.
choice_settings = {
	ConfigMapping.REAPPROVAL_ON_EDIT : ["none", "lore", "all"],
	ConfigMapping.STAT_METHOD        : ["both", "point_buy", "rolled"],
	ConfigMapping.SPECIES_CREATION   : ["everyone", "staff", "off"],
	ConfigMapping.ECONOMY            : ["economy", "free"],
	ConfigMapping.RETIRE_THREAD      : ["lock", "delete"],
	ConfigMapping.COMBAT_PACING      : ["async", "live", "choose"],
	ConfigMapping.COMBAT_LETHAL      : ["off", "gm", "agreed"],
	ConfigMapping.ABILITY_CREATION   : ["everyone", "staff", "off"],
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
	ConfigMapping.XP_CHANNELS   : "Text channels and forums where roleplay happens: messages earn XP there, and posts made as a character also earn that character currency. Threads count when their parent channel is listed. Messages shorter than 300 characters are removed there.",
	ConfigMapping.XP_GAIN       : "How many characters a message needs per point of XP (default 5).",
	ConfigMapping.CURRENCY_GAIN : "How many characters a post made as a character needs per unit of currency for that character (default 30).",
	ConfigMapping.CURRENCY_NAME : "The name shown for the server's currency (default 'currency').",
	ConfigMapping.ANNOUNCEMENT  : "The channel where level-up announcements are posted.",

	# == roleplay ==
	ConfigMapping.TIMELINE      : "The channel where /endscene posts scene summaries.",
	ConfigMapping.CHARACTER     : "The channel or forum where approved characters are posted.",

	# == characters ==
	ConfigMapping.CHARACTER_REVIEW   : "The staff channel where new and edited characters wait for approval. Characters cannot be created until it is set.",
	ConfigMapping.CHARACTER_CAP      : "How many characters a member can have (default 3). Retired characters do not count.",
	ConfigMapping.REAPPROVAL_ON_EDIT : "Which edits to an approved character need a new review: `none`, `lore` (name, avatar and sheet answers; the default) or `all` (also prefix, suffix and the member's own extra fields). Spending earned points never needs a review; a respec always does.",
	ConfigMapping.STAT_METHOD        : "How members set their SPECIAL stats: `both` (the member chooses; the default), `point_buy` or `rolled`.",
	ConfigMapping.STAT_BASE          : "The value every SPECIAL stat starts at with point-buy (default 5).",
	ConfigMapping.STAT_BONUS         : "The extra points a new character can spend on top of the starting values (default 5).",
	ConfigMapping.STAT_MIN           : "The lowest value a SPECIAL stat can have (default 1).",
	ConfigMapping.STAT_MAX           : "The highest value a SPECIAL stat can have (default 10).",
	ConfigMapping.LEVEL_BASE         : "How fast characters level: reaching level L takes this number x L(L-1)/2 XP (default 1000, so level 2 at 1000 XP and level 3 at 3000).",
	ConfigMapping.POINTS_PER_LEVEL   : "How many SPECIAL points a character gets for each level (default 1).",
	ConfigMapping.STARTING_CURRENCY  : "How much currency a new character starts with (default 3000).",
	ConfigMapping.PROXY_OUTSIDE_RP   : "Whether members can post as their characters outside the XP channels (default off). Posts there earn no XP and have no minimum length.",
	ConfigMapping.SPECIES_FORUM      : "The forum (or channel) where approved species are posted. Tags on a species' post can restrict who may pick it; see /tagrule.",
	ConfigMapping.SPECIES_CREATION   : "Who can create species with /species create: `everyone` (the default), `staff` (Manage Messages) or `off`.",
	ConfigMapping.GEAR_FORUM         : "Optional: the forum where the gear catalog is posted, one post per item. Tags on an item's post can restrict who may buy it; see /tagrule.",
	ConfigMapping.RETIRE_THREAD      : "What happens to a retired character's post in the character channel: `lock` (the default; the forum thread is locked and archived, and opened again if the character returns) or `delete`.",
	ConfigMapping.ECONOMY            : "`economy` (the default): characters buy gear with their currency and sell it for 30% of what they paid. `free`: all gear costs nothing and selling returns nothing.",

	ConfigMapping.LEGENDARY_POINTS   : "How many extra SPECIAL points a character gets when staff make it legendary (default 5). Legendary characters also have doubled stat limits and one extra ability slot.",

	# == combat ==
	ConfigMapping.COMBAT_PACING      : "How fights run: `async` (the default; each side gets a phase with a long timer), `live` (each combatant gets a short turn in Sequence order) or `choose` (whoever starts the fight picks).",
	ConfigMapping.COMBAT_ASYNC_TIMER : "Hours each side gets per phase in async fights (default 12). When it runs out, those who did not act get an automatic move.",
	ConfigMapping.COMBAT_LIVE_TIMER  : "Minutes each combatant gets per turn in live fights (default 3).",
	ConfigMapping.COMBAT_PVP         : "Whether members can challenge each other with /combat challenge (default on).",
	ConfigMapping.COMBAT_LETHAL      : "Whether fights can kill characters: `off`, `gm` (the default; staff can start a fight as lethal) or `agreed` (lethal fights need every player to accept when they join).",
	ConfigMapping.COMBAT_LEVEL_BONUS : "Whether characters get +1 to hit at levels 4, 8, 12 and 16 (default off).",
	ConfigMapping.ABILITY_CREATION   : "Who can create abilities, spells and magic schools: `everyone` (the default), `staff` (Manage Messages) or `off`.",
	ConfigMapping.ABILITY_FORUM      : "Optional: the forum where approved abilities are posted. Tags on an ability's post can restrict who may learn it; see /tagrule.",

	# == moderation ==
	ConfigMapping.MODLOG        : "The staff channel for bot notices, such as missing permissions.",
}
