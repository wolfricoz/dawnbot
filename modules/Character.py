import logging

import discord
from discord import app_commands
from discord.ext import commands

from classes.combat.AutoComplete import AutoComplete
from classes.combat.CombatCache import CombatCache

# Points every character can divide over its stats, before extra points.
BASE_POINTS = 12


class Character(commands.GroupCog, name="Character", group_name="character") :
	"""Create and manage your combat characters."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@staticmethod
	def character_embed(name: str, character: dict) -> discord.Embed :
		armor = CombatCache().get_armor_by_id(character["armor"])
		embed = discord.Embed(title=name)
		embed.add_field(name="Armor", value=armor["name"] if armor else "None")
		embed.add_field(name="Strength", value=character["strength"])
		embed.add_field(name="Perception", value=character["perception"])
		embed.add_field(name="Endurance", value=character["endurance"])
		embed.add_field(name="Charisma", value=character["charisma"])
		embed.add_field(name="Intelligence", value=character["intelligence"])
		embed.add_field(name="Agility", value=character["agility"])
		embed.add_field(name="extra_points", value=character["prestige"])
		return embed

	# ============================================================
	@app_commands.command(name="create", description="creates a character")
	@app_commands.autocomplete(armor=AutoComplete().armor)
	async def create(self, interaction: discord.Interaction,
	                 name: str,
	                 armor: str,
	                 strength: int,
	                 perception: int,
	                 endurance: int,
	                 charisma: int,
	                 intelligence: int,
	                 agility: int,
	                 extra_points: int = 0) :
		"""
		Creates a character. You can divide 12 points (plus any extra points) over the stats.
		"""
		await interaction.response.defer(ephemeral=True)
		allocated_points = strength + perception + endurance + charisma + intelligence + agility
		max_points = BASE_POINTS + extra_points
		if allocated_points > max_points :
			await interaction.followup.send(
				f"You have too many points allocated, you are allowed a maximum of {max_points} points but you allocated {allocated_points}!")
			return
		if CombatCache().get_armor(armor) is None :
			await interaction.followup.send(f"Armor set {armor} does not exist")
			return
		character = CombatCache().create_character(interaction.user.id, interaction.guild_id, name, armor,
		                                           strength=strength, perception=perception, endurance=endurance,
		                                           charisma=charisma, intelligence=intelligence, agility=agility,
		                                           prestige=extra_points)
		if character is None :
			await interaction.followup.send(f"You already have a character named {name}")
			return
		logging.info(
			f"Character {name} created by {interaction.user.name} with stats: {armor}, {strength}, {perception}, {endurance}, {charisma}, {intelligence}, {agility}, {extra_points}")
		await interaction.followup.send(f"Character {name} created")

	# ============================================================
	@app_commands.command(name="delete", description="deletes a character")
	@app_commands.autocomplete(name=AutoComplete().character)
	async def delete(self, interaction: discord.Interaction, name: str) :
		"""
		Deletes one of your characters.
		"""
		await interaction.response.defer(ephemeral=True)
		if not CombatCache().remove_character(interaction.user.id, name) :
			await interaction.followup.send(f"Character {name} does not exist")
			return
		logging.info(f"Character {name} deleted by {interaction.user.name}")
		await interaction.followup.send(f"Character {name} deleted")

	# ============================================================
	@app_commands.command(name="list", description="lists all characters")
	async def list(self, interaction: discord.Interaction) :
		"""
		Lists your characters and their stats.
		"""
		await interaction.response.defer()
		embed = discord.Embed(title="Characters")
		for name, character in list(CombatCache().get_user_characters(interaction.user.id).items())[:25] :
			armor = CombatCache().get_armor_by_id(character["armor"])
			embed.add_field(name=name, value=f"Armor: {armor['name'] if armor else 'None'}\n"
			                                 f"Strength: {character['strength']}\n"
			                                 f"Perception: {character['perception']}\n"
			                                 f"Endurance: {character['endurance']}\n"
			                                 f"Charisma: {character['charisma']}\n"
			                                 f"Intelligence: {character['intelligence']}\n"
			                                 f"Agility: {character['agility']}\n"
			                                 f"extra_points: {character['prestige']}")
		await interaction.followup.send(embed=embed)

	# ============================================================
	@app_commands.command(name="edit", description="edits a character")
	@app_commands.autocomplete(name=AutoComplete().character, armor=AutoComplete().armor)
	async def edit(self, interaction: discord.Interaction,
	               name: str,
	               armor: str = None,
	               strength: int = None,
	               perception: int = None,
	               endurance: int = None,
	               charisma: int = None,
	               intelligence: int = None,
	               agility: int = None,
	               extra_points: int = None) :
		"""
		Edits one of your characters; options you leave out keep their value.
		"""
		await interaction.response.defer(ephemeral=True)
		if CombatCache().get_character(interaction.user.id, name) is None :
			await interaction.followup.send(f"Character {name} does not exist")
			return
		if armor is not None and CombatCache().get_armor(armor) is None :
			await interaction.followup.send(f"Armor set {armor} does not exist")
			return
		CombatCache().update_character(interaction.user.id, name, armor, strength=strength, perception=perception,
		                               endurance=endurance, charisma=charisma, intelligence=intelligence,
		                               agility=agility, prestige=extra_points)
		logging.info(f"Character {name} edited by {interaction.user.name}")
		await interaction.followup.send(f"Character {name} edited")

	# ============================================================
	@app_commands.command(name="profile", description="shows the profile of a character")
	@app_commands.autocomplete(name=AutoComplete().character)
	async def profile(self, interaction: discord.Interaction, name: str) :
		"""
		Shows one of your characters.
		"""
		character = CombatCache().get_character(interaction.user.id, name)
		if character is None :
			await interaction.response.send_message(f"Character {name} does not exist")
			return
		await interaction.response.send_message(embed=self.character_embed(name, character))

	# ============================================================
	@app_commands.command(name="show", description="look at another person's character")
	async def show(self, interaction: discord.Interaction, member: discord.Member, name: str) :
		"""
		Shows another member's character.
		"""
		character = CombatCache().get_character(member.id, name)
		if character is None :
			await interaction.response.send_message(f"Character {name} does not exist")
			return
		await interaction.response.send_message(embed=self.character_embed(name, character))


async def setup(bot) :
	await bot.add_cog(Character(bot))
