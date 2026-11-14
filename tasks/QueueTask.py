import discord
from discord.ext import commands, tasks

from classes.kernel.Queue import Queue


class QueueTask(commands.Cog) :
	status = None

	def __init__(self, bot: commands.Bot) :
		self.bot = bot
		self.queue.start()
		self.display_status.start()

	def cog_unload(self) :
		self.queue.cancel()
		self.display_status.cancel()

	@tasks.loop(seconds=0.5)
	async def queue(self) :
		await Queue().start()

	@tasks.loop(seconds=3)
	async def display_status(self) :
		await self.bot.wait_until_ready()
		status = "over RMR"
		if not Queue().empty() :
			status = Queue().status()
		if self.status and self.status == status :
			return
		self.status = status
		await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=status))

	@queue.before_loop
	async def before_queue(self) :
		await self.bot.wait_until_ready()

	@display_status.before_loop
	async def before_display(self) :
		await self.bot.wait_until_ready()


async def setup(bot) :
	await bot.add_cog(QueueTask(bot))
