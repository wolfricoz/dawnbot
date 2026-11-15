"""Checks fight timers: when a phase or turn runs out, those who did not act get an automatic move."""
import logging

from discord.ext import commands, tasks

from classes.combat.CombatFlow import CombatFlow


class CombatTask(commands.Cog) :

	def __init__(self, bot: commands.Bot) :
		self.bot = bot
		self.timers.start()

	def cog_unload(self) :
		self.timers.cancel()

	@tasks.loop(seconds=30)
	async def timers(self) :
		try :
			await CombatFlow.tick(self.bot)
		except Exception as e :
			logging.error(f"Checking fight timers failed: {e}", exc_info=True)

	@timers.before_loop
	async def before_timers(self) :
		await self.bot.wait_until_ready()


async def setup(bot) :
	await bot.add_cog(CombatTask(bot))
