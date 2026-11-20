"""Keeps an approved character's post in the server's character channel (CHARACTER) in step with its sheet.

In a forum the character gets its own thread; in a text channel it gets its own messages. A long sheet takes several
messages, one embed each; their ids are stored on the character so later changes edit them in place.
"""
import logging

import discord

from classes.characters.Card import Card
from classes.characters.ImageStorage import ImageStorage
from classes.kernel.ConfigData import ConfigData
from database.database import Characters
from database.transactions.CharacterTransactions import CharacterTransactions, DEAD, RETIRED

# States whose post says so and stays locked.
CLOSED = (RETIRED, DEAD)
from resources.configs.ConfigMapping import ConfigMapping

THREAD_NAME_LIMIT = 100


class ForumPost :

	# ============================================================
	@staticmethod
	async def _location(guild: discord.Guild, character: Characters) :
		"""Where the character's existing post lives: its thread, or the character channel. None when it is gone."""
		if character.forum_thread_id :
			thread = guild.get_channel_or_thread(character.forum_thread_id)
			if thread is None :
				try :
					thread = await guild.fetch_channel(character.forum_thread_id)
				except discord.HTTPException :
					return None
			return thread
		return await ConfigData().get_channel(guild, ConfigMapping.CHARACTER, optional=True)

	# ============================================================
	@staticmethod
	async def sync(bot: discord.Client, character: Characters) -> bool :
		"""Creates or updates the character's post.

		@return: False when the server has no character channel or the bot may not post there.
		"""
		guild = bot.get_guild(character.guild_id)
		if guild is None :
			return False
		# Only a retired or dead character's post says so; every other post is of an approved character.
		embeds = Card.embeds(character, show_state=character.state in CLOSED)
		avatar = await ImageStorage.file(bot, character.avatar_id)
		if avatar is not None :
			embeds[0].set_thumbnail(url=f"attachment://{avatar.filename}")
		try :
			if character.forum_message_ids and await ForumPost._update(guild, character, embeds, avatar) :
				return True
			return await ForumPost._create(guild, character, embeds, avatar)
		except discord.Forbidden :
			logging.warning(f"Missing permissions to post character {character.id} in {guild.name}")
			return False
		except discord.HTTPException as e :
			logging.error(f"Posting character {character.id} in {guild.name} failed: {e}", exc_info=True)
			return False

	# ============================================================
	@staticmethod
	def owner_ping(character: Characters) -> tuple[str, discord.AllowedMentions] :
		"""The line above a new post that pings the player whose character it is, and lets only them be pinged.

		In a forum the mention also adds them to the character's thread. Later edits of the post leave the line as it
		is and ping no one.
		"""
		return f"<@{character.uid}>", discord.AllowedMentions(everyone=False, roles=False,
		                                                      users=[discord.Object(id=character.uid)])

	# ============================================================
	@staticmethod
	async def _create(guild: discord.Guild, character: Characters, embeds: list[discord.Embed],
	                  avatar: discord.File | None) -> bool :
		channel = await ConfigData().get_channel(guild, ConfigMapping.CHARACTER, optional=True)
		if channel is None :
			return False
		files = [avatar] if avatar is not None else []
		content, mentions = ForumPost.owner_ping(character)
		thread_id = None
		if isinstance(channel, discord.ForumChannel) :
			created = await channel.create_thread(name=character.name[:THREAD_NAME_LIMIT], content=content,
			                                      embed=embeds[0], files=files, allowed_mentions=mentions)
			target, first = created.thread, created.message
			thread_id = target.id
		else :
			target = channel
			first = await channel.send(content, embed=embeds[0], files=files, allowed_mentions=mentions)
		message_ids = [first.id]
		for embed in embeds[1 :] :
			message_ids.append((await target.send(embed=embed)).id)
		CharacterTransactions().update(character.id, forum_thread_id=thread_id, forum_message_ids=message_ids)
		return True

	# ============================================================
	@staticmethod
	async def _update(guild: discord.Guild, character: Characters, embeds: list[discord.Embed],
	                  avatar: discord.File | None) -> bool :
		"""Edits the existing post to match the sheet. False when the post is gone and has to be made again."""
		target = await ForumPost._location(guild, character)
		if target is None :
			return False
		if isinstance(target, discord.Thread) :
			# Messages in an archived thread cannot be edited; a character that came back gets its thread opened.
			if target.archived or (target.locked and character.state not in CLOSED) :
				await target.edit(archived=False, locked=False if character.state not in CLOSED else target.locked)
			if target.name != character.name[:THREAD_NAME_LIMIT] :
				await target.edit(name=character.name[:THREAD_NAME_LIMIT])
		message_ids = list(character.forum_message_ids)
		try :
			first = await target.fetch_message(message_ids[0])
		except discord.NotFound :
			return False
		await first.edit(embed=embeds[0], attachments=[avatar] if avatar is not None else [])

		kept = [first.id]
		for index, embed in enumerate(embeds[1 :], start=1) :
			message = None
			if index < len(message_ids) :
				try :
					message = await target.fetch_message(message_ids[index])
					await message.edit(embed=embed)
				except discord.NotFound :
					message = None
			if message is None :
				message = await target.send(embed=embed)
			kept.append(message.id)
		for message_id in message_ids[len(embeds) :] :
			try :
				await (await target.fetch_message(message_id)).delete()
			except discord.NotFound :
				pass
		if kept != message_ids :
			CharacterTransactions().update(character.id, forum_message_ids=kept)
		return True

	# ============================================================
	@staticmethod
	async def retire(bot: discord.Client, character: Characters, lock: bool = False) -> None :
		"""Handles a retired character's post as the server's RETIRE_THREAD setting says: locked (marked retired, and
		in a forum locked and archived) or deleted. lock always locks it (a dead character's post)."""
		if not lock and str(ConfigData().get_key(character.guild_id, ConfigMapping.RETIRE_THREAD)).lower() == "delete" :
			await ForumPost.remove(bot, character)
			CharacterTransactions().update(character.id, forum_thread_id=None, forum_message_ids=None)
			return
		if not character.forum_message_ids :
			return
		await ForumPost.sync(bot, character)
		guild = bot.get_guild(character.guild_id)
		if guild is None or not character.forum_thread_id :
			return
		try :
			thread = await ForumPost._location(guild, character)
			if isinstance(thread, discord.Thread) :
				await thread.edit(locked=True, archived=True)
		except discord.HTTPException as e :
			logging.warning(f"Locking the post of retired character {character.id} failed: {e}")

	# ============================================================
	@staticmethod
	async def remove(bot: discord.Client, character: Characters) -> None :
		"""Deletes the character's post: its whole thread in a forum, its messages in a text channel."""
		guild = bot.get_guild(character.guild_id)
		if guild is None or not character.forum_message_ids :
			return
		try :
			target = await ForumPost._location(guild, character)
			if target is None :
				return
			if character.forum_thread_id :
				await target.delete()
				return
			for message_id in character.forum_message_ids :
				try :
					await (await target.fetch_message(message_id)).delete()
				except discord.NotFound :
					pass
		except discord.HTTPException as e :
			logging.warning(f"Removing the post of character {character.id} in {guild.name} failed: {e}")
