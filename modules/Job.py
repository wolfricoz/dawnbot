"""The job board: jobs posted to the JOB_BOARD forum with rewards, claimed by characters with a button, and finished
by the poster or staff, who pick who took part and how it went (success pays all, partial half, failure nothing).
Jobs past their deadline fail. With JOB_PLAYER_POSTS on, players post jobs as their characters and pay the currency
reward up front. See design/roleplay-tools.md, section 10.
"""
import discord
from discord import app_commands
from discord.ext import commands

from classes.combat.AutoComplete import AutoComplete
from classes.economy.JobFlow import JobFlow
from database.transactions.EconomyTransactions import EconomyTransactions
from modules.Faction import faction_autocomplete
from views.combat.Pickers import reply


class JobForm(discord.ui.Modal) :
	"""A job's description."""

	def __init__(self, title: str, on_submit) :
		super().__init__(title=f"Job: {title}"[:45])
		self.handler = on_submit
		self.description = discord.ui.TextInput(label="What is the job?", style=discord.TextStyle.paragraph,
		                                        max_length=3000)
		self.add_item(self.description)

	# ============================================================
	async def on_submit(self, interaction: discord.Interaction) :
		await self.handler(interaction, self.description.value)


@app_commands.guild_only()
class Job(commands.GroupCog, name="Job", group_name="job") :
	"""The job board: post jobs, claim them and get paid when they are done."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@app_commands.command(name="post", description="Posts a job on the job board")
	@app_commands.autocomplete(faction=faction_autocomplete, as_character=AutoComplete().approved_character)
	@app_commands.describe(title="The job's title", currency="Currency each character gets",
	                       xp="XP each character gets", items="Catalog items each gets, separated by commas",
	                       slots="How many characters can take it", min_level="The lowest level that can take it",
	                       faction="The faction it is for", rep_success="Standing gained on success",
	                       rep_failure="Standing lost on failure", deadline_hours="Hours until it fails",
	                       location="Where it happens", as_character="Post it as your character (player jobs)")
	async def post(self, interaction: discord.Interaction, title: app_commands.Range[str, 1, 100],
	               currency: app_commands.Range[int, 0, 1000000] = 0, xp: app_commands.Range[int, 0, 1000000] = 0,
	               items: str = None, slots: app_commands.Range[int, 1, 25] = 1,
	               min_level: app_commands.Range[int, 1, 100] = 1, faction: str = None,
	               rep_success: app_commands.Range[int, 0, 100] = 0, rep_failure: app_commands.Range[int, 0, 100] = 0,
	               deadline_hours: app_commands.Range[int, 1, 8760] = None, location: discord.TextChannel = None,
	               as_character: str = None) :
		"""
		Opens a form for the job's description and posts it as a thread on the job board with **Claim**,
		**Withdraw**, **Complete** and **Start scene** buttons. Staff post jobs; with JOB_PLAYER_POSTS on, players
		post them as a character and the currency reward (for every slot) is held until the job ends.
		"""
		async def described(form_interaction: discord.Interaction, description: str) :
			await form_interaction.response.defer(ephemeral=True, thinking=True)
			await JobFlow.post(form_interaction, title, description, currency, xp, items, slots, min_level, faction,
			                   rep_success, rep_failure, deadline_hours, location, as_character)

		await interaction.response.send_modal(JobForm(title, described))

	# ============================================================
	@app_commands.command(name="cancel", description="Cancels a job")
	@app_commands.describe(job="The job's number (in its footer)")
	async def cancel(self, interaction: discord.Interaction, job: int) :
		"""
		Cancels an open job; a player job's held reward goes back. Poster or staff.
		"""
		await JobFlow.cancel(interaction, job)

	# ============================================================
	@app_commands.command(name="list", description="Lists the open jobs")
	async def list_jobs(self, interaction: discord.Interaction) :
		"""
		Lists open and taken jobs with links.
		"""
		jobs = EconomyTransactions().jobs(interaction.guild_id)
		if not jobs :
			return await reply(interaction, "There are no open jobs.")
		lines = [f"#{job.id} · **{job.title}** · {JobFlow.reward_text(job)[:80]}"
		         f"{f' · <#{job.thread_id}>' if job.thread_id else ''}" for job in jobs]
		await reply(interaction, "\n".join(lines)[:2000])


async def setup(bot) :
	await bot.add_cog(Job(bot))
