"""Checks every slash command against Discord's limits.

Discord refuses the whole command sync when one command breaks a limit, so no new or changed command reaches anyone
(bot.tree.sync() in main.py logs a CommandSyncFailure). /armory add and edit growing to 26 and 27 options did exactly
that, which is why this test loads every module and checks them all.
"""
import asyncio
import os
import unittest

import discord
from discord.ext import commands

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAX_OPTIONS = 25  # options of a command, subcommands of a group, choices of an option
MAX_DESCRIPTION = 100
MAX_TOP_LEVEL = 100
MAX_CHARACTERS = 8000  # names, descriptions and choice names and values of one command, together
SUBCOMMAND, GROUP = 1, 2


# ============================================================
def characters(data: dict) -> int :
	total = len(data.get("name", "")) + len(data.get("description", ""))
	for choice in data.get("choices", []) :
		total += len(choice["name"]) + len(str(choice["value"]))
	return total + sum(characters(option) for option in data.get("options", []))


# ============================================================
def problems(data: dict, path: str) -> list[str] :
	found = []
	if len(data.get("description", "")) > MAX_DESCRIPTION :
		found.append(f"/{path}: description of {len(data['description'])} characters")
	options = data.get("options", [])
	if len(options) > MAX_OPTIONS :
		found.append(f"/{path}: {len(options)} options")
	for option in options :
		if option["type"] in (SUBCOMMAND, GROUP) :
			found += problems(option, f"{path} {option['name']}")
			continue
		if len(option.get("description", "")) > MAX_DESCRIPTION :
			found.append(f"/{path} {option['name']}: description of {len(option['description'])} characters")
		if len(option.get("choices", [])) > MAX_OPTIONS :
			found.append(f"/{path} {option['name']}: {len(option['choices'])} choices")
	return found


class TestCommandLimits(unittest.TestCase) :

	@classmethod
	def setUpClass(cls) :
		from database.database import create_bot_database

		create_bot_database()  # some modules read the database when they load

		async def load() :
			bot = commands.Bot(command_prefix="?", intents=discord.Intents.default())
			for filename in sorted(os.listdir(os.path.join(ROOT, "modules"))) :
				if filename.endswith(".py") :
					await bot.load_extension(f"modules.{filename[:-3]}")
			return bot

		cls.bot = asyncio.run(load())
		cls.payload = [command.to_dict(cls.bot.tree) for command in cls.bot.tree._get_all_commands()]

	def test_commands_fit_discords_limits(self) :
		found = [problem for data in self.payload for problem in problems(data, data["name"])]
		self.assertEqual(found, [])

	def test_command_size(self) :
		too_big = {data["name"] : characters(data) for data in self.payload if characters(data) > MAX_CHARACTERS}
		self.assertEqual(too_big, {})

	def test_top_level_count(self) :
		chat_commands = [data for data in self.payload if data.get("type", 1) == 1]
		self.assertLessEqual(len(chat_commands), MAX_TOP_LEVEL)
