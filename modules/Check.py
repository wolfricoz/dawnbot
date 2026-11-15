"""Checks: anyone calls a check, players press Roll on its card to roll it as their character.

`/check call` posts a card for a SPECIAL check against a DC (individual, group, or opposed against an NPC); public,
with the DC hidden, or secret (only the caller sees the results). `/check oppose` pits your character against another
member's. `/check passive` rolls for every character that posted in the channel lately and shows only you the result,
with a button to tell those who passed what they notice. The rules are in classes/checks/Checks.py and
design/roleplay-tools.md (sections 7 and 8).
"""
import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.characters.Special import STATS
from classes.checks import Checks
from classes.checks.CheckFlow import CheckFlow
from classes.combat.AutoComplete import AutoComplete
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions

STAT_CHOICES = [Choice(name=stat.capitalize(), value=stat) for stat in STATS]
KIND_CHOICES = [Choice(name="Individual: everyone rolls for themselves", value=Checks.INDIVIDUAL),
                Choice(name="Group: succeeds when half of the rollers succeed", value=Checks.GROUP),
                Choice(name="Opposed: against an NPC's roll (give npc_bonus)", value=Checks.OPPOSED)]
VISIBILITY_CHOICES = [Choice(name="Public: everyone sees everything", value=Checks.PUBLIC),
                      Choice(name="Hidden DC: rolls and outcomes show, the DC doesn't", value=Checks.HIDDEN_DC),
                      Choice(name="Secret: only you see the results", value=Checks.SECRET)]


# ============================================================
async def dc_autocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	options = [Choice(name=f"{name.capitalize()} ({value})", value=str(value)) for name, value in Checks.DCS.items()
	           if current.lower() in name or current == str(value)]
	if current.strip().isdigit() and Checks.parse_dc(current) is not None and not options :
		options.append(Choice(name=f"DC {current.strip()}", value=current.strip()))
	return options[:25]


# ============================================================
async def their_characters(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	member = interaction.namespace.member
	if member is None :
		return []
	return [Choice(name=character.name[:100], value=character.name[:100])
	        for character in CharacterTransactions().get_all(member.id, interaction.guild_id, states=[APPROVED])
	        if current.lower() in character.name.lower()][:25]


@app_commands.guild_only()
class Check(commands.GroupCog, name="Check", group_name="check") :
	"""Checks players roll with a button: call one, oppose a character, or roll passively."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@app_commands.command(name="call", description="Calls for a check; players press Roll to roll it as their character")
	@app_commands.choices(stat=STAT_CHOICES, kind=KIND_CHOICES, visibility=VISIBILITY_CHOICES)
	@app_commands.autocomplete(dc=dc_autocomplete)
	@app_commands.describe(stat="The SPECIAL stat everyone rolls",
	                       dc="The number to reach: easy 8, average 12, hard 15, very hard 18, heroic 22, or any number",
	                       title="What the check is for, like 'Spot the pickpocket'",
	                       kind="Individual (default), group, or opposed against an NPC",
	                       visibility="Who sees the results (default public)",
	                       modifier="Added to everyone's roll, like -2 for fog",
	                       npc_bonus="Opposed checks: the NPC's bonus on its d20",
	                       npc_name="Opposed checks: the NPC's name",
	                       role="Only members with this role can roll",
	                       member="Only this member can roll",
	                       hours="Hours until it closes by itself (default 24)")
	async def call(self, interaction: discord.Interaction, stat: Choice[str], dc: str = None,
	               title: app_commands.Range[str, 1, 200] = None, kind: Choice[str] = None,
	               visibility: Choice[str] = None,
	               modifier: app_commands.Range[int, -Checks.MODIFIER_LIMIT, Checks.MODIFIER_LIMIT] = 0,
	               npc_bonus: app_commands.Range[int, -20, 30] = None, npc_name: app_commands.Range[str, 1, 80] = None,
	               role: discord.Role = None, member: discord.Member = None,
	               hours: app_commands.Range[int, 1, Checks.MAX_HOURS] = None) :
		"""
		Posts a check card in this channel. Each player presses **Roll** and picks a character; the bot rolls
		d20 + the stat's modifier (stat minus 5) + the modifier against the DC. The crit range widens with Luck and a
		natural 1 always fails. Each character rolls once. **Help** gives another member +2 on their roll, once per
		character. Whoever calls the check (or staff) can close it; it closes by itself after `hours`.

		- **Group** checks succeed when at least half of the rollers succeed.
		- **Opposed** checks are against an NPC: it rolls d20 + `npc_bonus` once, and players have to beat that total.
		- **Hidden DC** shows the rolls and outcomes but not the DC; **secret** shows only who rolled, while the caller
		  sees the results with the **Results** button.
		"""
		await CheckFlow.call(interaction, stat.value, dc, title, kind.value if kind else Checks.INDIVIDUAL,
		                     visibility.value if visibility else Checks.PUBLIC, modifier, npc_bonus, npc_name, role,
		                     member, hours)

	# ============================================================
	@app_commands.command(name="oppose", description="Pits one of your characters against another member's character")
	@app_commands.choices(stat=STAT_CHOICES, their_stat=STAT_CHOICES)
	@app_commands.autocomplete(character=AutoComplete().approved_character, their_character=their_characters)
	@app_commands.describe(member="The member whose character you oppose",
	                       their_character="Their character",
	                       character="Your character",
	                       stat="The stat your character rolls",
	                       their_stat="The stat their character rolls",
	                       title="What it is about, like 'Arm wrestling'",
	                       hours="Hours until it closes by itself (default 24)")
	async def oppose(self, interaction: discord.Interaction, member: discord.Member, their_character: str,
	                 character: str, stat: Choice[str], their_stat: Choice[str],
	                 title: app_commands.Range[str, 1, 200] = None,
	                 hours: app_commands.Range[int, 1, Checks.MAX_HOURS] = None) :
		"""
		Posts an opposed check: both players press **Roll**, each rolling d20 + their own stat's modifier. The higher
		total wins and a tie goes to the other member's character (the one defending). A critical success beats
		anything but another one; a fumble loses to anything but another fumble.
		"""
		await CheckFlow.oppose(interaction, member, their_character, character, stat.value, their_stat.value, title,
		                       hours)

	# ============================================================
	@app_commands.command(name="passive", description="Rolls secretly for every character that posted here lately")
	@app_commands.choices(stat=STAT_CHOICES)
	@app_commands.autocomplete(dc=dc_autocomplete)
	@app_commands.describe(stat="The SPECIAL stat they roll",
	                       dc="The number to reach: easy 8, average 12, hard 15, very hard 18, heroic 22, or any number",
	                       modifier="Added to everyone's roll",
	                       title="What it is for (only you see it)",
	                       role="Only characters of members with this role",
	                       member="Only this member's characters")
	async def passive(self, interaction: discord.Interaction, stat: Choice[str], dc: str,
	                  modifier: app_commands.Range[int, -Checks.MODIFIER_LIMIT, Checks.MODIFIER_LIMIT] = 0,
	                  title: app_commands.Range[str, 1, 200] = None, role: discord.Role = None,
	                  member: discord.Member = None) :
		"""
		Rolls the check for every approved character that posted in this channel (or thread) in the last 7 days,
		without anyone pressing anything. Only you see the results; **Reveal to those who passed** lets you write what
		they notice, which the bot sends to those players in a DM. Passive rolls don't count toward bad-roll protection.
		"""
		await CheckFlow.passive(interaction, stat.value, dc, modifier, title, role, member)


async def setup(bot) :
	await bot.add_cog(Check(bot))
