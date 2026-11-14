"""Posts a member's message as their character: the webhook post, removing the original, the log and the rewards."""
import logging

import discord
from discord_py_utilities.messages import send_message

from classes.characters.ImageStorage import ImageStorage
from classes.characters.Special import Special
from classes.kernel.ConfigData import ConfigData
from classes.progression.Progression import Progression
from classes.proxy.Compose import Compose
from classes.proxy.Matcher import Match, Matcher
from classes.proxy.WebhookManager import WebhookManager
from classes.support.PermissionNotice import PermissionNotice
from database.database import Characters
from database.transactions.ExperienceTransactions import ExperienceTransactions
from database.transactions.ProxyTransactions import ProxyTransactions
from resources.configs.ConfigMapping import ConfigMapping

# What decide() can answer.
IGNORE = "ignore"
TOO_SHORT = "too_short"
PROXY = "proxy"

# What the bot needs in a channel to post as characters there.
NEEDED_PERMISSIONS = ["manage_webhooks", "manage_messages"]

TOO_LARGE = ("Your attachments are larger than this server allows the bot to upload, so I left your message as it "
             "is. Please send smaller files.")


class Proxy :

	# ============================================================
	@staticmethod
	def decide(in_roleplay_channel: bool, outside_allowed: bool, long_enough: bool) -> str :
		"""Whether a message written as a character is posted, removed for being too short, or left alone."""
		if not in_roleplay_channel :
			return PROXY if outside_allowed else IGNORE
		return PROXY if long_enough else TOO_SHORT

	# ============================================================
	@staticmethod
	def missing_permissions(channel, me: discord.Member) -> list[str] :
		permissions = channel.permissions_for(me)
		return [name for name in NEEDED_PERMISSIONS if not getattr(permissions, name)]

	# ============================================================
	@staticmethod
	async def reply_line(message: discord.Message) -> tuple[str | None, int | None] :
		"""The reply line for a message that replies to another, and the player it may ping for a proxied message."""
		reference = message.reference
		if reference is None or reference.message_id is None :
			return None, None
		target = reference.resolved
		if target is None :
			try :
				target = await message.channel.fetch_message(reference.message_id)
			except discord.HTTPException :
				return None, None
		if not isinstance(target, discord.Message) :
			return None, None
		if target.webhook_id is not None :
			entry = ProxyTransactions().get(target.id)
			if entry is None :
				return Compose.reply_line(target.content, target.jump_url, None, target.author.display_name), None
			return Compose.reply_line(target.content, target.jump_url, entry.uid, target.author.display_name), entry.uid
		return Compose.reply_line(target.content, target.jump_url, target.author.id), None

	# ============================================================
	@staticmethod
	async def handle(bot: discord.Client, message: discord.Message) -> bool :
		"""Posts the message as a character when it is written as one. Returns True when it was handled."""
		match = Matcher.find(message)
		if match is None :
			return False
		guild = message.guild
		channel = message.channel
		in_roleplay = Progression.is_tracked(channel)
		outside_allowed = ConfigData().get_toggle(guild.id, ConfigMapping.PROXY_OUTSIDE_RP)
		decision = Proxy.decide(in_roleplay, outside_allowed, Progression.check_size(message, match.text))
		if decision == IGNORE :
			return False

		missing = Proxy.missing_permissions(channel, guild.me)
		if missing :
			await PermissionNotice().notify(guild, missing, channel=channel, source="event", user=message.author)
			return False
		if decision == TOO_SHORT :
			# Imported here: the listener module imports this one.
			from listeners.ProgressionListener import ProgressionListener
			await ProgressionListener.remove_short_message(message)
			return True

		if sum(attachment.size for attachment in message.attachments) > guild.filesize_limit :
			await Proxy._tell(message, TOO_LARGE)
			return True
		message_ids = await Proxy._post(bot, message, match)
		if not message_ids :
			return True
		try :
			await message.delete()
		except discord.NotFound :
			pass
		await Proxy._reward(bot, message, match, message_ids, in_roleplay)
		return True

	# ============================================================
	@staticmethod
	async def _tell(message: discord.Message, text: str) -> None :
		try :
			await message.author.send(text)
		except discord.HTTPException :
			await send_message(message.channel, f"{message.author.mention} {text}", error_mode="ignore")

	# ============================================================
	@staticmethod
	async def _post(bot: discord.Client, message: discord.Message, match: Match) -> list[int] :
		"""Sends the post through the channel's webhook. Returns the ids of the messages sent (empty on failure)."""
		character = match.character
		line, replied_player = await Proxy.reply_line(message)
		chunks = Compose.split(match.text, line)
		mentions = Compose.allowed_mentions(message, replied_player)
		avatar_url = await ImageStorage.url(bot, character.avatar_id)
		thread = message.channel if isinstance(message.channel, discord.Thread) else discord.utils.MISSING

		for attempt in range(2) :
			sent = []
			try :
				webhook = await WebhookManager().get(bot, message.channel)
				files = [await attachment.to_file(spoiler=attachment.is_spoiler())
				         for attachment in message.attachments]
				for index, chunk in enumerate(chunks) :
					last = index == len(chunks) - 1
					posted = await webhook.send(content=chunk or discord.utils.MISSING, username=character.name,
					                            avatar_url=avatar_url or discord.utils.MISSING,
					                            files=files if last and files else discord.utils.MISSING,
					                            allowed_mentions=mentions, thread=thread, wait=True)
					sent.append(posted.id)
				return sent
			except discord.NotFound :
				# The webhook was deleted by someone; make a new one and try once more.
				WebhookManager().forget(message.channel)
				await Proxy._remove(message.channel, sent)
				if attempt == 1 :
					break
			except discord.HTTPException as e :
				logging.warning(f"Posting as character {character.id} in {message.guild.name} failed: {e}")
				await Proxy._remove(message.channel, sent)
				break
		await Proxy._tell(message, "I could not post that as your character, so I left your message as it is.")
		return []

	# ============================================================
	@staticmethod
	async def _remove(channel, message_ids: list[int]) -> None :
		"""Removes the parts of a post that did get sent, so a failed post leaves nothing half done."""
		for message_id in message_ids :
			try :
				await channel.get_partial_message(message_id).delete()
			except discord.HTTPException :
				pass

	# ============================================================
	@staticmethod
	async def _reward(bot: discord.Client, message: discord.Message, match: Match, message_ids: list[int],
	                  in_roleplay: bool) -> None :
		"""Logs the post and, in a roleplay channel, gives XP to the character and the member and currency to the
		character."""
		guild = message.guild
		character = match.character
		xp = Progression.xp_for(guild.id, match.text) if in_roleplay else 0
		currency = Progression.currency_for(guild.id, match.text) if in_roleplay else 0
		ProxyTransactions().log(message_ids, character.id, message.author.id, guild.id, message.channel.id,
		                        len(match.text), in_roleplay, xp, currency)
		if not in_roleplay :
			return
		updated, gained = Special.add_xp(character, xp, currency)
		record = ExperienceTransactions().add_xp(message.author.id, guild.id, xp, count_message=xp > 0)
		if isinstance(message.author, discord.Member) :
			await Progression.announce_level(message.author, record.xp)
		if gained and updated is not None :
			await Proxy.announce_character_level(bot, updated, gained)

	# ============================================================
	@staticmethod
	async def announce_character_level(bot: discord.Client, character: Characters, gained: int) -> None :
		"""Announces a character's new level and refreshes its post, which shows the level."""
		from classes.characters.ForumPost import ForumPost

		guild = bot.get_guild(character.guild_id)
		if guild is None :
			return
		points = character.unspent_points
		channel = await ConfigData().get_channel(guild, ConfigMapping.ANNOUNCEMENT, optional=True)
		if channel is not None :
			await send_message(channel, f"**{character.name}** (<@{character.uid}>) reached level {character.level}! "
			                            f"They have {points} unspent SPECIAL point{'s' if points != 1 else ''}; spend "
			                            f"them with `/character spend`.", error_mode="ignore")
		await ForumPost.sync(bot, character)
