"""Staff tools for the server's economy: a report on how much currency is around and where it comes from and goes,
and an audit of one character's currency changes. Both read the ledger every currency change is written to, so staff
can tell when prices or income need adjusting and spot one-sided deals.
"""
import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.economy import Report
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.CurrencyTransactions import CurrencyTransactions
from modules.Currency import balance_text, currency_name, ledger_line

AUDIT_LENGTH = 25
FIELD_LIMIT = 1024


@app_commands.guild_only()
class Economy(commands.GroupCog, name="Economy", group_name="economy") :
	"""Staff reports on the server's currency."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	async def _characters(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		member = interaction.namespace.member
		if member is None :
			return []
		return [Choice(name=character.name, value=character.name)
		        for character in CharacterTransactions().get_all(member.id, interaction.guild_id)
		        if current.lower() in character.name.lower()][:25]

	# ============================================================
	@app_commands.command(name="report")
	@app_commands.checks.has_permissions(manage_messages=True)
	async def report(self, interaction: discord.Interaction, days: app_commands.Range[int, 1, 90] = Report.DAYS) :
		"""
		Shows the server's economy: how much currency the approved characters hold and the median, what came in and
		went out over the last `days` (default 7) by reason, the richest characters and the biggest earners. Use it
		to see whether prices or income need adjusting.

		**Permissions:**
		- `Manage Messages`
		"""
		await interaction.response.defer(ephemeral=True)
		guild_id = interaction.guild_id
		report = Report.build(guild_id, days=days)
		embed = discord.Embed(title="Economy report", color=discord.Color.dark_gold())
		for name, value in Report.lines(report, currency_name(guild_id), days).items() :
			embed.add_field(name=name, value=value[:FIELD_LIMIT], inline=False)
		await interaction.followup.send(embed=embed, ephemeral=True)

	# ============================================================
	@app_commands.command(name="audit")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(character=_characters)
	async def audit(self, interaction: discord.Interaction, member: discord.Member, character: str) :
		"""
		Shows the last 25 changes to one character's currency, with who made each change: roleplay earnings,
		purchases and sales, jobs, work, and what staff gave or took.

		**Permissions:**
		- `Manage Messages`
		"""
		record = CharacterTransactions().get(member.id, interaction.guild_id, character)
		if record is None :
			return await interaction.response.send_message(f"{member.display_name} has no character called "
			                                               f"{character}.", ephemeral=True)
		guild_id = interaction.guild_id
		name = currency_name(guild_id)
		rows = CurrencyTransactions().get_all(record.id, limit=AUDIT_LENGTH)
		lines = []
		for row in rows :
			line = ledger_line(row, name)
			if row.actor_uid and row.actor_uid != member.id and f"<@{row.actor_uid}>" not in line :
				line += f" · by <@{row.actor_uid}>"
			lines.append(line)
		embed = discord.Embed(title=f"{record.name}'s {name}", description="\n".join(lines or ["No changes yet."])[:4000],
		                      color=discord.Color.dark_gold())
		embed.set_footer(text=f"Now: {balance_text(guild_id, record.currency)} · {member.display_name}")
		await interaction.response.send_message(embed=embed, ephemeral=True,
		                                        allowed_mentions=discord.AllowedMentions.none())


async def setup(bot) :
	await bot.add_cog(Economy(bot))
