import logging

import discord
from discord import app_commands
from discord.ext import commands

from classes.combat.AutoComplete import AutoComplete
from classes.combat.CombatCache import CombatCache


class Weapon(commands.GroupCog, name="Weapon", group_name="weapon") :
	"""Weapon types used for attack rolls."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@app_commands.command(name="create", description="creates a weapon type")
	@app_commands.checks.has_permissions(manage_guild=True)
	async def create(self, interaction: discord.Interaction, name: str, dice: str, modifier: str,
	                 hitmodifier: int = 0) :
		"""
		Creates a weapon type. Dice look like 2d6; the modifier is dice:<stat>, damage:<stat> or none.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		if CombatCache().create_weapon(name, dice, modifier, hitmodifier) is None :
			await interaction.followup.send(f"Weapon {name} already exists")
			return
		logging.info(f"Weapon {name} created by {interaction.user.name}")
		await interaction.followup.send(f"Weapon {name} created")

	# ============================================================
	@app_commands.command(name="delete", description="deletes a weapon type")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.autocomplete(name=AutoComplete().weapon)
	async def delete(self, interaction: discord.Interaction, name: str) :
		"""
		Deletes a weapon type.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		if CombatCache().get_weapon(name) is None :
			await interaction.followup.send(f"Weapon {name} does not exist")
			return
		if not CombatCache().remove_weapon(name) :
			await interaction.followup.send(f"Weapon {name} could not be deleted")
			return
		logging.info(f"Weapon {name} deleted by {interaction.user.name}")
		await interaction.followup.send(f"Weapon {name} deleted")

	# ============================================================
	@app_commands.command(name="list", description="lists all weapon types")
	async def list(self, interaction: discord.Interaction) :
		"""
		Lists all weapon types.
		"""
		await interaction.response.defer()
		embed = discord.Embed(title="Weapon types")
		for name, weapon in list(CombatCache().weapons.items())[:25] :
			embed.add_field(name=name,
			                value=f"Damage: {weapon['dice']} + {weapon['modifier']} \n Hit modifier: {weapon['hitmodifier']}")
		await interaction.followup.send(embed=embed)

	# ============================================================
	@app_commands.command(name="edit", description="edits a weapon type")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.autocomplete(name=AutoComplete().weapon)
	async def edit(self, interaction: discord.Interaction, name: str, dice: str = None, modifier: str = None,
	               hitmodifier: int = None) :
		"""
		Edits a weapon type; options you leave out keep their value.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		if CombatCache().update_weapon(name, dice=dice, modifier=modifier, hitmodifier=hitmodifier) is None :
			await interaction.followup.send(f"Weapon {name} does not exist")
			return
		logging.info(f"Weapon {name} updated by {interaction.user.name}")
		await interaction.followup.send(f"Weapon {name} updated")


async def setup(bot) :
	await bot.add_cog(Weapon(bot))
