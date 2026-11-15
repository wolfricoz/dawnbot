"""Downtime: once a day, a character works, studies a language, works on a crafting project or carouses.

Only characters with a roleplay post in the last DOWNTIME_ACTIVE_DAYS days can, and the day starts at DOWNTIME_RESET
(UTC). Work pays the occupation's pay (WORK_PAY by default) by how a roll on its stat goes; study teaches a language
over STUDY_DAYS good days; crafting works a day on a project; carousing costs CAROUSE_COST and overhears a rumor at +2.
See design/roleplay-tools.md, section 12.
"""
import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.kernel.GMRole import gm_only
from classes.characters.Special import STATS
from classes.checks import Checks
from classes.combat.AutoComplete import AutoComplete
from classes.economy import Downtime as DowntimeRules
from classes.economy.DowntimeFlow import DowntimeFlow
from database.transactions.LanguageTransactions import LanguageTransactions
from database.transactions.OccupationTransactions import OccupationTransactions
from database.transactions.RollTableTransactions import RollTableTransactions
from views.combat.Pickers import reply

ACTIVITY_CHOICES = [Choice(name="Work: earn your occupation's pay", value=DowntimeRules.WORK),
                    Choice(name="Study: learn a language", value=DowntimeRules.STUDY),
                    Choice(name="Craft: a day on a crafting project", value=DowntimeRules.CRAFT),
                    Choice(name="Carouse: spend a little, hear a rumor", value=DowntimeRules.CAROUSE)]
STAT_CHOICES = [Choice(name=stat.capitalize(), value=stat) for stat in STATS]
FLAVOR_CHOICES = [Choice(name=label, value=outcome) for outcome, label in
                  ((Checks.CRIT, "Critical success"), (Checks.STRONG, "Strong success"), (Checks.SUCCESS, "Success"),
                   (Checks.FAILURE, "Failure"), (Checks.BAD, "Bad failure"), (Checks.FUMBLE, "Fumble"))]


# ============================================================
async def language_autocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	return [Choice(name=language.name[:100], value=language.name[:100])
	        for language in LanguageTransactions().get_all(interaction.guild_id)
	        if not language.common and current.lower() in language.name.lower()][:25]


# ============================================================
async def occupation_autocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	return [Choice(name=occupation.name[:100], value=occupation.name[:100])
	        for occupation in OccupationTransactions().get_all(interaction.guild_id)
	        if current.lower() in occupation.name.lower()][:25]


# ============================================================
async def table_autocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	return [Choice(name=table.name[:100], value=table.name[:100])
	        for table in RollTableTransactions().get_all(interaction.guild_id)
	        if current.lower() in table.name.lower()][:25]


@app_commands.guild_only()
class Downtime(commands.GroupCog, name="Downtime", group_name="downtime") :
	"""Once a day: work, study, craft or carouse."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@app_commands.command(name="spend", description="Spends today's downtime on an activity")
	@app_commands.autocomplete(character=AutoComplete().approved_character, language=language_autocomplete)
	@app_commands.choices(activity=ACTIVITY_CHOICES, stat=STAT_CHOICES)
	@app_commands.describe(character="Your character", activity="What it does today",
	                       language="Study: the language", project="Craft: the project's number (default: the oldest)",
	                       stat="Work without an occupation: the stat you work with")
	async def spend(self, interaction: discord.Interaction, character: str, activity: Choice[str],
	                language: str = None, project: int = None, stat: Choice[str] = None) :
		"""
		Spends the character's downtime for the day. The result is posted here (or only shown to you with
		DOWNTIME_PRIVATE on).

		- **Work** rolls the occupation's stat against 12 and pays by how it went: nothing on a bad failure, half on a
		  failure, all on a success, 1.5x on a strong success and double (plus a roll on the occupation's table) on a
		  crit. Without an occupation it is odd jobs at half pay.
		- **Study** rolls Intelligence against 12: +1 on a success, +2 on a strong one. STUDY_DAYS points teach the
		  language partly, twice that fluently.
		- **Craft** works a day on a crafting project (see /craft).
		- **Carouse** costs CAROUSE_COST and overhears a rumor at +2.
		"""
		await DowntimeFlow.run(interaction, character, activity.value, language, project,
		                       stat.value if stat else None)

	# ============================================================
	@app_commands.command(name="occupation", description="Sets what downtime work pays for an occupation (staff)")
	@gm_only()
	@app_commands.autocomplete(occupation=occupation_autocomplete, table=table_autocomplete)
	@app_commands.choices(stat=STAT_CHOICES)
	@app_commands.describe(pay="What a day pays (empty: WORK_PAY)", stat="The stat the work rolls",
	                       table="A roll table for a great day", seer="Seers can read omens for others")
	async def occupation(self, interaction: discord.Interaction, occupation: str,
	                     pay: app_commands.Range[int, 0, 100000] = None, stat: Choice[str] = None,
	                     table: str = None, seer: bool = None) :
		"""
		Sets an occupation's downtime work: its pay, the stat it rolls and a roll table for a crit. `seer` lets its
		characters read omens for others (/omen read).

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		record = OccupationTransactions().find(interaction.guild_id, occupation)
		if record is None :
			return await reply(interaction, f"There is no occupation called {occupation}.")
		changes = {}
		if pay is not None :
			changes["pay"] = pay
		if stat is not None :
			changes["work_stat"] = stat.value
		if table :
			found = RollTableTransactions().find(interaction.guild_id, table)
			if found is None :
				return await reply(interaction, f"There is no roll table called {table}.")
			changes["table_id"] = found.id
		if seer is not None :
			changes["seer"] = seer
		updated = OccupationTransactions().update(record.id, **changes)
		await reply(interaction, f"**{record.name}**: pays {updated.pay if updated.pay is not None else 'WORK_PAY'}, "
		                         f"rolls {(updated.work_stat or 'strength').capitalize()}"
		                         f"{', seer' if updated.seer else ''}.")

	# ============================================================
	@app_commands.command(name="flavor", description="Adds a line to how an occupation's work day reads (staff)")
	@gm_only()
	@app_commands.autocomplete(occupation=occupation_autocomplete)
	@app_commands.choices(outcome=FLAVOR_CHOICES)
	@app_commands.describe(occupation="The occupation", outcome="Which result the line is for",
	                       line="The line (leave empty to clear that result's lines)")
	async def flavor(self, interaction: discord.Interaction, occupation: str, outcome: Choice[str],
	                 line: app_commands.Range[str, 1, 200] = None) :
		"""
		Adds a flavor line shown when a character of this occupation has that result at work; one is picked at random.
		Without a line, that result's lines are cleared and the default line is used again.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		record = OccupationTransactions().find(interaction.guild_id, occupation)
		if record is None :
			return await reply(interaction, f"There is no occupation called {occupation}.")
		flavor = dict(record.flavor or {})
		if line is None :
			flavor.pop(outcome.value, None)
			text = f"Cleared the {outcome.name.lower()} lines of {record.name}."
		else :
			flavor[outcome.value] = (flavor.get(outcome.value) or [])[:19] + [line]
			text = f"{record.name} has {len(flavor[outcome.value])} {outcome.name.lower()} lines now."
		OccupationTransactions().update(record.id, flavor=flavor)
		await reply(interaction, text)


async def setup(bot) :
	await bot.add_cog(Downtime(bot))
