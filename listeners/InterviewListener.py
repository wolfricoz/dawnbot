import logging

import discord
from discord.ext import commands

from classes.characters.CharacterFlow import CharacterFlow


class InterviewListener(commands.Cog) :
	"""Passes DMs to the character interview of the member who sent them."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@commands.Cog.listener("on_message")
	async def on_message(self, message: discord.Message) :
		if message.guild is not None or message.author.bot :
			return
		try :
			await CharacterFlow.handle_dm(self.bot, message)
		except Exception as e :
			logging.error(f"Interview of {message.author.id} failed: {e}", exc_info=True)
			await CharacterFlow.send_dm(message.author,
			                            "Something went wrong on my side. Your answers so far are saved; please send "
			                            "that again in a moment.")


async def setup(bot) :
	await bot.add_cog(InterviewListener(bot))
