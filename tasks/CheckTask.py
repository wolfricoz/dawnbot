"""Closes checks whose time ran out."""
import logging

from discord.ext import commands, tasks

from classes.checks.CheckFlow import CheckFlow


class CheckTask(commands.Cog) :

	def __init__(self, bot: commands.Bot) :
		self.bot = bot
		self.timers.start()

	def cog_unload(self) :
		self.timers.cancel()

	@tasks.loop(minutes=1)
	async def timers(self) :
		try :
			await CheckFlow.tick(self.bot)
		except Exception as e :
			logging.error(f"Closing expired checks failed: {e}", exc_info=True)

	@timers.before_loop
	async def before_timers(self) :
		await self.bot.wait_until_ready()


async def setup(bot) :
	await bot.add_cog(CheckTask(bot))
