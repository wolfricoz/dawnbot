"""The GM roll log: when a server sets GM_ROLL_LOG, every secret roll (secret and passive checks, secret dice and
secret table rolls) is copied there, so the server can audit them."""
import logging

import discord
from discord_py_utilities.messages import send_message

from classes.kernel.ConfigData import ConfigData
from resources.configs.ConfigMapping import ConfigMapping


# ============================================================
async def post(guild: discord.Guild | None, text: str) -> None :
	if guild is None :
		return
	try :
		channel = await ConfigData().get_channel(guild, ConfigMapping.GM_ROLL_LOG, optional=True)
	except Exception as e :
		logging.warning(f"Could not read the GM roll log channel of {guild.name}: {e}")
		return
	if channel is None :
		return
	await send_message(channel, text[:2000], error_mode="ignore")
