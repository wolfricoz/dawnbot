import logging

import discord
from discord import app_commands
from discord.ext import commands

from classes.combat.AutoComplete import AutoComplete
from classes.combat.CombatCache import CombatCache


class Armor(commands.GroupCog, name="Armor", group_name="armor") :
	"""Armor sets that characters wear in combat."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@app_commands.command(name="create", description="creates an armor set")
	@app_commands.checks.has_permissions(manage_guild=True)
	async def create(self, interaction: discord.Interaction, name: str, hp: int, ac: int, hitchance: int = 0,
	                 modifier: str = "None") -> None :
		"""
		Creates an armor set.

		**Permissions:**
		- `Manage Server`
		"""
		if CombatCache().create_armor(name, hp, ac, hitchance, modifier) is None :
			await interaction.response.send_message(f"Armor set {name} already exists")
			return
		logging.info(f"Armor set {name} created by {interaction.user.name}")
		await interaction.response.send_message(f"Armor set {name} created")

	# ============================================================
	@app_commands.command(name="delete", description="deletes an armor set")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.autocomplete(name=AutoComplete().armor)
	async def delete(self, interaction: discord.Interaction, name: str) -> None :
		"""
		Deletes an armor set.

		**Permissions:**
		- `Manage Server`
		"""
		if CombatCache().get_armor(name) is None :
			await interaction.response.send_message(f"Armor set {name} does not exist")
			return
		if not CombatCache().remove_armor(name) :
			await interaction.response.send_message(f"Armor set {name} could not be deleted; characters may still be wearing it")
			return
		logging.info(f"Armor set {name} deleted by {interaction.user.name}")
		await interaction.response.send_message(f"Armor set {name} deleted")

	# ============================================================
	@app_commands.command(name="list", description="lists all armor sets")
	async def list(self, interaction: discord.Interaction) -> None :
		"""
		Lists all armor sets.
		"""
		embed = discord.Embed(title="Armor sets")
		for name, armor in list(CombatCache().armor.items())[:25] :
			embed.add_field(name=name, value=f"HP: {armor['hp']}\n"
			                                 f"AC: {armor['ac']}\n"
			                                 f"Hit chance: {armor['hitchance']}\n"
			                                 f"Modifier: {armor['modifier']}")
		await interaction.response.send_message(embed=embed)

	# ============================================================
	@app_commands.command(name="edit", description="edits an armor set")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.autocomplete(name=AutoComplete().armor)
	async def edit(self, interaction: discord.Interaction, name: str, hp: int = None, ac: int = None,
	               hitchance: int = None, modifier: str = None) -> None :
		"""
		Edits an armor set; options you leave out keep their value.

		**Permissions:**
		- `Manage Server`
		"""
		if CombatCache().update_armor(name, hp=hp, ac=ac, hitchance=hitchance, modifier=modifier) is None :
			await interaction.response.send_message(f"Armor set {name} does not exist")
			return
		logging.info(f"Armor set {name} edited by {interaction.user.name}")
		await interaction.response.send_message(f"Armor set {name} edited")


async def setup(bot) :
	await bot.add_cog(Armor(bot))
