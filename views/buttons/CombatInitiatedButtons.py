import logging

import discord
from discord_py_utilities.messages import send_message, send_response

from components.databaseEvents import CombatSystem
from database.transactions.CharacterTransactions import CharacterTransactions
from views.multiselect.characterselect import SelectCharacterView


class CombatInitiatedButtons(discord.ui.View) :
	def __init__(self) :
		super().__init__(timeout=None)
		pass

	@discord.ui.button(label="Join Instance", style=discord.ButtonStyle.green, custom_id="add_character")
	async def allow(self, interaction: discord.Interaction, button: discord.ui.Button) :
		"""This is a button"""
		characters = CharacterTransactions().get_all(interaction.user.id, interaction.guild_id)
		if not characters or len(characters) < 1 :
			return await send_response(interaction, f"{interaction.user.name} has no characters added.", ephemeral=True)

		select = SelectCharacterView(characters)
		await send_response(interaction, "Select a character!", view=select, ephemeral=True)
		await select.wait()
		logging.info(f"Selected character: {characters.id}")

		pass

	async def disable_buttons(self, interaction: discord.Interaction) :
		for item in self.children :
			item.disabled = True
		try :
			await interaction.message.edit(view=self)
		except Exception :
			pass

	async def load_data(self, interaction: discord.Interaction) :
		"""Load data from embed"""
		if len(interaction.message.embeds) < 1 :
			return False
		return True
