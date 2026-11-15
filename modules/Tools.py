import asyncio
import logging
import random

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands
from translate import Translator

from classes.characters.ImageStorage import ImageStorage
from classes.characters.Special import STATS, Special
from classes.combat.AutoComplete import AutoComplete
from classes.dice.Dice import Dice, MAX_AMOUNT, MAX_SIDES, MIN_SIDES, Modifier
from classes.dice.DiceCard import DiceCard
from classes.kernel.ConfigData import ConfigData
from data.languages import LANGUAGES
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from resources.configs.ConfigMapping import ConfigMapping


class Tools(commands.Cog) :
	"""Roleplay tools: dice, coin flips, scene endings and translation."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@app_commands.command(name="endscene", description="ends the scene")
	async def endscene(self, interaction: discord.Interaction, rpenddate: str, title: str = None) :
		"""
		Ends the scene in this channel and posts a summary entry in the timeline channel.
		"""
		await interaction.response.defer(thinking=False, ephemeral=True)
		channel = await ConfigData().get_channel(interaction.guild, ConfigMapping.TIMELINE, optional=True)
		if channel is None :
			return await interaction.followup.send("No timeline channel is set up; staff can set one with /config singlechannels.")
		message: discord.Message = await interaction.channel.send(f"{interaction.user.mention} ended the scene.")
		await channel.send(f"{f'# {title}' if title is not None else ''}\n"
		                   f"Author: {interaction.user.mention}\n"
		                   f"Link to final message: {message.jump_url}\n"
		                   f"In roleplay date: {rpenddate}\n"
		                   f"Brief summary of what happened: (Post below!)")

	# ============================================================
	@app_commands.command(name="dice", description="rolls dice for you, optionally as one of your characters")
	@app_commands.autocomplete(character=AutoComplete().approved_character)
	@app_commands.choices(stat=[Choice(name=stat.capitalize(), value=stat) for stat in STATS])
	@app_commands.describe(dicetype="How many sides each die has, e.g. 20 for a d20",
	                       modifier="A bonus or penalty on top of the stat, added once to the total",
	                       title="What you are trying to do; shown as the title",
	                       amount="How many dice to roll",
	                       character="Roll as one of your approved characters",
	                       stat="The character's SPECIAL stat that adds its modifier")
	async def dice(self, interaction: discord.Interaction, dicetype: app_commands.Range[int, MIN_SIDES, MAX_SIDES],
	               modifier: app_commands.Range[int, -50, 50] = 0, title: app_commands.Range[str, 1, 200] = None,
	               amount: app_commands.Range[int, 1, MAX_AMOUNT] = 1, character: str = None,
	               stat: Choice[str] = None) :
		"""
		Rolls one or more dice and posts the result with a line of story text that depends on how the roll went.

		Pick one of your approved characters to roll as them, and a SPECIAL stat to add its modifier: the stat minus the
		server's starting stat value (5 by default), so 5 adds nothing, 10 adds +5 and 1 adds -4. The modifier option
		comes on top. Modifiers are added once to the total, and dice of 100 sides or more triple them. Rolling every die
		on its highest side is a critical success; every die on 1 is a critical failure.
		"""
		stat = stat.value if isinstance(stat, Choice) else stat
		logging.debug(f"{interaction.user.name} rolled {amount}d{dicetype} modifier {modifier} character {character} "
		              f"stat {stat}: {title}")
		if (problem := Dice.check(dicetype, amount)) is not None :
			return await interaction.response.send_message(problem, ephemeral=True)
		if stat and not character :
			return await interaction.response.send_message("Pick a character to roll with a stat.", ephemeral=True)

		record = None
		modifiers = []
		if character :
			record = CharacterTransactions().get(interaction.user.id, interaction.guild_id, character)
			if record is None :
				return await interaction.response.send_message(f"You have no character called {character}.",
				                                               ephemeral=True)
			if record.state != APPROVED :
				return await interaction.response.send_message(f"{record.name} has not been approved by staff yet.",
				                                               ephemeral=True)
			if stat :
				value = getattr(record, stat)
				base = Special.rules(interaction.guild_id).base
				modifiers.append(Modifier(f"{stat.capitalize()} {value}", Dice.stat_modifier(value, base)))
		modifiers.append(Modifier("Bonus", modifier))

		# Fetching a stored avatar can take a moment.
		await interaction.response.defer(thinking=True)
		avatar = await ImageStorage.url(self.bot, record.avatar_id) if record else None
		roll = Dice.roll(dicetype, amount, modifiers)
		embed = DiceCard.embed(roll, roller=interaction.user.display_name, goal=title,
		                       character_name=record.name if record else None, stat=stat,
		                       icon_url=avatar or interaction.user.display_avatar.url, thumbnail_url=avatar)
		await interaction.followup.send(embed=embed)

	# ============================================================
	@app_commands.command(name="coinflip", description="flips a coin for you!")
	async def coin(self, interaction: discord.Interaction) :
		"""
		Flips a coin.
		"""
		await interaction.response.defer(thinking=False, ephemeral=True)
		await interaction.followup.send("The coin has been cast..")
		await interaction.channel.send("Heads!" if random.randint(1, 2) == 1 else "Tails!")

	# ============================================================
	@app_commands.command(name="purge", description="kicks every member with the given inactivity role")
	@app_commands.checks.has_permissions(manage_guild=True)
	async def purge(self, interaction: discord.Interaction, role: discord.Role) :
		"""
		Kicks every member who has the given (inactivity) role, after DMing them a one-time invite back.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer()
		message: discord.Message = await interaction.followup.send(f"Purging members with {role.name}.")
		count = 0
		for member in list(role.members) :
			invite = await interaction.channel.create_invite(max_age=86400, max_uses=1)
			await asyncio.sleep(1)
			try :
				await member.send("You have been purged from the server due to inactivity. If you wish to rejoin, please use the invite link."
				                  f"{invite.url}")
			except discord.Forbidden :
				await interaction.channel.send(f"Error: {member.mention} could not be dmed.")
			await member.kick(reason="purged due to inactivity")
			count += 1
		await message.edit(content=f"{count} members have been purged.")


	# ============================================================
	async def language_autocomplete(self, interaction: discord.Interaction, current: str) :
		return [Choice(name=name, value=code) for code, name in LANGUAGES.items()
		        if name.lower().startswith(current.lower())][:25]

	# ============================================================
	@app_commands.command(name="translate", description="translates a message to another language")
	@app_commands.autocomplete(from_language=language_autocomplete, target_language=language_autocomplete)
	async def translate(self, interaction: discord.Interaction, text: app_commands.Range[str, 1, 500],
	                    from_language: str = "en", target_language: str = "en") :
		"""
		Translates text between languages using the MyMemory translation service.
		"""
		await interaction.response.defer(ephemeral=True)
		translator = Translator(from_lang=from_language.lower(), to_lang=target_language.lower())
		# The translator makes a blocking web request.
		translation = await asyncio.to_thread(translator.translate, text)
		await interaction.followup.send(
			f"Translated from {LANGUAGES.get(from_language, from_language)} to "
			f"{LANGUAGES.get(target_language, target_language)} ```{translation}```", ephemeral=True)


async def setup(bot) :
	await bot.add_cog(Tools(bot))
