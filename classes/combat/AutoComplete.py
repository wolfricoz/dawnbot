import discord
from discord import app_commands

from classes.combat.CombatCache import CombatCache
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions


class AutoComplete :
	"""Autocomplete callbacks for the armor, weapon and character options (at most 25 choices)."""

	# ============================================================
	@staticmethod
	def _choices(names, current: str, lower: bool = True) -> list[app_commands.Choice[str]] :
		matches = [name.lower() if lower else name for name in names if current.lower() in name.lower()]
		return [app_commands.Choice(name=name[:100], value=name[:100]) for name in matches[:25]]

	# ============================================================
	async def weapon(self, interaction: discord.Interaction, current: str) :
		return self._choices(CombatCache().weapons.keys(), current)

	# ============================================================
	async def character(self, interaction: discord.Interaction, current: str) :
		"""The member's own characters on this server, whatever their review state."""
		characters = CharacterTransactions().get_all(interaction.user.id, interaction.guild_id)
		return self._choices([character.name for character in characters], current, lower=False)

	# ============================================================
	async def approved_character(self, interaction: discord.Interaction, current: str) :
		"""The member's approved characters on this server."""
		characters = CharacterTransactions().get_all(interaction.user.id, interaction.guild_id, states=[APPROVED])
		return self._choices([character.name for character in characters], current, lower=False)

	# ============================================================
	async def armor(self, interaction: discord.Interaction, current: str) :
		return self._choices(CombatCache().armor.keys(), current)
