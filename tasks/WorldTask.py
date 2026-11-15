"""Moves the world on: flowing in-world time (with the events and birthdays of new days), arrivals, and the timers
of the other roleplay tools (letters, job deadlines, fading rumors, idle scenes). Every job is guarded on its own, so
one failing doesn't stop the rest."""
import logging

from discord.ext import commands, tasks

from classes.world.TravelFlow import TravelFlow
from classes.world.WorldFlow import WorldFlow
from database.transactions.WorldTransactions import WorldTransactions


class WorldTask(commands.Cog) :

	def __init__(self, bot: commands.Bot) :
		self.bot = bot
		self.jobs = [("time", self.move_time), ("arrivals", self.arrivals), ("scenes", self.scenes), ("letters", self.letters),
		             ("jobs", self.jobs_due), ("rumors", self.rumors)]
		self.minute = 0
		self.loop.start()

	def cog_unload(self) :
		self.loop.cancel()

	# ============================================================
	@tasks.loop(minutes=1)
	async def loop(self) :
		self.minute += 1
		for name, job in self.jobs :
			try :
				await job()
			except Exception as e :
				logging.error(f"World task {name} failed: {e}", exc_info=True)

	# ============================================================
	async def move_time(self) :
		for calendar in WorldTransactions().calendars() :
			if self.bot.get_guild(calendar.guild_id) is None :
				continue
			lines = WorldFlow.tick(calendar.guild_id)
			if lines :
				await WorldFlow.announce(self.bot, calendar.guild_id, lines)

	# ============================================================
	async def arrivals(self) :
		await TravelFlow.arrivals(self.bot)

	# ============================================================
	async def scenes(self) :
		# Reminders are measured in hours, so every 5 minutes is plenty.
		if self.minute % 5 == 1 :
			from classes.scenes.SceneFlow import SceneFlow

			await SceneFlow.tick(self.bot)

	# ============================================================
	async def letters(self) :
		from classes.language.LetterFlow import LetterFlow

		await LetterFlow.deliver_due(self.bot)

	# ============================================================
	async def jobs_due(self) :
		from classes.economy.JobFlow import JobFlow

		await JobFlow.deadlines(self.bot)

	# ============================================================
	async def rumors(self) :
		from classes.flavor.RumorFlow import RumorFlow

		await RumorFlow.spread(self.bot)

	# ============================================================
	@loop.before_loop
	async def before_loop(self) :
		await self.bot.wait_until_ready()


async def setup(bot) :
	await bot.add_cog(WorldTask(bot))
