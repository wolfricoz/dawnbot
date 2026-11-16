"""Downtime: once a day, a character works, studies a language, works on a crafting project, carouses or repairs gear.

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
from classes.gear import Condition
from classes.kernel import RoleplaySettings
from database.transactions.CharacterGearTransactions import CharacterGearTransactions
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.EconomyTransactions import EconomyTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from modules.Gear import entry_choices, find_entry
from resources.configs.ConfigMapping import ConfigMapping
from views.combat.Pickers import reply

REPAIR = "repair"

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
	"""Once a day: work, study, craft, carouse or repair gear."""

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
	async def _repair_items(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		"""Items that need repair: the owner's character's when `member` and `owner` are given, else your own."""
		namespace = interaction.namespace
		member = getattr(namespace, "member", None)
		user_id = member.id if member is not None else interaction.user.id
		name = getattr(namespace, "owner", None) or getattr(namespace, "character", None)
		character = CharacterTransactions().get(user_id, interaction.guild_id, name) if name else None
		if character is None :
			return []
		entries = [entry for entry in CharacterGearTransactions().get_all(character.id)
		           if Condition.of(entry) != Condition.GOOD]
		return entry_choices(entries, current)

	# ============================================================
	async def _owners(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		member = interaction.namespace.member
		if member is None :
			return []
		return [Choice(name=character.name, value=character.name)
		        for character in CharacterTransactions().get_all(member.id, interaction.guild_id)
		        if current.lower() in character.name.lower()][:25]

	# ============================================================
	@app_commands.command(name="repair", description="Spends today's downtime repairing gear")
	@app_commands.autocomplete(character=AutoComplete().approved_character, item=_repair_items, owner=_owners)
	@app_commands.describe(character="Your character, who does the repair", item="The item to repair",
	                       member="Whose character owns it (leave out for your own)",
	                       owner="That member's character")
	async def repair(self, interaction: discord.Interaction, character: str, item: str,
	                 member: discord.Member = None, owner: str = None) :
		"""
		Spends the character's downtime for the day repairing an item, its own or another character's. Its occupation
		has to repair that kind of gear (staff set it with /downtime occupation). It rolls the better of Agility and
		Intelligence against 10 (Worn), 13 (Damaged) or 16 (Broken); a success makes the item good as new. When the
		item has a salvage list, the repair uses one of those materials from the repairer (lost on a bad failure too).
		"""
		repairer = CharacterTransactions().get(interaction.user.id, interaction.guild_id, character)
		problem = DowntimeFlow.problem(repairer)
		if problem :
			return await reply(interaction, problem)
		if member is not None and owner :
			target = CharacterTransactions().get(member.id, interaction.guild_id, owner)
			if target is None :
				return await reply(interaction, f"{member.display_name} has no character called {owner}.")
		else :
			target = repairer
		entry = find_entry(CharacterGearTransactions().get_all(target.id), item)
		if entry is None :
			return await reply(interaction, f"{target.name} doesn't own {item}.")
		outcome, lines = Condition.repair_by_hand(repairer, entry, GearItemTransactions().get(entry.gear_item_id),
		                                          target)
		if outcome is None :
			return await reply(interaction, lines[0])
		EconomyTransactions().add_downtime(repairer.id, DowntimeFlow.day(interaction.guild_id), REPAIR, outcome,
		                                   {"entry_id" : entry.id, "owner_id" : target.id})
		embed = discord.Embed(title="🌙 Downtime: Repair", description="\n".join(lines)[:4096],
		                      colour=discord.Colour.dark_gold())
		embed.set_author(name=repairer.name)
		private = RoleplaySettings.toggle(interaction.guild_id, ConfigMapping.DOWNTIME_PRIVATE)
		await interaction.response.send_message(embed=embed, ephemeral=private)

	# ============================================================
	@app_commands.command(name="occupation", description="Sets what downtime work pays for an occupation (staff)")
	@gm_only()
	@app_commands.autocomplete(occupation=occupation_autocomplete, table=table_autocomplete)
	@app_commands.choices(stat=STAT_CHOICES)
	@app_commands.describe(pay="What a day pays (empty: WORK_PAY)", stat="The stat the work rolls",
	                       table="A roll table for a great day", seer="Seers can read omens for others",
	                       repairs="What it repairs: weapon, clothing, light, medium, heavy, accessory (or none)")
	async def occupation(self, interaction: discord.Interaction, occupation: str,
	                     pay: app_commands.Range[int, 0, 100000] = None, stat: Choice[str] = None,
	                     table: str = None, seer: bool = None, repairs: app_commands.Range[str, 1, 100] = None) :
		"""
		Sets an occupation's downtime work: its pay, the stat it rolls and a roll table for a crit. `seer` lets its
		characters read omens for others (/omen read). `repairs` lists the gear its characters can repair with
		/downtime repair, like `weapon, medium, heavy` for a blacksmith (armor goes by its class); `none` clears it.

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
		if repairs is not None :
			kinds = [word.strip().lower() for word in repairs.replace(";", ",").split(",") if word.strip()]
			kinds = [] if kinds == ["none"] else kinds
			unknown = [kind for kind in kinds if kind not in Condition.REPAIR_KINDS]
			if unknown :
				return await reply(interaction, f"Unknown gear kinds: {', '.join(unknown)}. Use "
				                                f"{', '.join(Condition.REPAIR_KINDS)}.")
			changes["repairs"] = kinds or None
		updated = OccupationTransactions().update(record.id, **changes)
		await reply(interaction, f"**{record.name}**: pays {updated.pay if updated.pay is not None else 'WORK_PAY'}, "
		                         f"rolls {(updated.work_stat or 'strength').capitalize()}"
		                         f"{', seer' if updated.seer else ''}"
		                         f"{', repairs ' + ', '.join(updated.repairs) if updated.repairs else ''}.")

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
