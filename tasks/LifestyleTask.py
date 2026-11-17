"""Charges characters' weekly lifestyle on servers that use lifestyles."""
import logging

from discord.ext import commands, tasks

from classes.economy import Lifestyle


class LifestyleTask(commands.Cog) :

	def __init__(self, bot: commands.Bot) :
		self.bot = bot
		self.weekly.start()

	def cog_unload(self) :
		self.weekly.cancel()

	@tasks.loop(hours=1)
	async def weekly(self) :
		try :
			Lifestyle.weekly_all()
		except Exception as e :
			logging.error(f"Charging lifestyles failed: {e}", exc_info=True)

	@weekly.before_loop
	async def before_weekly(self) :
		await self.bot.wait_until_ready()


async def setup(bot) :
	await bot.add_cog(LifestyleTask(bot))
