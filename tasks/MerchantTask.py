"""Restocks merchants whose daily or weekly restock has come."""
import logging

from discord.ext import commands, tasks

from classes.economy import Merchants


class MerchantTask(commands.Cog) :

	def __init__(self, bot: commands.Bot) :
		self.bot = bot
		self.restocks.start()

	def cog_unload(self) :
		self.restocks.cancel()

	@tasks.loop(minutes=15)
	async def restocks(self) :
		try :
			Merchants.restock_due()
		except Exception as e :
			logging.error(f"Restocking merchants failed: {e}", exc_info=True)

	@restocks.before_loop
	async def before_restocks(self) :
		await self.bot.wait_until_ready()


async def setup(bot) :
	await bot.add_cog(MerchantTask(bot))
