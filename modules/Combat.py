import logging
import random
from math import ceil

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands
from discord_py_utilities.messages import send_response

from classes.combat.AutoComplete import AutoComplete
from classes.combat.CombatCache import CombatCache
from classes.combat.CombatController import CombatController
from classes.combat.CombatInstance import CombatInstance
from classes.combat.InstanceManager import InstanceManager
from classes.kernel.AccessControl import AccessControl
from views.buttons.CombatInitiatedButtons import CombatInitiatedButtons


class Combat(commands.GroupCog, name="Combat", group_name="combat") :
	"""Attack rolls and combat instances."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@app_commands.command(name="attack",
	                      description="attacks a target. Only fill in modifier if you have extra bonuses that aren't from stats.")
	@app_commands.autocomplete(character=AutoComplete().character,
	                           weapon=AutoComplete().weapon)
	@app_commands.choices(hitchance_modifier=[Choice(name=str(x), value=x) for x in range(-10, 11)],
	                      damage_modifier=[Choice(name=str(x), value=x) for x in range(-10, 11)],
	                      advantage=[Choice(name="yes", value="yes"), Choice(name="no", value="no")])
	async def attack(self, interaction: discord.Interaction, title: str, character: str, weapon: str, enemy_ac: int,
	                 hitchance_modifier: Choice[int] = 0, damage_modifier: Choice[int] = 0,
	                 advantage: Choice[str] = "no") :
		"""
		Rolls an attack with one of your characters and a weapon against the enemy's armor class.
		"""
		await interaction.response.defer()

		embed = discord.Embed(title=title)

		if isinstance(damage_modifier, Choice) :
			damage_modifier = damage_modifier.value
		if isinstance(advantage, Choice) :
			advantage = advantage.value
		if isinstance(hitchance_modifier, Choice) :
			hitchance_modifier = hitchance_modifier.value
		chosen_character = CombatCache().get_character(interaction.user.id, character)
		chosen_weapon = CombatCache().get_weapon(weapon)
		if chosen_character is None :
			return await interaction.followup.send(f"Character {character} does not exist")
		if chosen_weapon is None :
			return await interaction.followup.send(f"Weapon {weapon} does not exist")
		# hit dice
		final_hit, crit, hit_result, hit_mod = CombatController.calculate_hit(chosen_character, weapon, chosen_weapon,
		                                                                      hitchance_modifier, advantage, enemy_ac)

		if final_hit is False :
			embed.description = f"**{character}** missed the attack"
			embed.set_footer(text=f"Hit roll: {crit} ({hit_result} + {hit_mod}) vs {enemy_ac}")
			await interaction.followup.send(embed=embed)
			return
		# damage dice
		extra_dice = 0
		damage_mod = 0
		dice_number, dice_size = (int(part) for part in chosen_weapon['dice'].lower().split("d"))
		results = []
		modifier = (chosen_weapon['modifier'] or "").lower()
		if modifier.startswith("dice") :
			extra_dice += ceil(chosen_character[modifier.split(":")[1]] / 2)
		if modifier.startswith("damage") :
			damage_mod += chosen_character[modifier.split(":")[1]]
		damage_mod += damage_modifier
		dice_number += extra_dice
		while dice_number > 0 and crit is False :
			dice_number -= 1
			results.append(random.randint(1, dice_size))
		total_damage = sum(results) + damage_mod
		if crit :
			total_damage = (dice_size * dice_number) + (damage_mod * 2)
		embed.description = f"**{character}** hit the attack for **{total_damage}** damage with **{weapon}**!"
		debug = (f"Debug: Hit roll: {final_hit} ({hit_result} + {hit_mod}) vs {enemy_ac}, Damage roll: {results} + "
		         f"{damage_mod} = {total_damage} (crit: {crit}) (advantage: {advantage})")
		embed.set_footer(text=debug)
		logging.info(f"{character} hit the attack for {total_damage} damage with {weapon}!")
		logging.debug(debug)
		await interaction.followup.send(embed=embed)

	# ============================================================
	@app_commands.command(name="start", description="Creates a new instance, only one can be active per channel")
	async def start(self, interaction: discord.Interaction) :
		"""
		Starts a combat instance in this channel; only one can be active per channel.
		"""
		instance_manager = InstanceManager()
		existing = instance_manager.load(interaction.channel)

		# prevent a second instance on the same channel
		if existing :
			return await send_response(interaction,
			                           f"This channel already has an active instance! Active instance: {existing.get_instance_guid()}",
			                           ephemeral=True)

		instance = instance_manager.create(interaction.channel)
		if not isinstance(instance, CombatInstance) :
			return await send_response(interaction, "Failed to create instance.", ephemeral=True)
		embed = discord.Embed(
			title="New combat instance created!",
			description="You have successfully created a new instance! You can add your character by clicking the button below or do /combat join in this channel!"
		)
		embed.set_footer(text=f"Instance guid: {instance.get_instance_guid()}")

		await send_response(interaction, " ", embed=embed, view=CombatInitiatedButtons(), ephemeral=False)

	# ============================================================
	@app_commands.command(name="reload")
	@AccessControl().check_access("dev")
	async def forcereload(self, interaction: discord.Interaction) :
		"""
		Reloads armor, weapons and characters from the database.

		**Permissions:**
		- `Developer`
		"""
		await interaction.response.defer()
		CombatCache().load_all()
		await interaction.followup.send("Reloaded all data")


async def setup(bot) :
	await bot.add_cog(Combat(bot))
