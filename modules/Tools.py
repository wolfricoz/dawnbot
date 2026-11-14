import asyncio
import logging
import random

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.kernel.ConfigData import ConfigData
from resources.configs.ConfigMapping import ConfigMapping


class Tools(commands.Cog) :
	"""Roleplay tools: dice, coin flips and scene endings."""

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
	@app_commands.command(name="dice", description="rolls a dice for you!")
	@app_commands.choices(modifier=[Choice(name=str(x), value=x) for x in range(-10, 11)])
	async def dice(self, interaction: discord.Interaction, dicetype: int, modifier: Choice[int] = 0,
	               title: str = "No goal given.", amount: int = 1) :
		"""
		Rolls one or more dice with an optional modifier. Dice of 100 sides or more triple the modifier.
		"""
		logging.debug(f"{interaction.user.name} rolled dicetype: {dicetype}, modifier: {modifier}, title: {title}, amount: {amount}")
		if isinstance(modifier, Choice) :
			modifier = modifier.value
		await interaction.response.defer(thinking=False, ephemeral=True)
		if dicetype < 2 :
			return await interaction.followup.send("Please choose a dice with at least 2 sides!")
		if dicetype > 1000 :
			return await interaction.followup.send("Please choose a dice with less than 1000 sides!")
		if amount > 50 :
			return await interaction.followup.send("you can roll up to 50 dice!")
		results = []
		text_results = []
		if dicetype >= 100 :
			modifier *= 3
		for _ in range(amount) :
			result = random.randint(1, dicetype)
			results.append(result + modifier)
			text_results.append(f"{result + modifier} ({result}+{modifier})")

		await interaction.followup.send("The dice has been cast..")
		embed = discord.Embed(title=title,
		                      description=f"You roll {amount}d{dicetype}{'+' if modifier >= 0 else ''}{modifier}: {', '.join(text_results)} \n(total: {sum(results)})")
		embed.set_footer(text=f"{interaction.user.name}")

		await interaction.channel.send(f"{interaction.user.mention}", embed=embed)

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


async def setup(bot) :
	await bot.add_cog(Tools(bot))
