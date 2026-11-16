"""/config setup: puts the channels and settings for characters, proxying, species, gear and levels in place.

Two ways in:
- auto: creates every channel that is not set yet, in three categories (a hidden staff one, a read-only info one and
  a roleplay one), and keeps the channels that are already set or that already exist under the default name.
- guided: walks staff through each channel and the main settings, one step at a time (views/setup/SetupSteps.py).

Both only fill in what is missing or what staff pick; nothing that is already set is replaced without being asked.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import discord
from discord_py_utilities.permissions import check_missing_channel_permissions, check_missing_guild_permissions

from classes.kernel.ConfigData import ConfigData
from classes.kernel.ServerSync import sync_server
from classes.support.PermissionNotice import CORE_GUILD_PERMISSIONS, humanise
from database.transactions.GearItemTransactions import GearItemTransactions
from database.transactions.LevelTransactions import LevelTransactions
from resources.configs.ConfigMapping import ConfigMapping, choice_settings

STAFF = "staff"
INFO = "info"
ROLEPLAY = "roleplay"

CATEGORY_NAMES = {
	STAFF    : "Roleplay Staff",
	INFO     : "Roleplay Info",
	ROLEPLAY : "Roleplay",
}
ROLEPLAY_CHANNEL = "roleplay"
ROLEPLAY_TOPIC = "Roleplay here. Posts earn XP, and you can post as your characters."

# What auto setup needs to create the categories and channels and set their permissions.
AUTO_PERMISSIONS = ["manage_channels", "manage_roles", "view_channel"]
# Proxying posts through webhooks and removes the original message.
PROXY_PERMISSIONS = ["manage_webhooks", "manage_messages"]
# What the bot needs in each kind of channel it posts in.
POST_PERMISSIONS = ["view_channel", "send_messages", "embed_links"]
FORUM_PERMISSIONS = POST_PERMISSIONS + ["send_messages_in_threads", "manage_threads"]
ROLEPLAY_PERMISSIONS = ["view_channel", "send_messages", "read_message_history"] + PROXY_PERMISSIONS
# The bot's own overwrite in the channels it creates, so the read-only and hidden categories never lock it out.
BOT_OVERWRITE = ["view_channel", "send_messages", "send_messages_in_threads", "embed_links", "attach_files",
                 "read_message_history", "manage_messages", "manage_threads", "manage_webhooks"]

# How long after setup created a channel the "should this be a roleplay channel?" prompt stays quiet. Discord can
# deliver the channel-create event after the request that made the channel has returned.
QUIET_SECONDS = 15


@dataclass(frozen=True)
class ChannelStep :
	key: ConfigMapping
	title: str
	# The name auto setup gives the channel, and looks for before creating one.
	name: str
	# Auto setup makes a forum (falling back to a text channel when the server cannot have forums).
	forum: bool
	section: str
	required: bool
	description: str
	# The setting only accepts text channels.
	text_only: bool = False


CHANNEL_STEPS = [
	ChannelStep(ConfigMapping.CHARACTER_REVIEW, "Character review", "character-review", forum=False, section=STAFF,
	            required=True, text_only=True,
	            description="The staff channel where new and edited characters and species wait for approval. "
	                        "Members cannot create characters until this is set."),
	ChannelStep(ConfigMapping.MODLOG, "Bot log", "bot-log", forum=False, section=STAFF, required=False,
	            text_only=True,
	            description="The staff channel for my notices: missing permissions, and the question whether a new "
	                        "channel is for roleplay."),
	ChannelStep(ConfigMapping.CHARACTER, "Characters", "characters", forum=True, section=INFO, required=False,
	            description="Where approved characters are posted. In a forum every character gets its own post."),
	ChannelStep(ConfigMapping.SPECIES_FORUM, "Species", "species", forum=True, section=INFO, required=False,
	            description="Where approved species are posted. Tags on a species' post can restrict who may pick "
	                        "it (see /tagrule)."),
	ChannelStep(ConfigMapping.GEAR_FORUM, "Gear catalog", "gear", forum=True, section=INFO, required=False,
	            description="Where the gear catalog is posted, one post per item. Tags on an item's post can restrict "
	                        "who may buy it (see /tagrule)."),
	ChannelStep(ConfigMapping.ANNOUNCEMENT, "Level-ups", "level-ups", forum=False, section=INFO, required=False,
	            description="Where level-ups are announced."),
	ChannelStep(ConfigMapping.TIMELINE, "Timeline", "timeline", forum=False, section=INFO, required=False,
	            description="Where /endscene posts scene summaries."),
]

# The settings the guided setup asks about, on two pages, with a label for every value.
TOGGLE_ON, TOGGLE_OFF = "TRUE", "FALSE"
SETTING_PAGES = [
	("Character rules", [ConfigMapping.STAT_METHOD, ConfigMapping.REAPPROVAL_ON_EDIT, ConfigMapping.PROXY_OUTSIDE_RP]),
	("Species, gear and retiring", [ConfigMapping.SPECIES_CREATION, ConfigMapping.ECONOMY,
	                                ConfigMapping.RETIRE_THREAD]),
]
SETTING_LABELS = {
	ConfigMapping.STAT_METHOD        : {
		"both"      : "SPECIAL: members choose point-buy or rolling",
		"point_buy" : "SPECIAL: point-buy only",
		"rolled"    : "SPECIAL: rolled only",
	},
	ConfigMapping.REAPPROVAL_ON_EDIT : {
		"none" : "Edits to approved characters never need a review",
		"lore" : "Name, avatar and sheet edits need a review",
		"all"  : "Every edit to an approved character needs a review",
	},
	ConfigMapping.PROXY_OUTSIDE_RP   : {
		TOGGLE_OFF : "Members post as characters only in roleplay channels",
		TOGGLE_ON  : "Members can post as characters anywhere",
	},
	ConfigMapping.SPECIES_CREATION   : {
		"everyone" : "Everyone can create species",
		"staff"    : "Only staff can create species",
		"off"      : "Nobody can create species",
	},
	ConfigMapping.ECONOMY            : {
		"economy" : "Gear costs currency (sells back for about 30%)",
		"free"    : "Gear is free",
	},
	ConfigMapping.RETIRE_THREAD      : {
		"lock"   : "Lock a retired character's post",
		"delete" : "Delete a retired character's post",
	},
}


@dataclass
class SetupReport :
	"""What a setup run did, by setting key."""
	created: list[str] = field(default_factory=list)
	kept: list[str] = field(default_factory=list)


class BotSetup :
	# Guild id -> number of channel creations in flight (or that just finished), for the new-channel prompt.
	_creating: dict[int, int] = {}

	# == creating channels quietly ==

	# ============================================================
	@staticmethod
	def is_creating(guild_id: int) -> bool :
		"""True while setup is creating channels in the guild, and shortly after."""
		return BotSetup._creating.get(guild_id, 0) > 0

	# ============================================================
	@staticmethod
	@asynccontextmanager
	async def creating(guild_id: int) :
		BotSetup._creating[guild_id] = BotSetup._creating.get(guild_id, 0) + 1
		try :
			yield
		finally :
			def release() :
				left = BotSetup._creating.get(guild_id, 1) - 1
				if left > 0 :
					BotSetup._creating[guild_id] = left
				else :
					BotSetup._creating.pop(guild_id, None)

			asyncio.get_running_loop().call_later(QUIET_SECONDS, release)

	# == reading the current setup ==

	# ============================================================
	@staticmethod
	def fits(step: ChannelStep, channel) -> bool :
		if step.text_only :
			return isinstance(channel, discord.TextChannel)
		return isinstance(channel, (discord.TextChannel, discord.ForumChannel))

	# ============================================================
	@staticmethod
	def current(guild: discord.Guild, step: ChannelStep) :
		"""The channel the setting points at, when it still exists and is of a kind the setting accepts."""
		channel_id = ConfigData().get_int(guild.id, step.key)
		channel = guild.get_channel(channel_id) if channel_id else None
		return channel if BotSetup.fits(step, channel) else None

	# ============================================================
	@staticmethod
	def by_name(guild: discord.Guild, step: ChannelStep) :
		"""A channel that already has the default name, so setup reuses it instead of making a second one."""
		for channel in guild.channels :
			if channel.name == step.name and BotSetup.fits(step, channel) :
				return channel
		return None

	# ============================================================
	@staticmethod
	def roleplay_channels(guild: discord.Guild) -> list :
		"""The XP (roleplay) channels that still exist."""
		return [channel for channel_id in ConfigData().get_list(guild.id, ConfigMapping.XP_CHANNELS)
		        if (channel := guild.get_channel(channel_id)) is not None]

	# ============================================================
	@staticmethod
	def plan(guild: discord.Guild) -> list[tuple[ChannelStep, object]] :
		"""Per channel setting: the channel auto setup would use, or None when it would create one."""
		return [(step, BotSetup.current(guild, step) or BotSetup.by_name(guild, step)) for step in CHANNEL_STEPS]

	# ============================================================
	@staticmethod
	def describe_plan(guild: discord.Guild) -> str :
		"""What auto setup is about to do, for its confirmation question."""
		create, keep = [], []
		for step, channel in BotSetup.plan(guild) :
			if channel is None :
				create.append(f"#{step.name}")
			else :
				keep.append(f"{step.title}: {channel.mention}")
		if not BotSetup.roleplay_channels(guild) :
			create.append(f"#{ROLEPLAY_CHANNEL}")
		lines = ["Set up the roleplay features automatically?"]
		if create :
			lines.append(f"I'll create {', '.join(create)}, in the categories **{CATEGORY_NAMES[STAFF]}** (hidden "
			             f"from members), **{CATEGORY_NAMES[INFO]}** (read-only for members) and "
			             f"**{CATEGORY_NAMES[ROLEPLAY]}**.")
		if keep :
			lines.append("I'll keep what is already there: " + "; ".join(keep) + ".")
		if not create :
			lines.append("Every channel is already in place, so nothing new is created.")
		lines.append("Settings keep their current values; change them with `/config setup guided` or `/config`.")
		return "\n".join(lines)

	# == writing ==

	# ============================================================
	@staticmethod
	def set_channel(guild_id: int, step: ChannelStep, channel) :
		ConfigData().add_key(guild_id, step.key, channel.id, overwrite=True)

	# ============================================================
	@staticmethod
	def add_roleplay_channel(guild_id: int, channel) -> bool :
		"""False when it already was a roleplay channel."""
		return ConfigData().add_to_list(guild_id, ConfigMapping.XP_CHANNELS, channel.id)

	# ============================================================
	@staticmethod
	def current_setting(guild_id: int, key: ConfigMapping) -> str :
		if key == ConfigMapping.PROXY_OUTSIDE_RP :
			return TOGGLE_ON if ConfigData().get_toggle(guild_id, key) else TOGGLE_OFF
		return str(ConfigData().get_key(guild_id, key))

	# ============================================================
	@staticmethod
	def set_setting(guild_id: int, key: ConfigMapping, value: str) :
		if value not in SETTING_LABELS.get(key, {}) or (key in choice_settings and value not in choice_settings[key]) :
			raise ValueError(f"{value} is not a value for {key}")
		ConfigData().add_key(guild_id, key, value, overwrite=True)

	# == creating ==

	# ============================================================
	@staticmethod
	def bot_overwrite(guild: discord.Guild) -> discord.PermissionOverwrite :
		"""Allows the bot what it needs, limited to what it has: Discord refuses overwrites granting more."""
		granted = guild.me.guild_permissions
		return discord.PermissionOverwrite(**{perm : True for perm in BOT_OVERWRITE if getattr(granted, perm, False)})

	# ============================================================
	@staticmethod
	def staff_roles(guild: discord.Guild) -> list[discord.Role] :
		"""Roles whose members count as staff for characters (Manage Messages), which see the staff category."""
		return [role for role in guild.roles
		        if role.permissions.manage_messages and not role.is_default() and not role.managed]

	# ============================================================
	@staticmethod
	def overwrites(guild: discord.Guild, section: str) -> dict :
		everyone = guild.default_role
		result = {}
		match section :
			case "staff" :
				result[everyone] = discord.PermissionOverwrite(view_channel=False)
				for role in BotSetup.staff_roles(guild) :
					result[role] = discord.PermissionOverwrite(view_channel=True)
			case "info" :
				# Members read and may comment in forum posts, but only the bot starts posts and writes in channels.
				result[everyone] = discord.PermissionOverwrite(send_messages=False, create_public_threads=False)
		result[guild.me] = BotSetup.bot_overwrite(guild)
		return result

	# ============================================================
	@staticmethod
	async def category(guild: discord.Guild, section: str, made: dict) -> discord.CategoryChannel :
		"""The setup category for a section; made holds the ones this run created, which the cache may not list yet."""
		if section in made :
			return made[section]
		name = CATEGORY_NAMES[section]
		category = discord.utils.get(guild.categories, name=name)
		if category is None :
			category = await guild.create_category(name=name, overwrites=BotSetup.overwrites(guild, section),
			                                       reason="/config setup")
		made[section] = category
		return category

	# ============================================================
	@staticmethod
	async def create(guild: discord.Guild, step: ChannelStep, made: dict | None = None) :
		"""Creates the channel for a setting in its category and sets it. Forums fall back to text channels."""
		made = {} if made is None else made
		category = await BotSetup.category(guild, step.section, made)
		overwrites = BotSetup.overwrites(guild, step.section)
		async with BotSetup.creating(guild.id) :
			channel = None
			if step.forum :
				try :
					channel = await guild.create_forum(name=step.name, category=category, topic=step.description,
					                                   overwrites=overwrites, reason="/config setup")
				except discord.HTTPException as e :
					# Forums need a server that can have them (Discord answers 50024 or similar otherwise).
					logging.info(f"Could not create forum {step.name} in {guild.name}, using a text channel: {e}")
			if channel is None :
				channel = await guild.create_text_channel(name=step.name, category=category, topic=step.description,
				                                          overwrites=overwrites, reason="/config setup")
		BotSetup.set_channel(guild.id, step, channel)
		return channel

	# ============================================================
	@staticmethod
	async def create_roleplay_channel(guild: discord.Guild, made: dict | None = None) -> discord.TextChannel :
		made = {} if made is None else made
		category = await BotSetup.category(guild, ROLEPLAY, made)
		async with BotSetup.creating(guild.id) :
			channel = await guild.create_text_channel(name=ROLEPLAY_CHANNEL, category=category, topic=ROLEPLAY_TOPIC,
			                                          overwrites=BotSetup.overwrites(guild, ROLEPLAY),
			                                          reason="/config setup")
		BotSetup.add_roleplay_channel(guild.id, channel)
		return channel

	# ============================================================
	@staticmethod
	def missing_auto_permissions(guild: discord.Guild) -> list[str] :
		return check_missing_guild_permissions(guild, AUTO_PERMISSIONS) or []

	# ============================================================
	@staticmethod
	async def auto(guild: discord.Guild) -> SetupReport :
		"""Creates every channel that is not set, reusing channels that have the default name."""
		sync_server(guild)
		report = SetupReport()
		made = {}
		for step, channel in BotSetup.plan(guild) :
			if channel is not None :
				if BotSetup.current(guild, step) is None :
					BotSetup.set_channel(guild.id, step, channel)
				report.kept.append(step.key)
				continue
			await BotSetup.create(guild, step, made)
			report.created.append(step.key)
		if BotSetup.roleplay_channels(guild) :
			report.kept.append(ConfigMapping.XP_CHANNELS)
		else :
			existing = discord.utils.get(guild.text_channels, name=ROLEPLAY_CHANNEL)
			if existing is not None :
				BotSetup.add_roleplay_channel(guild.id, existing)
				report.kept.append(ConfigMapping.XP_CHANNELS)
			else :
				await BotSetup.create_roleplay_channel(guild, made)
				report.created.append(ConfigMapping.XP_CHANNELS)
		logging.info(f"Auto setup in {guild.name}: created {', '.join(report.created) or 'nothing'}")
		return report

	# == checking ==

	# ============================================================
	@staticmethod
	def problems(guild: discord.Guild) -> list[str] :
		"""What still stops a feature from working: unset required channels and missing permissions."""
		problems = []
		for step in CHANNEL_STEPS :
			if step.required and BotSetup.current(guild, step) is None :
				problems.append(f"The {step.title.lower()} channel is not set.")
		if missing := check_missing_guild_permissions(guild, CORE_GUILD_PERMISSIONS) :
			problems.append(f"Server-wide I'm missing: {', '.join(humanise(missing))}.")
		for step in CHANNEL_STEPS :
			channel = BotSetup.current(guild, step)
			if channel is None :
				continue
			needed = FORUM_PERMISSIONS if isinstance(channel, discord.ForumChannel) else POST_PERMISSIONS
			if missing := check_missing_channel_permissions(channel, needed) :
				problems.append(f"In {channel.mention} I'm missing: {', '.join(humanise(missing))}.")
		roleplay = BotSetup.roleplay_channels(guild)
		if not roleplay :
			problems.append("There are no roleplay channels, so nobody earns XP and nobody can post as a character.")
		for channel in roleplay :
			if missing := check_missing_channel_permissions(channel, ROLEPLAY_PERMISSIONS) :
				problems.append(f"In {channel.mention} I'm missing: {', '.join(humanise(missing))}.")
		return problems

	# ============================================================
	@staticmethod
	def summary(guild: discord.Guild, report: SetupReport | None = None) -> discord.Embed :
		"""The end of both setups: where everything is, what is still wrong and what to do next."""
		report = report or SetupReport()
		lines = []
		for step in CHANNEL_STEPS :
			channel = BotSetup.current(guild, step)
			new = " *(new)*" if step.key in report.created else ""
			lines.append(f"**{step.title}:** {channel.mention + new if channel else 'not set'}")
		roleplay = BotSetup.roleplay_channels(guild)
		new = " *(new)*" if ConfigMapping.XP_CHANNELS in report.created else ""
		lines.append(f"**Roleplay channels:** {', '.join(channel.mention for channel in roleplay) + new or 'none'}")

		problems = BotSetup.problems(guild)
		embed = discord.Embed(title="Setup finished" if not problems else "Setup finished, with things to fix",
		                      description="\n".join(lines), color=0x2ecc71 if not problems else 0xe67e22)
		if problems :
			embed.add_field(name="To fix", value="\n".join(f"- {problem}" for problem in problems)[:1024],
			                inline=False)

		steps = []
		if not LevelTransactions().get_all(guild.id) :
			steps.append("Add level roles with `/config roles`.")
		if not GearItemTransactions().get_all(guild.id) :
			steps.append("Fill the gear catalog with `/armory import` (a ready-made pack) or `/armory add`.")
		steps += [
			"Change the character sheet with `/sheet`, and add occupations with `/occupation add`.",
			"Numbers such as the character cap, SPECIAL rules, levelling speed and starting currency are in "
			"`/config characters`; the currency's name in `/config currency_name`.",
			"More roleplay channels: `/config channel`, `/config forum` or `/config category`.",
			"See everything with `/config view`.",
		]
		embed.add_field(name="Next", value="\n".join(f"- {step}" for step in steps)[:1024], inline=False)
		return embed
