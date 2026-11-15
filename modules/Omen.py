"""Omens: a character draws a card from a deck (tarot, bone casting, or a server's own deck made with /table create
deck:true) once every OMEN_DAYS days, without repeats until the deck runs out. With OMEN_EFFECTS on, a card can be a
boon (the next failed roll is made again) or a bane (-1 on the next check); by default cards are pure story. Seers
(an occupation marked seer with /downtime occupation) read for others. See design/roleplay-tools.md, section 15.
"""
import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.combat.AutoComplete import AutoComplete
from classes.flavor import OmenFlow
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.OccupationTransactions import OccupationTransactions
from views.combat.Pickers import reply

EFFECT_TEXT = {OmenFlow.BOON : "✨ A boon: the next failed roll is made again.",
               OmenFlow.BANE : "🌑 A bane: -1 on the next check."}


# ============================================================
async def deck_autocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	return [Choice(name=title[:100], value=key) for key, title in OmenFlow.decks(interaction.guild_id)
	        if current.lower() in title.lower()][:25]


# ============================================================
async def member_characters(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	member = interaction.namespace.member
	if member is None :
		return []
	return [Choice(name=character.name[:100], value=character.name[:100])
	        for character in CharacterTransactions().get_all(member.id, interaction.guild_id, states=[APPROVED])
	        if current.lower() in character.name.lower()][:25]


# ============================================================
def card_embed(character_name: str, drawn: dict, reader: str | None = None) -> discord.Embed :
	title = f"🔮 {drawn['card']}" + (" (reversed)" if drawn["orientation"] == "reversed" else "")
	embed = discord.Embed(title=title[:256], description=f"*{drawn['text']}*"[:4096], colour=discord.Colour.dark_magenta())
	embed.set_author(name=f"{character_name} draws from {drawn['deck']}" + (f", read by {reader}" if reader else ""))
	if drawn["effect"] in EFFECT_TEXT :
		embed.add_field(name="Omen", value=EFFECT_TEXT[drawn["effect"]], inline=False)
	return embed


@app_commands.guild_only()
class Omen(commands.GroupCog, name="Omen", group_name="omen") :
	"""Fortune cards and bone casting for your character."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@app_commands.command(name="draw", description="Draws an omen for your character")
	@app_commands.autocomplete(character=AutoComplete().approved_character, deck=deck_autocomplete)
	@app_commands.describe(deck="The deck (default: tarot)")
	async def draw(self, interaction: discord.Interaction, character: str, deck: str = "tarot") :
		"""
		Draws a card and posts it with its meaning. Each character draws once every OMEN_DAYS days.
		"""
		record = CharacterTransactions().get(interaction.user.id, interaction.guild_id, character)
		if record is None or record.state != APPROVED :
			return await reply(interaction, f"You have no approved character called {character}.")
		drawn, problem = OmenFlow.draw(record, deck)
		if problem :
			return await reply(interaction, problem)
		await interaction.response.send_message(embed=card_embed(record.name, drawn))

	# ============================================================
	@app_commands.command(name="read", description="Reads an omen for another character (seers)")
	@app_commands.autocomplete(seer=AutoComplete().approved_character, character=member_characters,
	                           deck=deck_autocomplete)
	@app_commands.describe(seer="Your character, who holds a seer occupation", member="Whose character you read for",
	                       character="Their character", deck="The deck (default: tarot)")
	async def read(self, interaction: discord.Interaction, seer: str, member: discord.Member, character: str,
	               deck: str = "tarot") :
		"""
		A seer reads for another character: the card is posted and its omen goes to that character. It counts as that
		character's draw, not the seer's.
		"""
		reader = CharacterTransactions().get(interaction.user.id, interaction.guild_id, seer)
		occupation = OccupationTransactions().get(reader.occupation_id) if reader and reader.occupation_id else None
		if reader is None or occupation is None or not occupation.seer :
			return await reply(interaction, "Only a character with a seer occupation can read for others.")
		target = CharacterTransactions().get(member.id, interaction.guild_id, character)
		if target is None or target.state != APPROVED :
			return await reply(interaction, f"{member.display_name} has no approved character called {character}.")
		drawn, problem = OmenFlow.draw(target, deck, interaction.user.id)
		if problem :
			return await reply(interaction, problem)
		await interaction.response.send_message(content=member.mention, embed=card_embed(target.name, drawn,
		                                                                                 reader.name),
		                                        allowed_mentions=discord.AllowedMentions(users=[member]))

	# ============================================================
	@app_commands.command(name="decks", description="Lists the decks you can draw from")
	async def decks(self, interaction: discord.Interaction) :
		"""
		Lists the built-in decks and the server's own (roll tables made as decks).
		"""
		lines = [f"**{title}** (`{key}`)" for key, title in OmenFlow.decks(interaction.guild_id)]
		await reply(interaction, "\n".join(lines) or "There are no decks.")


async def setup(bot) :
	await bot.add_cog(Omen(bot))
