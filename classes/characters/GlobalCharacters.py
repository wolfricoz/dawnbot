"""Global characters: a player can let an approved character's sheet be viewed on their small servers.

A small server has fewer than 10 members, bots not counted. On a small server, /character show and /character list
also find the player's global characters from their other servers. Those characters are only shown there: they keep
posting, growing and being reviewed on their own server.
"""
import discord

from classes.setup.Safeguards import human_member_count
from database.database import Characters
from database.transactions.CharacterTransactions import CharacterTransactions

# Servers with fewer members than this (bots not counted) show global characters.
SMALL_SERVER_LIMIT = 10


class GlobalCharacters :

	# ============================================================
	@staticmethod
	def is_small(guild: discord.Guild) -> bool :
		return human_member_count(guild) < SMALL_SERVER_LIMIT

	# ============================================================
	@staticmethod
	def visible(guild: discord.Guild, user_id: int) -> list[Characters] :
		"""The member's global characters from other servers that can be viewed here (none on bigger servers)."""
		if not GlobalCharacters.is_small(guild) :
			return []
		return CharacterTransactions().get_global(user_id, guild.id)

	# ============================================================
	@staticmethod
	def find(guild: discord.Guild, user_id: int, name: str) -> Characters | None :
		"""One of the member's global characters visible here, by name (compared without case)."""
		return next((character for character in GlobalCharacters.visible(guild, user_id)
		             if character.name.lower() == name.lower()), None)

	# ============================================================
	@staticmethod
	def home_name(bot: discord.Client, character: Characters) -> str :
		guild = bot.get_guild(character.guild_id)
		return guild.name if guild else "another server"
