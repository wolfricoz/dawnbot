"""This class is for the guild's Config data, which is stored in the database. It is used to store and retrieve data from the database."""
import json
import logging
import os

import discord
from discord import CategoryChannel, ForumChannel, StageChannel, TextChannel, Thread, VoiceChannel
from discord_py_utilities.messages import send_message
from discord_py_utilities.permissions import find_first_accessible_text_channel

from classes.kernel.Queue import Singleton
from database.transactions.ConfigTransactions import ConfigTransactions
from database.transactions.ServerTransactions import ServerTransactions
from project.data import BOT_NAME
from resources.configs.ConfigMapping import ConfigMapping, defaults, legacy_json_keys, lists


class ConfigData(metaclass=Singleton) :
	"""This class generates the Config file, with functions to change and get values from it"""

	configcontroller = ConfigTransactions()
	data = {}

	# ============================================================
	def migrate(self, directory: str = "jsons") -> int :
		"""Imports the legacy jsons/<guild_id>.json configs into the database.

		Each imported file is renamed to <guild_id>.json.imported so it is never imported twice and can still be
		inspected. Returns the number of guilds imported.
		"""
		if not os.path.isdir(directory) :
			return 0
		imported = 0
		for file in os.listdir(directory) :
			serverid = file[:-5]
			if not file.endswith(".json") or not serverid.isnumeric() :
				continue
			try :
				serverid = int(serverid)
				with open(os.path.join(directory, file), "r") as f :
					config = json.load(f)
				if not ServerTransactions().exists(serverid) :
					ServerTransactions().add(serverid, "None", config.get("Name") or "None", 0, "", active=False)
				logging.info(f"Migrating config for {serverid}")
				for key, value in config.items() :
					mapped = legacy_json_keys.get(key)
					if mapped is None or value in (None, "") :
						continue
					if mapped in lists :
						for item in value :
							self.configcontroller.config_key_add(serverid, mapped, item)
						continue
					self.configcontroller.config_unique_add(serverid, mapped, value, overwrite=True)
				os.replace(os.path.join(directory, file), os.path.join(directory, f"{file}.imported"))
				self.load_guild(serverid)
				imported += 1
			except Exception as e :
				logging.error(f"Failed to migrate config file {file}: {e}", exc_info=True)
		return imported

	# ============================================================
	def reload(self) :
		"""Reloads the Config data from the database"""
		self.data = {}
		for guild in ServerTransactions().get_all() :
			try :
				self.load_guild(guild)
			except Exception as e :
				logging.error(e, exc_info=True)

	# ============================================================
	def load(self, guilds) :
		self.data = {}
		for guild in guilds :
			self.load_guild(guild.id)

	# ============================================================
	def load_guild(self, serverid) :
		"""Loads the Config for a guild; multi-value keys become lists."""
		config = self.configcontroller.server_config_get(serverid)
		guild_data = {key.upper() : [] for key in lists}

		for item in config :
			key = item.key.upper()
			if key in lists :
				guild_data[key].append(item.value)
				continue
			guild_data[key] = item.value
		self.data[str(serverid)] = guild_data

	# ============================================================
	def add_key(self, serverid, key, value: str | bool | int, overwrite=False) :
		"""Adds a key to the Config"""

		self.configcontroller.config_unique_add(serverid, key, value, overwrite=overwrite)
		self.load_guild(serverid)

	# ============================================================
	def remove_key(self, serverid, key) :
		"""Removes a key from the Config"""
		self.configcontroller.config_unique_remove(serverid, key)
		self.load_guild(serverid)

	# ============================================================
	def update_key(self, serverid, key, value) :
		"""Updates a key in the Config"""
		self.configcontroller.config_update(serverid, key, value)
		self.load_guild(serverid)

	# == lists ==

	# ============================================================
	def get_list(self, serverid, key) -> list[int | str] :
		"""All values of a multi-value key; numeric values are returned as ints."""
		values = self.get_guild(serverid).get(key.upper(), [])
		if not isinstance(values, list) :
			values = [values]
		return [int(value) if str(value).isnumeric() else value for value in values]

	# ============================================================
	def add_to_list(self, serverid, key, value) -> bool :
		"""Returns False when the value was already in the list."""
		added = self.configcontroller.config_key_add(serverid, key, value)
		self.load_guild(serverid)
		return added

	# ============================================================
	def remove_from_list(self, serverid, key, value) -> bool :
		"""Returns False when the value was not in the list."""
		removed = self.configcontroller.config_key_remove(serverid, key, value) is not False
		self.load_guild(serverid)
		return removed

	# == single values ==

	# ============================================================
	def get_key(self, serverid, key, default=None) :
		"""Gets a key from the Config, falls back to the documented default and then to `default`."""
		guild = self.get_guild(serverid)
		value = guild.get(key.upper(), None)
		if default is None :
			default = defaults.get(key.upper())
		if not value :
			return default

		if isinstance(value, bool) :
			return value
		if value.isnumeric() and value not in ["0", "1"] :
			return int(value)
		if isinstance(value, str) :
			if value.lower() in ["true", "1", "enabled"] :
				return True
			if value.lower() in ["false", "0", "disabled"] :
				return False

			return value

		return default

	# ============================================================
	def get_int(self, serverid, key, default: int = None) -> int | None :
		"""Gets a numeric key as an int. Unlike get_key, "0" and "1" stay numbers instead of becoming booleans."""
		if default is None :
			default = defaults.get(key.upper())
		value = self.get_guild(serverid).get(key.upper(), None)
		try :
			return int(value)
		except (TypeError, ValueError) :
			return default

	# ============================================================
	def get_toggle(self, guildid: int, key: str, expected: str = "ENABLED", default: str = "DISABLED") -> bool :
		"""
		:param guildid:
		:param key:
		:param expected:
		:param default:
		:return:
		"""
		value = str(self.get_key(guildid, key, default)).upper()

		# Due the database field being a string, it allows for multiple ways to represent enabled/disabled. In legacy we used ENABLED/DISABLED but we're slowly moving to TRUE/FALSE; to ensure backwards compatibility we check for all options we check for all options here.
		if value in ["ENABLED", "TRUE", "1", "ON"] :
			return expected.upper() == "ENABLED"
		if value in ["DISABLED", "FALSE", "0", "OFF"] :
			return expected.upper() == "DISABLED"
		return value == expected.upper()

	# ============================================================
	def get_key_or_none(self, serverid, key) :
		"""Gets a key from the Config, returns None if not found"""
		return self.get_key(serverid, key)

	# ============================================================
	async def get_channel(self, guild: discord.Guild, channel_type: str = ConfigMapping.MODLOG,
	                      optional=False) -> None | VoiceChannel | StageChannel | ForumChannel | TextChannel | CategoryChannel | Thread :
		"""Gets the channel from the Config. Unless optional, tells the server when it is not set or not reachable."""
		channel_id = self.get_int(guild.id, channel_type)

		if channel_id is None :
			if optional :
				return None
			channel = find_first_accessible_text_channel(guild)
			if channel is None :
				channel = guild.owner
			await send_message(channel,
			                   f"No `{channel_type}` channel set for {guild.name}, please set it up using the /config command",
			                   error_mode='ignore')
			return None
		channel = guild.get_channel_or_thread(channel_id)
		attempts = 0
		while channel is None and attempts < 3 :
			attempts += 1
			try :
				channel = await guild.fetch_channel(channel_id)
			except discord.NotFound :
				break
			except discord.HTTPException :
				continue
		if channel is None :
			if optional :
				return None
			channel = find_first_accessible_text_channel(guild)
			if channel is None :
				channel = guild.owner

			await send_message(channel,
			                   f"{BOT_NAME} could not fetch the `{channel_type}` channel with id {channel_id} in {guild.name}, please verify it exists and is accessible by the bot. If it does then discord may be having issues.",
			                   error_mode='ignore')
			return None
		return channel

	# ============================================================
	def get_guild(self, guild_id: int) -> dict[str, str | bool | int | list] :
		if str(guild_id) not in self.data :
			self.load_guild(guild_id)
		return self.data.get(str(guild_id), {})
