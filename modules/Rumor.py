"""The rumor mill: anonymous rumors, rumors GMs plant (marked true, false or partly true, and maybe secret), and
characters overhearing them once a day. In `board` mode (RUMOR_MODE) rumors are posted to RUMOR_CHANNEL at once; in
`whisper` mode they are overheard and posted once 3 characters heard them. Every rumor is logged with its author in
MODLOG. Rumors fade after RUMOR_DAYS unless pinned. See design/roleplay-tools.md, section 6.
"""
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.kernel.GMRole import gm_only
from classes.combat.AutoComplete import AutoComplete
from classes.flavor.RumorFlow import RumorFlow, TRUTHS
from database.transactions.FlavorTransactions import FlavorTransactions
from views.combat.Pickers import reply

TRUTH_CHOICES = [Choice(name=truth.capitalize() if truth != "partial" else "Partly true", value=truth)
                 for truth in TRUTHS]


@app_commands.guild_only()
class Rumor(commands.GroupCog, name="Rumor", group_name="rumor") :
	"""Rumors: post them anonymously, overhear them, and plant some as a GM."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@app_commands.command(name="post", description="Spreads a rumor anonymously")
	@app_commands.autocomplete(character=AutoComplete().approved_character)
	@app_commands.describe(text="The rumor", location="Where it is going round", character="Who started it (hidden)")
	async def post(self, interaction: discord.Interaction, text: app_commands.Range[str, 5, 1000],
	               location: discord.TextChannel = None, character: str = None) :
		"""
		Spreads a rumor. Other players never see who started it; staff can, for moderation.
		"""
		await RumorFlow.post(interaction, text, location, character)

	# ============================================================
	@app_commands.command(name="listen", description="Keeps an ear out for rumors (once a day)")
	@app_commands.autocomplete(character=AutoComplete().approved_character)
	async def listen(self, interaction: discord.Interaction, character: str) :
		"""
		Rolls d20 + the better of your character's Perception or Charisma modifier against 12, once a day. A success
		hears a rumor (secret ones and the ones from where the character is first), a strong success two and a hint
		about whether one is true; a bad failure hears a false one.
		"""
		await RumorFlow.listen(interaction, character)

	# ============================================================
	@app_commands.command(name="plant", description="Plants a rumor as a GM, marked true or false")
	@gm_only()
	@app_commands.choices(truth=TRUTH_CHOICES)
	@app_commands.describe(text="The rumor", truth="Whether it is true (hidden from players)",
	                       secret="Never posted: it can only be overheard", location="Where it is going round")
	async def plant(self, interaction: discord.Interaction, text: app_commands.Range[str, 5, 1000],
	                truth: Choice[str], secret: bool = False, location: discord.TextChannel = None) :
		"""
		Plants a rumor. Characters who overhear it with a strong success get a hint about its truth.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		await RumorFlow.post(interaction, text, location, None, planted=True, truth=truth.value, secret=secret)

	# ============================================================
	@app_commands.command(name="mark", description="Marks a rumor true, false or partly true (staff)")
	@gm_only()
	@app_commands.choices(truth=TRUTH_CHOICES)
	async def mark(self, interaction: discord.Interaction, rumor: int, truth: Choice[str]) :
		"""
		Marks whether a rumor is true; players only learn it from hints.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		record = FlavorTransactions().rumor(rumor)
		if record is None or record.guild_id != interaction.guild_id :
			return await reply(interaction, "There is no rumor with that number.")
		FlavorTransactions().update_rumor(record.id, truth=truth.value)
		await reply(interaction, f"Rumor #{record.id} is {truth.name.lower()}.")

	# ============================================================
	@app_commands.command(name="pin", description="Keeps a rumor from fading, or lets it fade again (staff)")
	@gm_only()
	async def pin(self, interaction: discord.Interaction, rumor: int, pinned: bool = True) :
		"""
		Pinned rumors never fade.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		record = FlavorTransactions().rumor(rumor)
		if record is None or record.guild_id != interaction.guild_id :
			return await reply(interaction, "There is no rumor with that number.")
		FlavorTransactions().update_rumor(record.id, pinned=pinned)
		await reply(interaction, f"Rumor #{record.id} {'never fades' if pinned else 'fades as usual'}.")

	# ============================================================
	@app_commands.command(name="block", description="Stops a member posting rumors, or lets them again (staff)")
	@gm_only()
	async def block(self, interaction: discord.Interaction, member: discord.Member, blocked: bool = True) :
		"""
		Blocks (or unblocks) a member from /rumor post.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		FlavorTransactions().set_blocked(interaction.guild_id, member.id, blocked)
		await reply(interaction, f"{member.display_name} {'can no longer' if blocked else 'can'} post rumors.")

	# ============================================================
	@app_commands.command(name="list", description="Lists the rumors going round, with authors and truth (staff)")
	@gm_only()
	async def list_rumors(self, interaction: discord.Interaction) :
		"""
		Lists live rumors with their number, author, truth and how often they were overheard.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		rumors = FlavorTransactions().live(interaction.guild_id, datetime.now(timezone.utc))
		if not rumors :
			return await reply(interaction, "No rumors are going round.")
		lines = [f"#{rumor.id} · <@{rumor.author_uid}> · {rumor.truth}{' · secret' if rumor.secret else ''}"
		         f"{' · 📌' if rumor.pinned else ''} · heard {rumor.heard}× · {rumor.text[:80]}" for rumor in rumors[:30]]
		await reply(interaction, "\n".join(lines)[:2000])


async def setup(bot) :
	await bot.add_cog(Rumor(bot))
