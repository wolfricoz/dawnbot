"""The chronicle: finished scenes written up as transcripts in the CHRONICLE forum, with an HTML and a Markdown file.

Scenes write theirs when they end. `/chronicle make` writes one for older roleplay between two message links, and
`/chronicle character` lists the chronicles a character appears in. See design/roleplay-tools.md, section 3.
"""
import discord
from discord import app_commands
from discord.ext import commands

from classes.combat.AutoComplete import AutoComplete
from classes.kernel.GMRole import is_gm
from classes.scenes.ChronicleFlow import ChronicleFlow
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.ProxyTransactions import ProxyTransactions
from database.transactions.SceneTransactions import SceneTransactions
from views.combat.Pickers import reply


@app_commands.guild_only()
class Chronicle(commands.GroupCog, name="Chronicle", group_name="chronicle") :
	"""Transcripts of finished scenes and older roleplay, and the scenes a character was in."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@app_commands.command(name="make", description="Writes a chronicle of roleplay between two message links")
	@app_commands.describe(first="Link to the first message", last="Link to the last message",
	                       title="The chronicle's title")
	async def make(self, interaction: discord.Interaction, first: str, last: str,
	               title: app_commands.Range[str, 1, 200]) :
		"""
		Writes a chronicle of the posts made as characters between two messages in the same channel or thread
		(right-click a message, Copy Message Link). Staff can chronicle anything; other members only roleplay their
		characters took part in.
		"""
		start, end = ChronicleFlow.parse_link(first), ChronicleFlow.parse_link(last)
		if start is None or end is None :
			return await reply(interaction, "Give two message links (right-click a message, Copy Message Link).")
		if start[0] != interaction.guild_id or start[1] != end[1] :
			return await reply(interaction, "Both messages need to be in the same channel on this server.")
		first_id, last_id = sorted((start[2], end[2]))
		channel = interaction.guild.get_channel_or_thread(start[1])
		if channel is None :
			return await reply(interaction, "I can't see that channel.")
		if not is_gm(interaction.user) :
			logged = ProxyTransactions().in_range(channel.id, first_id, last_id)
			if not any(entry.uid == interaction.user.id for entry in logged) :
				return await reply(interaction, "None of your characters posted there; staff can chronicle it.")
		await interaction.response.defer(ephemeral=True, thinking=True)
		record, problem = await ChronicleFlow.write(interaction.client, interaction.guild, title, channel, first_id,
		                                            last_id, interaction.user.id)
		if problem :
			return await reply(interaction, problem)
		await reply(interaction, f"📜 Written: <#{record.thread_id}>." if record.thread_id else "📜 Written.")

	# ============================================================
	@app_commands.command(name="character", description="Lists the chronicles a character appears in")
	@app_commands.autocomplete(character=AutoComplete().character)
	@app_commands.describe(character="Your character")
	async def character(self, interaction: discord.Interaction, character: str) :
		"""
		Lists the scenes your character took part in that have a chronicle, newest first, with links.
		"""
		record = CharacterTransactions().get(interaction.user.id, interaction.guild_id, character)
		if record is None :
			return await reply(interaction, f"You have no character called {character}.")
		chronicles = SceneTransactions().chronicles_of(record.id)
		if not chronicles :
			return await reply(interaction, f"{record.name} isn't in any chronicle yet.")
		lines = [f"📜 **{chronicle.title}**" + (f" · <#{chronicle.thread_id}>" if chronicle.thread_id else "")
		         for chronicle in chronicles[:40]]
		await reply(interaction, f"**{record.name}'s story so far**\n" + "\n".join(lines))


async def setup(bot) :
	await bot.add_cog(Chronicle(bot))
