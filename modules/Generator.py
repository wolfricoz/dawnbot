import json
import random

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

NAMES_FILE = "resources/data/names/{gender}names.json"


class Generator(commands.GroupCog, name="Generator", group_name="generator") :
	"""Generators for roleplay inspiration."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot
		self.names: dict[str, list[str]] = {}

	# ============================================================
	def load_names(self, gender: str) -> list[str] :
		if gender not in self.names :
			with open(NAMES_FILE.format(gender=gender), encoding="utf-8") as f :
				self.names[gender] = json.load(f)["names"]
		return self.names[gender]

	# ============================================================
	@app_commands.command(name="name", description="Generate up to 20 names for your character")
	@app_commands.choices(gender=[
		Choice(name="Male", value="m"),
		Choice(name="Female", value="f"),
	])
	async def name(self, interaction: discord.Interaction, gender: Choice[str],
	               amount: app_commands.Range[int, 1, 20] = 10) :
		"""
		Generates up to 20 random first names.
		"""
		names = random.sample(self.load_names(gender.value), amount)
		embed = discord.Embed(title=f"{amount} {gender.name} names generated:", description="\n".join(names))
		await interaction.response.send_message(embed=embed)


async def setup(bot) :
	await bot.add_cog(Generator(bot))
