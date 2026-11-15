import logging

import discord
from discord.ext import commands

from classes.kernel.ConfigData import ConfigData
from classes.kernel.ServerSync import sync_server
from classes.proxy.Matcher import Matcher
from classes.progression.Progression import MINIMUM_POST_LENGTH, Progression
from database.transactions.UserTransactions import UserTransactions

TOO_SHORT = (f"Your message is too short, please make it longer than {MINIMUM_POST_LENGTH} characters. "
             f"No XP has been awarded and your post has been removed.")


# Currency belongs to characters and is earned by posting as one (see the ProxyListener).
class ProgressionListener(commands.Cog) :
	"""Awards members XP for posts in the XP channels and keeps members registered."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@commands.Cog.listener("on_message")
	async def on_message(self, message: discord.Message) :
		if message.guild is None or message.author.bot :
			return
		if message.channel.type not in (discord.ChannelType.text, discord.ChannelType.public_thread) :
			return
		if not Progression.is_tracked(message.channel) :
			return
		# Posts written as a character are handled, and rewarded, by the ProxyListener.
		if Matcher.find(message) is not None :
			return

		# A forum post's opening message has the same id as the thread; it is never removed for its length.
		is_starter = message.id == message.channel.id
		if not Progression.check_size(message) and not is_starter :
			await self.remove_short_message(message)
			return

		record = Progression.award(message)
		await Progression.announce_level(message.author, record.xp)

	# ============================================================
	@staticmethod
	async def remove_short_message(message: discord.Message) :
		try :
			await message.author.send(f"{TOO_SHORT}\n {message.content}")
		except discord.Forbidden :
			await message.channel.send(
				f"{message.author.mention} {TOO_SHORT} **The bot could not DM you, please open your dms.**\n {message.content}")
		try :
			await message.delete()
		except discord.NotFound :
			pass

	# ============================================================
	@commands.Cog.listener("on_member_join")
	async def on_member_join(self, member: discord.Member) :
		if member.bot :
			return
		UserTransactions().add(member.id, member.guild.id)

	# ============================================================
	@commands.Cog.listener("on_guild_join")
	async def on_guild_join(self, guild: discord.Guild) :
		try :
			sync_server(guild)
			ConfigData().load_guild(guild.id)
			UserTransactions().sync_guild(guild.id, [member.id for member in guild.members if not member.bot])
		except Exception as e :
			logging.error(f"Failed to register {guild.name}: {e}", exc_info=True)


async def setup(bot) :
	await bot.add_cog(ProgressionListener(bot))
