"""Ends market listings whose time ran out; the items go back to their sellers."""
import logging

from discord.ext import commands, tasks

from classes.economy.MarketFlow import MarketFlow


class MarketTask(commands.Cog) :

	def __init__(self, bot: commands.Bot) :
		self.bot = bot
		self.expiry.start()

	def cog_unload(self) :
		self.expiry.cancel()

	@tasks.loop(minutes=10)
	async def expiry(self) :
		try :
			await MarketFlow.tick(self.bot)
		except Exception as e :
			logging.error(f"Ending expired market listings failed: {e}", exc_info=True)

	@expiry.before_loop
	async def before_expiry(self) :
		await self.bot.wait_until_ready()


async def setup(bot) :
	await bot.add_cog(MarketTask(bot))
