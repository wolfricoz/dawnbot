import discord
from discord import app_commands

from classes.combat.CombatCache import CombatCache


class AutoComplete :
	"""Autocomplete callbacks for the armor, weapon and character options. Discord shows at most 25 choices."""

	# ============================================================
	@staticmethod
	def _choices(names, current: str) -> list[app_commands.Choice[str]] :
		matches = [name.lower() for name in names if current.lower() in name.lower()]
		return [app_commands.Choice(name=name, value=name) for name in matches[:25]]

	# ============================================================
	async def weapon(self, interaction: discord.Interaction, current: str) :
		return self._choices(CombatCache().weapons.keys(), current)

	# ============================================================
	async def character(self, interaction: discord.Interaction, current: str) :
		return self._choices(CombatCache().characters.get(interaction.user.id, {}).keys(), current)

	# ============================================================
	async def armor(self, interaction: discord.Interaction, current: str) :
		return self._choices(CombatCache().armor.keys(), current)
