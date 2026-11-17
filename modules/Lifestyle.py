"""Lifestyle: on servers that use it, each character pays every week for how it lives, from Destitute to Aristocratic,
with small perks and penalties.
"""
import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.combat.AutoComplete import AutoComplete
from classes.economy import Lifestyle as Rules
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from modules.Currency import balance_text
from views.combat.Pickers import reply

PERKS = {Rules.DESTITUTE : "−2 to haggling", Rules.POOR : "−1 to haggling", Rules.MODEST : "no perks or penalties",
         Rules.COMFORTABLE : "Worn gear looked after for free",
         Rules.WEALTHY : "Worn gear looked after, +2 to haggling and rumors",
         Rules.ARISTOCRATIC : "Worn gear looked after, +2 to haggling and rumors"}


@app_commands.guild_only()
class Lifestyle(commands.GroupCog, name="Lifestyle", group_name="lifestyle") :
	"""Choose how your character lives, paid every week."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	def _tiers(self, guild_id: int) -> list[Choice[str]] :
		return [Choice(name=f"{tier.capitalize()} · {Rules.WEEKLY[tier]} a week · {PERKS[tier]}"[:100], value=tier)
		        for tier in Rules.TIERS]

	# ============================================================
	async def _tier_choices(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		return [choice for choice in self._tiers(interaction.guild_id) if current.lower() in choice.name.lower()]

	# ============================================================
	@app_commands.command(name="set", description="Chooses how your character lives")
	@app_commands.autocomplete(character=AutoComplete().approved_character, lifestyle=_tier_choices)
	async def set_lifestyle(self, interaction: discord.Interaction, character: str, lifestyle: str) :
		"""
		Chooses your character's lifestyle and pays its first week: Destitute 0 (−2 to haggling), Poor 70 (−1),
		Modest 250, Comfortable 700 (Worn gear looked after), Wealthy 1,750 and Aristocratic 5,000 (also +2 to
		haggling and to listening for rumors). After that it is paid every week; a character that can't pay drops to
		the best lifestyle it can afford.
		"""
		record = CharacterTransactions().get(interaction.user.id, interaction.guild_id, character)
		if record is None or record.state != APPROVED :
			return await reply(interaction, "Pick one of your approved characters.")
		updated, problem = Rules.choose(record, lifestyle.strip().lower(), interaction.user.id)
		if problem :
			return await reply(interaction, problem)
		await reply(interaction, f"{record.name} now lives **{updated.lifestyle.capitalize()}** "
		                         f"({balance_text(interaction.guild_id, Rules.WEEKLY[updated.lifestyle])} a week), paid "
		                         f"until {discord.utils.format_dt(updated.lifestyle_paid_until, 'f')}.")

	# ============================================================
	@app_commands.command(name="view", description="Shows how your character lives")
	@app_commands.autocomplete(character=AutoComplete().character)
	async def view(self, interaction: discord.Interaction, character: str) :
		"""
		Shows your character's lifestyle, what it costs each week, its perks, and until when it is paid.
		"""
		record = CharacterTransactions().get(interaction.user.id, interaction.guild_id, character)
		if record is None :
			return await reply(interaction, f"You have no character called {character}.")
		tier = Rules.of(record)
		if tier is None :
			return await reply(interaction, "This server doesn't use lifestyles.")
		paid = f", paid until {discord.utils.format_dt(record.lifestyle_paid_until, 'f')}" \
			if record.lifestyle_paid_until else ""
		await reply(interaction, f"{record.name} lives **{tier.capitalize()}**: "
		                         f"{balance_text(interaction.guild_id, Rules.WEEKLY[tier])} a week, {PERKS[tier]}{paid}.")


async def setup(bot) :
	await bot.add_cog(Lifestyle(bot))
