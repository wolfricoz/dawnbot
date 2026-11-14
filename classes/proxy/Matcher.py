"""Decides whether a message should be posted as one of the author's characters, and which one."""
from dataclasses import dataclass

import discord

from database.database import Characters
from database.transactions.AutoproxyTransactions import AutoproxyTransactions
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions

# A message that starts with this is never posted as a character, even with autoproxy on.
ESCAPE = "\\"
# Discord channels proxying works in: text channels and the threads under text channels and forums.
PROXY_CHANNEL_TYPES = (discord.ChannelType.text, discord.ChannelType.news, discord.ChannelType.public_thread,
                       discord.ChannelType.private_thread, discord.ChannelType.news_thread)


@dataclass
class Match :
	character: Characters
	# The message without the prefix and suffix.
	text: str
	autoproxy: bool = False


class Matcher :

	# ============================================================
	@staticmethod
	def strip(content: str, prefix: str | None, suffix: str | None) -> str | None :
		"""The content without the prefix and suffix (compared without case), or None when it does not use them."""
		prefix, suffix = prefix or "", suffix or ""
		if not prefix and not suffix :
			return None
		if len(content) < len(prefix) + len(suffix) :
			return None
		if not content.lower().startswith(prefix.lower()) or not content.lower().endswith(suffix.lower()) :
			return None
		return content[len(prefix) :len(content) - len(suffix)].strip()

	# ============================================================
	@staticmethod
	def match(content: str, has_attachments: bool, characters: list[Characters],
	          autoproxy: Characters | None = None) -> Match | None :
		"""Picks the character a message is written as.

		A prefix or suffix wins over autoproxy; when several characters fit, the one with the longest prefix and suffix
		wins (so `A:` and `Ab:` can both be used). A post needs text or an attachment.
		"""
		if content.startswith(ESCAPE) :
			return None
		best = None
		for character in characters :
			text = Matcher.strip(content, character.prefix, character.suffix)
			if text is None or (not text and not has_attachments) :
				continue
			length = len(character.prefix or "") + len(character.suffix or "")
			if best is None or length > best[0] :
				best = (length, Match(character, text))
		if best is not None :
			return best[1]
		if autoproxy is not None and (content.strip() or has_attachments) :
			return Match(autoproxy, content.strip(), autoproxy=True)
		return None

	# ============================================================
	@staticmethod
	def channel_ids(channel) -> list[int] :
		"""The channel, and for a thread also its parent: the places autoproxy can be set for this message."""
		ids = [channel.id]
		if isinstance(channel, discord.Thread) and channel.parent_id :
			ids.append(channel.parent_id)
		return ids

	# ============================================================
	@staticmethod
	def find(message: discord.Message) -> Match | None :
		"""The character this message should be posted as, or None when it is posted as the member themself."""
		if message.guild is None or message.author.bot or message.webhook_id is not None :
			return None
		if message.type not in (discord.MessageType.default, discord.MessageType.reply) :
			return None
		if message.channel.type not in PROXY_CHANNEL_TYPES or message.stickers :
			return None
		# A forum post's opening message cannot be removed without removing the whole post.
		if message.id == message.channel.id :
			return None
		characters = CharacterTransactions().get_all(message.author.id, message.guild.id, states=[APPROVED])
		if not characters :
			return None
		autoproxy = None
		autoproxy_id = AutoproxyTransactions().get(message.author.id, Matcher.channel_ids(message.channel))
		if autoproxy_id is not None :
			autoproxy = next((character for character in characters if character.id == autoproxy_id), None)
		return Matcher.match(message.content, bool(message.attachments), characters, autoproxy)
