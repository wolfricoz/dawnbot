"""Builds the text of a proxied post: the reply line, splitting long posts, and who may be pinged."""
import discord

from classes.characters.Card import chunk_text

# Webhook messages can hold 2000 characters; members with Nitro can send 4000.
MESSAGE_LIMIT = 2000
REPLY_SNIPPET = 80
# Marks the first line of a proxied reply, so it can be kept when the post is edited.
REPLY_MARK = "-# ↪ "


class Compose :

	# ============================================================
	@staticmethod
	def snippet(text: str, limit: int = REPLY_SNIPPET) -> str :
		"""The start of a message on one line, without the reply line it may have, for quoting."""
		if text.startswith(REPLY_MARK) :
			text = text.split("\n", 1)[1] if "\n" in text else ""
		text = " ".join(text.split())
		# Characters that would break the [text](link) around the quote.
		text = text.replace("[", "(").replace("]", ")")
		if not text :
			return "a message"
		return text if len(text) <= limit else f"{text[:limit - 1]}…"

	# ============================================================
	@staticmethod
	def reply_line(target_text: str, jump_url: str, user_id: int | None, name: str | None = None) -> str :
		"""`-# ↪ Replying to @user: [quote](link)`.

		For a proxied message the character's name goes first, `Aria (@user)`; a message from someone who cannot be
		mentioned (another bot's webhook) shows only its name.
		"""
		if user_id is None :
			who = f"**{name or 'someone'}**"
		else :
			who = f"{name} (<@{user_id}>)" if name else f"<@{user_id}>"
		return f"{REPLY_MARK}Replying to {who}: [{Compose.snippet(target_text)}]({jump_url})"

	# ============================================================
	@staticmethod
	def strip_reply_line(content: str) -> tuple[str | None, str] :
		"""Splits a proxied message into its reply line (or None) and the rest."""
		if content.startswith(REPLY_MARK) :
			line, _, rest = content.partition("\n")
			return line, rest
		return None, content

	# ============================================================
	@staticmethod
	def split(text: str, reply_line: str | None = None) -> list[str] :
		"""The messages a post takes; the reply line goes on the first one."""
		if reply_line :
			text = f"{reply_line}\n{text}" if text else reply_line
		return [chunk for chunk in chunk_text(text, MESSAGE_LIMIT) if chunk] or [""]

	# ============================================================
	@staticmethod
	def allowed_mentions(message: discord.Message, extra_user: int | None = None) -> discord.AllowedMentions :
		"""Lets the post ping exactly who the member's own message would have pinged.

		Members the message mentions (which includes the author of a message replied to with pinging on) can be
		pinged; extra_user is the player behind a proxied message that was replied to. @everyone and roles follow
		the member's permissions.
		"""
		users = list({user.id : user for user in message.mentions}.values())
		if extra_user is not None and all(user.id != extra_user for user in users) :
			users.append(discord.Object(id=extra_user))
		can_mention_everyone = message.channel.permissions_for(message.author).mention_everyone
		roles = True if can_mention_everyone else [role for role in message.role_mentions if role.mentionable]
		return discord.AllowedMentions(everyone=can_mention_everyone, users=users, roles=roles, replied_user=False)

	# ============================================================
	@staticmethod
	def kept_mentions(message: discord.Message) -> discord.AllowedMentions :
		"""The mentions an edit of a proxied post may keep: the ones the post already pings.

		Discord reads the mentions of a message again on every edit, so an edit that allows none takes the ping off
		the post (the reply ping among them) and it no longer shows as a mention. An edit never notifies anyone again,
		and it cannot ping anyone the post did not already ping.
		"""
		return discord.AllowedMentions(everyone=message.mention_everyone, users=list(message.mentions),
		                               roles=list(message.role_mentions), replied_user=False)
