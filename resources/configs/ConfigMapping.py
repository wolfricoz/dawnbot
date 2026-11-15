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

	# === Roleplay tools ===
	GM_ROLL_LOG = "GM_ROLL_LOG"
	TIME_FLOW = "TIME_FLOW"
	WEATHER_HOURS = "WEATHER_HOURS"
	WEATHER_EFFECTS = "WEATHER_EFFECTS"
	TRAVEL = "TRAVEL"
	PRESENCE_DAYS = "PRESENCE_DAYS"
	SCENE_NUDGE_HOURS = "SCENE_NUDGE_HOURS"
	SCENE_SKIP_HOURS = "SCENE_SKIP_HOURS"
	SCENE_IDLE_DAYS = "SCENE_IDLE_DAYS"
	CHRONICLE = "CHRONICLE"
	CHRONICLE_CHARACTER_POSTS = "CHRONICLE_CHARACTER_POSTS"
	COMMON_LANGUAGE = "COMMON_LANGUAGE"
	LANGUAGE_SLOTS = "LANGUAGE_SLOTS"
	LANGUAGE_SCRAMBLE = "LANGUAGE_SCRAMBLE"
	LETTER_DELAY = "LETTER_DELAY"
	COURIER_COST = "COURIER_COST"
	LETTER_CHANNEL = "LETTER_CHANNEL"
	LETTER_INTERCEPT = "LETTER_INTERCEPT"
	JOB_BOARD = "JOB_BOARD"
	JOB_PLAYER_POSTS = "JOB_PLAYER_POSTS"
	DOWNTIME_RESET = "DOWNTIME_RESET"
	DOWNTIME_ACTIVE_DAYS = "DOWNTIME_ACTIVE_DAYS"
	DOWNTIME_PRIVATE = "DOWNTIME_PRIVATE"
	WORK_PAY = "WORK_PAY"
	STUDY_DAYS = "STUDY_DAYS"
	CAROUSE_COST = "CAROUSE_COST"
	RUMOR_MODE = "RUMOR_MODE"
	RUMOR_CHANNEL = "RUMOR_CHANNEL"
	RUMOR_DAYS = "RUMOR_DAYS"
	OMEN_DAYS = "OMEN_DAYS"
	OMEN_EFFECTS = "OMEN_EFFECTS"

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
	ConfigMapping.GM_ROLL_LOG,
	ConfigMapping.CHRONICLE,
	ConfigMapping.LETTER_CHANNEL,
	ConfigMapping.JOB_BOARD,
	ConfigMapping.RUMOR_CHANNEL,
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
	ConfigMapping.TIME_FLOW          : "manual",
	ConfigMapping.WEATHER_HOURS      : 12,
	ConfigMapping.WEATHER_EFFECTS    : "ENABLED",
	ConfigMapping.TRAVEL             : "DISABLED",
	ConfigMapping.PRESENCE_DAYS      : 7,
	ConfigMapping.SCENE_NUDGE_HOURS  : 24,
	ConfigMapping.SCENE_SKIP_HOURS   : 72,
	ConfigMapping.SCENE_IDLE_DAYS    : 14,
	ConfigMapping.CHRONICLE_CHARACTER_POSTS : "DISABLED",
	ConfigMapping.COMMON_LANGUAGE    : "Common",
	ConfigMapping.LANGUAGE_SLOTS     : 1,
	ConfigMapping.LANGUAGE_SCRAMBLE  : "speech",
	ConfigMapping.LETTER_DELAY       : 6,
	ConfigMapping.COURIER_COST       : 25,
	ConfigMapping.LETTER_INTERCEPT   : "DISABLED",
	ConfigMapping.JOB_PLAYER_POSTS   : "DISABLED",
	ConfigMapping.DOWNTIME_RESET     : 0,
	ConfigMapping.DOWNTIME_ACTIVE_DAYS : 7,
	ConfigMapping.DOWNTIME_PRIVATE   : "DISABLED",
	ConfigMapping.WORK_PAY           : 50,
	ConfigMapping.STUDY_DAYS         : 10,
	ConfigMapping.CAROUSE_COST       : 50,
	ConfigMapping.RUMOR_MODE         : "board",
	ConfigMapping.RUMOR_DAYS         : 14,
	ConfigMapping.OMEN_DAYS          : 7,
	ConfigMapping.OMEN_EFFECTS       : "DISABLED",
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

# The roleplay tools' settings (design/roleplay-tools.md), all set with /config roleplay: ("number", lowest, highest),
# ("choice", [values]), ("toggle",) or ("text", longest).
roleplay_settings = {
	ConfigMapping.TIME_FLOW          : ("choice", ["manual", "1:1", "2:1", "4:1", "7:1", "1:2", "1:4", "1:7"]),
	ConfigMapping.WEATHER_HOURS      : ("number", 1, 168),
	ConfigMapping.WEATHER_EFFECTS    : ("toggle",),
	ConfigMapping.TRAVEL             : ("toggle",),
	ConfigMapping.PRESENCE_DAYS      : ("number", 1, 60),
	ConfigMapping.SCENE_NUDGE_HOURS  : ("number", 1, 336),
	ConfigMapping.SCENE_SKIP_HOURS   : ("number", 0, 720),
	ConfigMapping.SCENE_IDLE_DAYS    : ("number", 0, 90),
	ConfigMapping.CHRONICLE_CHARACTER_POSTS : ("toggle",),
	ConfigMapping.COMMON_LANGUAGE    : ("text", 50),
	ConfigMapping.LANGUAGE_SLOTS     : ("number", 0, 10),
	ConfigMapping.LANGUAGE_SCRAMBLE  : ("choice", ["speech", "all"]),
	ConfigMapping.LETTER_DELAY       : ("number", 0, 168),
	ConfigMapping.COURIER_COST       : ("number", 0, 100000),
	ConfigMapping.LETTER_INTERCEPT   : ("toggle",),
	ConfigMapping.JOB_PLAYER_POSTS   : ("toggle",),
	ConfigMapping.DOWNTIME_RESET     : ("number", 0, 23),
	ConfigMapping.DOWNTIME_ACTIVE_DAYS : ("number", 0, 60),
	ConfigMapping.DOWNTIME_PRIVATE   : ("toggle",),
	ConfigMapping.WORK_PAY           : ("number", 0, 100000),
	ConfigMapping.STUDY_DAYS         : ("number", 1, 100),
	ConfigMapping.CAROUSE_COST       : ("number", 0, 100000),
	ConfigMapping.RUMOR_MODE         : ("choice", ["board", "whisper"]),
	ConfigMapping.RUMOR_DAYS         : ("number", 1, 90),
	ConfigMapping.OMEN_DAYS          : ("number", 1, 60),
	ConfigMapping.OMEN_EFFECTS       : ("toggle",),
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

	# == roleplay tools ==
	ConfigMapping.GM_ROLL_LOG        : "Optional: a channel where every secret roll is copied (secret and passive checks, secret /dice rolls and secret table rolls), so the server can audit them.",

	ConfigMapping.TIME_FLOW          : "How in-world time moves: `manual` (the default; staff move it with /time advance) or a ratio of in-world days to real days, such as `1:1`, `2:1` or `1:4`.",
	ConfigMapping.WEATHER_HOURS      : "With manual time, how many real hours the weather lasts before it changes (default 12). With flowing time it changes every in-world day.",
	ConfigMapping.WEATHER_EFFECTS    : "Whether weather at an outdoor location changes checks rolled there, such as -2 Perception in fog (default on).",
	ConfigMapping.TRAVEL             : "Whether characters travel between locations with /travel, with encounters on dangerous routes (default off).",
	ConfigMapping.PRESENCE_DAYS      : "A character counts as being at the location of its last post for this many days (default 7). Used by /location who and passive checks.",
	ConfigMapping.SCENE_NUDGE_HOURS  : "Hours before the player whose turn it is in a scene gets a reminder (default 24).",
	ConfigMapping.SCENE_SKIP_HOURS   : "Hours before a scene skips the player whose turn it is (default 72; 0 never skips).",
	ConfigMapping.SCENE_IDLE_DAYS    : "Days without posts before a scene asks its host whether to end it; 7 days later it ends by itself (default 14; 0 never).",
	ConfigMapping.CHRONICLE          : "The forum (or channel) where finished scenes are written up as transcripts.",
	ConfigMapping.CHRONICLE_CHARACTER_POSTS : "Whether each finished scene adds a line to its characters' posts in the character forum (default off).",
	ConfigMapping.COMMON_LANGUAGE    : "The language every character speaks (default Common).",
	ConfigMapping.LANGUAGE_SLOTS     : "Languages a new character picks besides the common one, plus 1 per 2 Intelligence above 5 (default 1).",
	ConfigMapping.LANGUAGE_SCRAMBLE  : "What a language scrambles: `speech` (the default; only quoted text) or `all`.",
	ConfigMapping.LETTER_DELAY       : "Real hours a letter takes to arrive (default 6), unless a route between the characters says otherwise.",
	ConfigMapping.COURIER_COST       : "What an express letter (delivered in an hour) costs the sender (default 25).",
	ConfigMapping.LETTER_CHANNEL     : "Optional: where the bot says a letter arrived when its recipient has DMs closed.",
	ConfigMapping.LETTER_INTERCEPT   : "Whether GMs can read, hold and destroy letters in transit (default off). Players are warned when they write.",
	ConfigMapping.JOB_BOARD          : "The forum where jobs are posted with /job post.",
	ConfigMapping.JOB_PLAYER_POSTS   : "Whether players can post jobs as their characters, paying the reward up front (default off).",
	ConfigMapping.DOWNTIME_RESET     : "The hour (UTC) when a new downtime day starts (default 0).",
	ConfigMapping.DOWNTIME_ACTIVE_DAYS : "Downtime is only for characters that posted in the last this many days (default 7; 0 lets every character).",
	ConfigMapping.DOWNTIME_PRIVATE   : "Whether downtime results are private instead of posted (default off).",
	ConfigMapping.WORK_PAY           : "What a day of downtime work pays when the occupation sets no pay (default 50).",
	ConfigMapping.STUDY_DAYS         : "Successful study days to learn a language partly, and again to speak it fluently (default 10).",
	ConfigMapping.CAROUSE_COST       : "What carousing in downtime costs (default 50).",
	ConfigMapping.RUMOR_MODE         : "`board` (the default): rumors are posted to the rumor channel straight away. `whisper`: characters overhear them with /rumor listen, and one heard 3 times is posted.",
	ConfigMapping.RUMOR_CHANNEL      : "The channel where rumors are posted.",
	ConfigMapping.RUMOR_DAYS         : "Days before a rumor fades (default 14).",
	ConfigMapping.OMEN_DAYS          : "Days between omen draws for each character (default 7).",
	ConfigMapping.OMEN_EFFECTS       : "Whether omen cards give boons and banes (default off; cards are pure story).",

	# == moderation ==
	ConfigMapping.MODLOG        :"The staff channel for bot notices, such as missing permissions.",
}
