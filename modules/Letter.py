"""Letters: in-character mail between characters, delivered after a delay (LETTER_DELAY hours, or the route between
them when travel is on), or in an hour by express courier (COURIER_COST). A letter can be written in a language, and
arrives scrambled when the recipient's character doesn't know it. Letters are private: staff only read one that was
reported, or intercepted where LETTER_INTERCEPT is on. See design/roleplay-tools.md, section 14.
"""
import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.combat.AutoComplete import AutoComplete
from classes.language.LetterFlow import LetterFlow
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.LanguageTransactions import LanguageTransactions
from views.combat.Pickers import reply

ACTION_CHOICES = [Choice(name="Read it", value="read"), Choice(name="Hold it back", value="hold"),
                  Choice(name="Let it through now", value="deliver"), Choice(name="Destroy it", value="destroy")]


# ============================================================
async def recipient_autocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	choices = []
	for character in CharacterTransactions().get_in_guild(interaction.guild_id) :
		if character.state != APPROVED or current.lower() not in character.name.lower() :
			continue
		member = interaction.guild.get_member(character.uid)
		owner = f" ({member.display_name})" if member else ""
		choices.append(Choice(name=f"{character.name}{owner}"[:100], value=str(character.id)))
	return choices[:25]


# ============================================================
async def language_autocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	return [Choice(name=language.name[:100], value=language.name[:100])
	        for language in LanguageTransactions().get_all(interaction.guild_id)
	        if current.lower() in language.name.lower()][:25]


@app_commands.guild_only()
class Letter(commands.GroupCog, name="Letter", group_name="letter") :
	"""In-character letters between characters, delivered after a while."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@app_commands.command(name="write", description="Writes a letter from your character to another character")
	@app_commands.autocomplete(sender=AutoComplete().approved_character, recipient=recipient_autocomplete,
	                           language=language_autocomplete)
	@app_commands.describe(sender="Your character", recipient="Who it is for", language="The language it is written in",
	                       express="Delivered in an hour, for the courier's fee",
	                       sealed="The recipient sees if it was opened on the way")
	async def write(self, interaction: discord.Interaction, sender: str, recipient: str, language: str = None,
	                express: bool = False, sealed: bool = False) :
		"""
		Opens a form for the letter's subject and text. It arrives in the recipient player's DMs (or, with DMs closed,
		with a ping in the letter channel), with Reply and Report buttons, and stays in /letter inbox.
		"""
		await LetterFlow.start(interaction, sender, recipient, language, express, sealed)

	# ============================================================
	@app_commands.command(name="inbox", description="Lists the letters your character received")
	@app_commands.autocomplete(character=AutoComplete().character)
	async def inbox(self, interaction: discord.Interaction, character: str) :
		"""
		Lists the latest letters your character received; read one with /letter read.
		"""
		record = CharacterTransactions().get(interaction.user.id, interaction.guild_id, character)
		if record is None :
			return await reply(interaction, f"You have no character called {character}.")
		letters = LanguageTransactions().inbox(record.id)
		if not letters :
			return await reply(interaction, f"{record.name} has no letters.")
		lines = [f"{'📩' if letter.read_at is None else '✉️'} **#{letter.id}** · {letter.from_name} · "
		         f"“{letter.subject}”" for letter in letters]
		await reply(interaction, f"**{record.name}'s letters**\n" + "\n".join(lines))

	# ============================================================
	@app_commands.command(name="read", description="Reads a letter")
	@app_commands.describe(letter="The letter's number from /letter inbox")
	async def read(self, interaction: discord.Interaction, letter: int) :
		"""
		Shows a letter your character received (or sent), as your character understands its language.
		"""
		await LetterFlow.read(interaction, letter)

	# ============================================================
	@app_commands.command(name="transit", description="Lists the letters on their way (staff)")
	@app_commands.checks.has_permissions(manage_messages=True)
	async def transit(self, interaction: discord.Interaction) :
		"""
		Lists letters in transit: who wrote to whom and when they arrive. Subjects show only when interception is on;
		the text never shows here.

		**Permissions:**
		- `Manage Messages`
		"""
		lines = LetterFlow.transit_lines(interaction.guild_id)
		await reply(interaction, "\n".join(lines)[:2000] if lines else "No letters are on their way.")

	# ============================================================
	@app_commands.command(name="intercept", description="Reads, holds, releases or destroys a letter in transit (GM)")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.choices(action=ACTION_CHOICES)
	@app_commands.describe(letter="The letter's number from /letter transit", action="What to do with it")
	async def intercept(self, interaction: discord.Interaction, letter: int, action: Choice[str]) :
		"""
		An in-game intercept, only when LETTER_INTERCEPT is on. Reading a sealed letter breaks its seal, which the
		recipient sees.

		**Permissions:**
		- `Manage Messages`
		"""
		await LetterFlow.intercept(interaction, letter, action.value)


async def setup(bot) :
	await bot.add_cog(Letter(bot))
