"""XP, currency and level roles earned by posting in the configured XP channels."""
import logging
from typing import Awaitable, Callable

import discord

from classes.kernel.ConfigData import ConfigData
from database.database import Experience
from database.transactions.ExperienceTransactions import ExperienceTransactions
from database.transactions.LevelTransactions import LevelTransactions
from database.transactions.UserTransactions import UserTransactions
from resources.configs.ConfigMapping import ConfigMapping, defaults

# Messages up to this length earn no XP (currency is still awarded).
XP_MINIMUM_LENGTH = 50
# Messages up to this length are removed from XP channels, unless the author can manage messages.
MINIMUM_POST_LENGTH = 300


class Progression :

	# ============================================================
	@staticmethod
	def is_tracked(channel: discord.abc.GuildChannel | discord.Thread) -> bool :
		"""A channel earns XP when it, or for threads its parent channel, is in the guild's XP channels."""
		tracked = ConfigData().get_list(channel.guild.id, ConfigMapping.XP_CHANNELS)
		if channel.id in tracked :
			return True
		return isinstance(channel, discord.Thread) and channel.parent_id in tracked

	# ============================================================
	@staticmethod
	def check_size(message: discord.Message) -> bool :
		"""False when the message is too short for an XP channel and should be removed."""
		if len(message.content) <= XP_MINIMUM_LENGTH and message.mentions :
			return True
		if len(message.content) <= MINIMUM_POST_LENGTH and not message.author.guild_permissions.manage_messages :
			return False
		return True

	# ============================================================
	@staticmethod
	def _gain(guild_id: int, key: ConfigMapping) -> int :
		"""Characters needed per point; a missing or non-positive setting falls back to the default."""
		value = ConfigData().get_int(guild_id, key)
		if not value or value <= 0 :
			return defaults[key]
		return value

	# ============================================================
	@staticmethod
	def xp_for(guild_id: int, content: str) -> int :
		if len(content) <= XP_MINIMUM_LENGTH :
			return 0
		return round(len(content) / Progression._gain(guild_id, ConfigMapping.XP_GAIN))

	# ============================================================
	@staticmethod
	def currency_for(guild_id: int, content: str) -> int :
		return round(len(content) / Progression._gain(guild_id, ConfigMapping.CURRENCY_GAIN))

	# ============================================================
	@staticmethod
	def award(message: discord.Message) -> Experience :
		"""Awards XP and currency for one message and returns the user's updated progression."""
		guild_id = message.guild.id
		xp = Progression.xp_for(guild_id, message.content)
		currency = Progression.currency_for(guild_id, message.content)
		ExperienceTransactions().add_currency(message.author.id, guild_id, currency)
		record = ExperienceTransactions().add_xp(message.author.id, guild_id, xp, count_message=xp > 0)
		logging.debug(f"{message.author} gained {xp} xp and {currency} currency in {message.guild.name}")
		return record

	# == level roles ==

	# ============================================================
	@staticmethod
	def level_roles(guild: discord.Guild) -> list[discord.Role] :
		roles = [guild.get_role(level.role_id) for level in LevelTransactions().get_all(guild.id)]
		return [role for role in roles if role is not None]

	# ============================================================
	@staticmethod
	async def update_level_roles(member: discord.Member, xp: int) -> discord.Role | None :
		"""Gives the member the level role their XP has reached and removes their other level roles.

		@return: the role when the member newly reached it, otherwise None.
		"""
		role_id = LevelTransactions().highest_reached(member.guild.id, xp)
		new_rank = member.guild.get_role(role_id) if role_id else None
		if new_rank is None :
			return None
		outdated = [role for role in Progression.level_roles(member.guild) if role in member.roles and role != new_rank]
		if outdated :
			await member.remove_roles(*outdated, reason="Level role replaced")
		if new_rank in member.roles :
			return None
		await member.add_roles(new_rank, reason=f"Reached {xp} xp")
		return new_rank

	# == recounting ==

	# ============================================================
	@staticmethod
	async def count_history(channel: discord.TextChannel | discord.ForumChannel | discord.Thread) -> int :
		"""Awards XP and currency for every past message in the channel, its threads and archived threads.

		@return: the number of messages counted.
		"""
		count = 0
		if isinstance(channel, discord.Thread) :
			async for message in channel.history(limit=None) :
				if message.author.bot :
					continue
				Progression.award(message)
				count += 1
			return count

		if isinstance(channel, discord.TextChannel) :
			async for message in channel.history(limit=None) :
				if message.author.bot :
					continue
				Progression.award(message)
				count += 1

		threads = list(channel.threads)
		async for thread in channel.archived_threads(limit=None) :
			threads.append(thread)
		for thread in threads :
			count += await Progression.count_history(thread)
		return count

	# ============================================================
	@staticmethod
	async def recount(guild: discord.Guild,
	                  on_progress: Callable[[str], Awaitable[None]] | None = None) -> int :
		"""Resets every member's progression in the guild and counts all XP channels again.

		@return: the number of messages counted.
		"""

		async def progress(text: str) :
			logging.info(f"Recount {guild.name}: {text}")
			if on_progress is not None :
				await on_progress(text)

		members = [member.id for member in guild.members if not member.bot]
		for uid in members :
			UserTransactions().delete(uid, guild.id)
		UserTransactions().sync_guild(guild.id, members)
		await progress(f"Reset {len(members)} users, starting to calculate currency and xp now")

		total = 0
		for channel_id in ConfigData().get_list(guild.id, ConfigMapping.XP_CHANNELS) :
			channel = guild.get_channel_or_thread(channel_id)
			if channel is None :
				logging.warning(f"Recount: channel {channel_id} not found in {guild.name}")
				continue
			if not isinstance(channel, (discord.TextChannel, discord.ForumChannel)) :
				# Tracked threads are counted through their parent channel.
				continue
			await progress(f"Calculating {channel.mention}")
			total += await Progression.count_history(channel)
		await progress(f"Finished recounting {total} messages")
		return total
