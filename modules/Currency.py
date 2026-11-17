"""Characters' currency: balances and the history of every change.

Currency belongs to characters, not members. A character starts with the server's starting amount and earns more by
roleplaying as that character; GMs can give or take it with /gm currency.
"""
import discord
from discord import app_commands
from discord.ext import commands

from classes.characters.CharacterFlow import CharacterFlow
from classes.combat.AutoComplete import AutoComplete
from classes.gear.Gear import Gear
from classes.kernel.ConfigData import ConfigData
from database.database import Characters
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.CurrencyTransactions import BUY, CurrencyTransactions, GM_GIVE, GM_TAKE, ROLEPLAY, SELL, \
	START
from resources.configs.ConfigMapping import ConfigMapping

HISTORY_LENGTH = 15
# Ledger reasons from the economy round, shown with their note (who the other side was, which item).
NOTED_REASONS = {"trade_in" : "trade", "trade_out" : "trade", "pay" : "payment", "market" : "market",
                 "market_fee" : "market fee", "repair" : "repair", "refill" : "ammunition", "lodging" : "room",
                 "training" : "training", "healing" : "healer", "lifestyle" : "lifestyle", "loot" : "loot",
                 "service" : "service"}
FREE_NOTE = "Gear is free on this server right now, so currency isn't spent."


# ============================================================
def currency_name(guild_id: int) -> str :
	return str(ConfigData().get_key(guild_id, ConfigMapping.CURRENCY_NAME))


# ============================================================
def balance_text(guild_id: int, amount: int) -> str :
	"""`1400 caps`, using the server's currency name."""
	return f"{amount} {currency_name(guild_id)}"


# ============================================================
def ledger_line(row, name: str) -> str :
	"""One ledger row as text, like `+13 caps · roleplay · 2 hours ago`."""
	reasons = {
		START    : "starting amount",
		ROLEPLAY : "roleplay",
		BUY      : f"bought {row.note}" if row.note else "bought gear",
		SELL     : f"sold {row.note}" if row.note else "sold gear",
		GM_GIVE  : f"given by <@{row.actor_uid}>" if row.actor_uid else "given by staff",
		GM_TAKE  : f"taken by <@{row.actor_uid}>" if row.actor_uid else "taken by staff",
	}
	reason = reasons.get(row.reason, row.reason)
	if row.reason in (GM_GIVE, GM_TAKE) and row.note :
		reason += f": {row.note}"
	elif row.reason in NOTED_REASONS :
		reason = NOTED_REASONS[row.reason] + (f": {row.note}" if row.note else "")
	parts = [f"`{row.amount:+}` {name}", reason]
	if row.created_at is not None :
		parts.append(discord.utils.format_dt(row.created_at, "R"))
	return " · ".join(parts)


# ============================================================
async def find_own_character(interaction: discord.Interaction, name: str,
                             approved: bool = False) -> Characters | None :
	"""The member's character with that name on this server; tells them when there is none (or it is not approved)."""
	character = CharacterTransactions().get(interaction.user.id, interaction.guild_id, name)
	if character is None :
		await CharacterFlow.respond(interaction, f"You have no character called {name} on this server.")
		return None
	if approved and character.state != APPROVED :
		await CharacterFlow.respond(interaction, f"{character.name} needs to be approved by staff first.")
		return None
	return character


@app_commands.guild_only()
class Currency(commands.GroupCog, name="currency", group_name="currency", description="Shows how much currency you have.") :


	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@app_commands.command(name="balance")
	@app_commands.autocomplete(character=AutoComplete().character)
	async def balance(self, interaction: discord.Interaction, character: str = None) :
		"""
		Shows how much currency your characters have. Leave out `character` to see all of them.
		"""
		if character is not None :
			if (record := await find_own_character(interaction, character)) is None :
				return
			characters = [record]
		else :
			characters = CharacterTransactions().get_all(interaction.user.id, interaction.guild_id)
			if not characters :
				return await CharacterFlow.respond(interaction, "You have no characters on this server.")
		guild_id = interaction.guild_id
		lines = [f"**{record.name}**: {balance_text(guild_id, record.currency)}" for record in characters]
		embed = discord.Embed(title=currency_name(guild_id).capitalize(), description="\n".join(lines)[:4000],
		                      color=discord.Color.dark_gold())
		if not Gear.economy(guild_id) :
			embed.set_footer(text=FREE_NOTE)
		await interaction.response.send_message(embed=embed, ephemeral=True)

	# ============================================================
	async def _theirs(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]] :
		member = interaction.namespace.member
		if member is None :
			return []
		return [app_commands.Choice(name=character.name, value=character.name)
		        for character in CharacterTransactions().get_all(member.id, interaction.guild_id, states=[APPROVED])
		        if current.lower() in character.name.lower()][:25]

	# ============================================================
	@app_commands.command(name="pay")
	@app_commands.autocomplete(character=AutoComplete().approved_character, theirs=_theirs)
	@app_commands.describe(character="Your character, who pays", member="The other player",
	                       theirs="The other player's character", note="What it is for (shown in both histories)")
	async def pay(self, interaction: discord.Interaction, character: str, member: discord.Member, theirs: str,
	              amount: app_commands.Range[int, 1, 1000000000], note: app_commands.Range[str, 1, 100] = None) :
		"""
		Pays currency from one of your characters to another player's character, after you confirm. Your own
		characters can't pay each other. The payment shows in both characters' currency history.
		"""
		from classes.economy import Trading
		from views.buttons.Confirm import ask

		payer = CharacterTransactions().get(interaction.user.id, interaction.guild_id, character)
		payee = CharacterTransactions().get(member.id, interaction.guild_id, theirs)
		problem = Trading.pair_problem(payer, payee)
		if problem :
			return await CharacterFlow.respond(interaction, problem)
		guild_id = interaction.guild_id
		if not await ask(interaction, f"Pay {balance_text(guild_id, amount)} from {payer.name} to {payee.name}?",
		                 "Pay") :
			return
		problem = Trading.pay(payer, payee, amount, interaction.user.id, note)
		if problem :
			return await interaction.followup.send(problem, ephemeral=True)
		balance = CharacterTransactions().get_by_id(payer.id).currency
		await interaction.followup.send(f"{payer.name} paid {balance_text(guild_id, amount)} to {payee.name} and has "
		                                f"{balance_text(guild_id, balance)} left.", ephemeral=True)
		try :
			await member.send(f"💰 {payer.name} paid {balance_text(guild_id, amount)} to your character {payee.name} on "
			                  f"{interaction.guild.name}." + (f" Note: {note}" if note else ""))
		except discord.HTTPException :
			pass

	# ============================================================
	@app_commands.command(name="history")
	@app_commands.autocomplete(character=AutoComplete().character)
	async def history(self, interaction: discord.Interaction, character: str) :
		"""
		Shows the last changes to one of your characters' currency: roleplay earnings, purchases, sales and what
		staff gave or took.
		"""
		if (record := await find_own_character(interaction, character)) is None :
			return
		guild_id = interaction.guild_id
		name = currency_name(guild_id)
		rows = CurrencyTransactions().get_all(record.id, limit=HISTORY_LENGTH)
		lines = [ledger_line(row, name) for row in rows] or ["No changes yet."]
		embed = discord.Embed(title=f"{record.name}'s {name}", description="\n".join(lines)[:4000],
		                      color=discord.Color.dark_gold())
		embed.set_footer(text=f"Now: {balance_text(guild_id, record.currency)}")
		await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot) :
	await bot.add_cog(Currency(bot))
