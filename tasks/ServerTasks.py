import asyncio
import logging

from discord.ext import tasks
from discord.ext.commands import Bot, Cog

from classes.kernel.AccessControl import AccessControl
from classes.kernel.ServerSync import sync_server
from classes.support.PermissionNotice import PermissionNotice
from database.transactions.ServerTransactions import ServerTransactions


class ServerTasks(Cog) :
	"""Keeps the servers table in sync with the guilds the bot is in and checks its permissions there."""

	def __init__(self, bot: Bot) :
		self.bot = bot
		self.update_servers.start()

	def cog_unload(self) -> None :
		self.update_servers.cancel()

	# ============================================================
	@tasks.loop(hours=1)
	async def update_servers(self) :
		logging.info("Updating server list...")
		count = 0

		# Every server starts inactive; the ones the bot is still in are marked active again below.
		ServerTransactions().set_all_inactive()

		for guild in self.bot.guilds :
			if count % 10 == 0 :
				# prevents blocking the event loop for too long
				await asyncio.sleep(0)
			count += 1
			try :
				sync_server(guild)
			except Exception as e :
				logging.error(f"Failed to update {guild.name}: {e}", exc_info=True)
				continue
			# Notify the server if we're missing any core permissions. Throttled to
			# once per hour per distinct problem, so this hourly loop won't spam.
			await PermissionNotice().check_guild(guild, source="loop")
		AccessControl().reload()
		logging.info(f"Updated {count} servers!")

	# ============================================================
	@update_servers.before_loop
	async def before_update_servers(self) :
		await self.bot.wait_until_ready()


async def setup(bot: Bot) :
	await bot.add_cog(ServerTasks(bot))
