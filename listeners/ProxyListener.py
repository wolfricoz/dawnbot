import logging

import discord
from discord.ext import commands
from discord_py_utilities.messages import send_message

from classes.kernel.ConfigData import ConfigData
from classes.progression.Progression import Progression
from classes.proxy.Proxy import Proxy
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.ProxyTransactions import ProxyTransactions
from resources.configs.ConfigMapping import ConfigMapping
from views.buttons.RoleplayChannelPrompt import prompt_view

DELETE_EMOJI = "❌"
WHO_EMOJI = "❓"


class ProxyListener(commands.Cog) :
	"""Posts messages written as characters, and handles the reactions on those posts."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@commands.Cog.listener("on_message")
	async def on_message(self, message: discord.Message) :
		if message.guild is None or message.author.bot :
			return
		try :
			await Proxy.handle(self.bot, message)
		except Exception as e :
			logging.error(f"Posting message {message.id} as a character failed: {e}", exc_info=True)

	# ============================================================
	@commands.Cog.listener("on_raw_reaction_add")
	async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) :
		if payload.guild_id is None or payload.member is None or payload.member.bot :
			return
		emoji = str(payload.emoji)
		if emoji not in (DELETE_EMOJI, WHO_EMOJI) :
			return
		entry = ProxyTransactions().get(payload.message_id)
		if entry is None or entry.deleted :
			return
		guild = self.bot.get_guild(payload.guild_id)
		channel = guild.get_channel_or_thread(payload.channel_id) if guild else None
		if channel is None :
			return
		message = channel.get_partial_message(payload.message_id)
		member = payload.member
		if emoji == DELETE_EMOJI :
			if member.id == entry.uid or channel.permissions_for(member).manage_messages :
				await self.delete_post(channel, payload.message_id)
				return
		else :
			await self.who_wrote(member, entry)
		try :
			await message.remove_reaction(payload.emoji, member)
		except discord.HTTPException :
			pass

	# ============================================================
	@staticmethod
	async def delete_post(channel, message_id: int) -> None :
		"""Deletes every message of the post the message belongs to."""
		post = ProxyTransactions().get_post(message_id)
		for entry in post :
			try :
				await channel.get_partial_message(entry.message_id).delete()
			except discord.NotFound :
				pass
			except discord.HTTPException as e :
				logging.warning(f"Could not delete proxied message {entry.message_id}: {e}")
		ProxyTransactions().mark_deleted([entry.message_id for entry in post])

	# ============================================================
	@staticmethod
	async def who_wrote(member: discord.Member, entry) -> None :
		character = CharacterTransactions().get_by_id(entry.character_id) if entry.character_id else None
		as_who = f"as **{character.name}**" if character else "as a character that no longer exists"
		try :
			await member.send(f"That message in <#{entry.channel_id}> was written by <@{entry.uid}> {as_who}.")
		except discord.HTTPException :
			pass

	# ============================================================
	@commands.Cog.listener("on_raw_message_delete")
	async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) :
		if payload.guild_id is not None :
			ProxyTransactions().mark_deleted([payload.message_id])

	# ============================================================
	@commands.Cog.listener("on_raw_bulk_message_delete")
	async def on_raw_bulk_message_delete(self, payload: discord.RawBulkMessageDeleteEvent) :
		if payload.guild_id is not None :
			ProxyTransactions().mark_deleted(list(payload.message_ids))

	# ============================================================
	@commands.Cog.listener("on_guild_channel_create")
	async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) :
		"""Asks staff whether a new text channel or forum should be a roleplay channel."""
		if not isinstance(channel, (discord.TextChannel, discord.ForumChannel)) :
			return
		if Progression.is_tracked(channel) :
			return
		modlog = await ConfigData().get_channel(channel.guild, ConfigMapping.MODLOG, optional=True)
		if modlog is None :
			return
		await send_message(modlog, f"{channel.mention} was just created. Should it be a roleplay channel? Posts "
		                           f"there earn XP, and members can post as their characters there.",
		                   view=prompt_view(channel.id), error_mode="ignore")


async def setup(bot) :
	await bot.add_cog(ProxyListener(bot))
