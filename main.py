# dependencies included in requirements.txt. To install do pip install -r requirements.txt
import asyncio
import logging
import os
from contextlib import asynccontextmanager

import discord
import sentry_sdk
from discord.ext import commands
from discord_py_utilities.exceptions import NoChannelException, NoPermissionException
from discord_py_utilities.messages import send_message
from fastapi import FastAPI

from data.env.loader import env, load_environment

# loads env and variables
load_environment()

import api
from classes.kernel.AccessControl import AccessControl
from classes.kernel.ConfigData import ConfigData
from classes.kernel.ServerSync import sync_server
from database import database
from database.exceptions.KeyNotFound import KeyNotFound
from database.transactions.UserTransactions import UserTransactions
from project.data import BOT_NAME, VERSION
from views.buttons.ReviewButtons import ReviewButtons
from views.buttons.RoleplayChannelPrompt import RoleplayChannelButton
from views.multiselect.StatPicker import StatButton, StatSelect
from views.buttons.SpeciesReviewButtons import SpeciesReviewButtons
from views.combat.AbilityReviewButtons import AbilityReviewButtons
from views.checks.CheckButtons import CheckButton
from views.combat.BoardButtons import CombatButton
from views.tables.TableButtons import TableRollButton

# Exceptions caused by a server's own setup (missing Discord permissions, an unset
# or deleted config channel), not by a bug in the bot. These are surfaced to the
# affected server/user by the code that raises them; reporting them to Sentry just
# creates noise, so we drop them before they become issues.
SENTRY_IGNORED_EXCEPTIONS = (
	discord.Forbidden,  # 403 Missing Permissions
	NoPermissionException,
	NoChannelException,
	KeyNotFound,
)


def _sentry_before_send(event, hint) :
	"""Drops user-setup faults (permissions/config) so only real bugs reach Sentry."""
	exc_info = hint.get("exc_info")
	if exc_info is not None and isinstance(exc_info[1], SENTRY_IGNORED_EXCEPTIONS) :
		return None
	return event


sentry_sdk.init(
	dsn=env("SENTRY_DSN"),
	send_default_pii=False,
	environment="development" if str(env('DEBUG')).upper() == "TRUE" else "production",
	release=VERSION,
	before_send=_sentry_before_send,
)

# Creates database
database.database().create()

# declares the bots intent, these are required to view message content and the members in the guild.
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
activity = discord.Activity(type=discord.ActivityType.playing, name="Gamemaster Ultimate")
bot = commands.Bot(command_prefix=env('PREFIX', '?'), case_insensitive=False, intents=intents, activity=activity)


@asynccontextmanager
async def lifespan(app: FastAPI) :
	# Starts the bot in an async task; run.bat sets this up through uvicorn.
	async def run_bot() :
		try :
			await bot.start(env('TOKEN'))
		except asyncio.CancelledError :
			# Graceful cancellation
			await bot.close()
			raise
		except Exception as e :
			logging.error(f"Failed to start {BOT_NAME}: {e}", exc_info=True)

	logging.info("Starting bot...")
	bot_task = asyncio.create_task(run_bot())
	app.state.bot = bot
	try :
		yield
	finally :
		# Trigger shutdown if still running
		if not bot.is_closed() :
			await bot.close()
		# Ensure the task finishes
		if not bot_task.done() :
			bot_task.cancel()
			try :
				await bot_task
			except asyncio.CancelledError :
				pass


app = FastAPI(lifespan=lifespan,
              docs_url=None,
              redoc_url=None,
              openapi_url=None,
              )
routers = []
# Loops through all the routers in the api folder and includes them in the FastAPI app.
for router in api.__all__ :
	try :
		app.include_router(getattr(api, router))
		routers.append(router)
	except Exception as e :
		logging.error(f"Failed to load {router}: {e}")


# ============================================================
async def send_dev_message(message: str) :
	dev_channel = bot.get_channel(int(env('DEVCHANNEL', 0)))
	if dev_channel is None :
		logging.warning(f"Dev channel {env('DEVCHANNEL', 0)} not found")
		return
	await send_message(dev_channel, message, error_mode='ignore')


# ============================================================
@bot.event
async def on_ready() :
	for guild in bot.guilds :
		try :
			sync_server(guild)
			UserTransactions().sync_guild(guild.id, [member.id for member in guild.members if not member.bot])
		except Exception as e :
			logging.error(f"Failed to sync {guild.name}: {e}", exc_info=True)
	# Imports any config left in the old jsons/ folder, then loads every guild's config.
	ConfigData().migrate()
	ConfigData().load(bot.guilds)
	AccessControl().reload()

	await send_dev_message(f"{BOT_NAME} version {VERSION} is in {len(bot.guilds)} servers and has started up successfully!")
	# Synchronises the slash commands with discord.
	await bot.tree.sync()
	logging.info("Commands synced, start up _done_")


# ============================================================
@bot.event
async def setup_hook() :
	# Persistent views must be registered on every start, or their buttons stop working after a restart.
	bot.add_view(ReviewButtons())
	bot.add_view(SpeciesReviewButtons())
	bot.add_view(AbilityReviewButtons())
	bot.add_dynamic_items(RoleplayChannelButton, StatSelect, StatButton, CombatButton, CheckButton, TableRollButton)

	directories = ["modules", "listeners", "tasks"]
	loaded = []
	for directory in directories :
		if not os.path.isdir(directory) :
			os.mkdir(directory)
		for filename in os.listdir(directory) :
			if filename.endswith('.py') :
				await bot.load_extension(f"{directory}.{filename[:-3]}")
				loaded.append(f"{directory}.{filename[:-3]}")
	logging.info(f'Loaded {len(loaded)} modules: {", ".join(loaded)}')


# ============================================================
@bot.event
async def on_guild_join(guild: discord.Guild) -> None :
	membercount = len([m for m in guild.members if not m.bot])
	await send_dev_message(f"{BOT_NAME} is now in {len(bot.guilds)} servers! It just joined:"
	                       f"\nGuild: `{guild}({guild.id})`"
	                       f"\nOwner: `{guild.owner}({guild.owner_id})`"
	                       f"\nMember count: {membercount}")


# runs the bot with the token when not started through uvicorn
if env('API') != "TRUE" and __name__ == "__main__" :
	bot.run(env('TOKEN'))
