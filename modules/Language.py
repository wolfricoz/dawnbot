"""Languages: characters speak them, and readers whose characters don't know one see it scrambled.

Write `{Elvish}` in a post to switch to Elvish for the rest of it, `{}` (or `{common}`) to switch back; `/language speak`
sets a language a character's posts use unless they say otherwise. In `speech` mode (LANGUAGE_SCRAMBLE) only quoted
text is scrambled. The post gets an Understand button (and the message menu has Understand) that shows each member
what their characters understand: everything when fluent, about half the words when they know it partly. Staff always
read everything. Characters pick LANGUAGE_SLOTS languages, plus 1 per 2 Intelligence above 5, with /language pick;
species can give languages; staff grant more, and downtime study teaches them. See design/roleplay-tools.md, section 1.
"""
import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.combat.AutoComplete import AutoComplete
from classes.language import Languages
from classes.language.LanguageFlow import GRANTED, LanguageFlow, START
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.LanguageTransactions import LanguageTransactions
from database.transactions.SpeciesTransactions import SpeciesTransactions
from views.combat.Pickers import reply

SOUND_CHOICES = [Choice(name=f"{name.capitalize()}: {' '.join(pieces[:5])}", value=name)
                 for name, pieces in Languages.SOUNDS.items()]
FLUENCY_CHOICES = [Choice(name="Fluent", value=Languages.FLUENT), Choice(name="Partly", value=Languages.PARTIAL)]


# ============================================================
async def language_autocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	LanguageFlow.common(interaction.guild_id)
	return [Choice(name=language.name[:100], value=language.name[:100])
	        for language in LanguageTransactions().get_all(interaction.guild_id)
	        if current.lower() in language.name.lower()][:25]


# ============================================================
async def member_characters(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	member = interaction.namespace.member
	if member is None :
		return []
	return [Choice(name=character.name[:100], value=character.name[:100])
	        for character in CharacterTransactions().get_in_guild(interaction.guild_id, member.id)
	        if current.lower() in character.name.lower()][:25]


# ============================================================
async def species_autocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	return [Choice(name=species.name[:100], value=species.name[:100])
	        for species in SpeciesTransactions().get_all(interaction.guild_id)
	        if current.lower() in species.name.lower()][:25]


# ============================================================
def parse_syllables(text: str | None) -> list[str] | None :
	pieces = [piece.strip() for piece in (text or "").replace(";", ",").split(",") if piece.strip()]
	return pieces[:40] or None


@app_commands.guild_only()
class Language(commands.GroupCog, name="Language", group_name="language") :
	"""Languages characters speak; others see them scrambled until they understand."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot
		self.understand_menu = app_commands.ContextMenu(name="Understand", callback=self.understand)
		self.bot.tree.add_command(self.understand_menu)

	# ============================================================
	async def cog_unload(self) :
		self.bot.tree.remove_command(self.understand_menu.name, type=self.understand_menu.type)

	# ============================================================
	async def understand(self, interaction: discord.Interaction, message: discord.Message) :
		"""Shows what a post made in a language says, as far as your characters understand it."""
		await interaction.response.send_message(
			LanguageFlow.understand_text(interaction.guild_id, interaction.user, message.id), ephemeral=True)

	# ============================================================
	@app_commands.command(name="add", description="Adds a language")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.choices(sound=SOUND_CHOICES)
	@app_commands.describe(name="The language's name", sound="How its scrambled text looks",
	                       syllables="Your own sounds instead, separated by commas: ae, th, el",
	                       description="What it is and who speaks it")
	async def add(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 50], sound: Choice[str],
	              syllables: app_commands.Range[str, 1, 300] = None,
	              description: app_commands.Range[str, 1, 1000] = None) :
		"""
		Adds a language characters can learn. Its scrambled text is built from the sound's pieces (or your own).

		**Permissions:**
		- `Manage Messages`
		"""
		LanguageFlow.common(interaction.guild_id)
		if name.strip().lower() == "common" :
			return await reply(interaction, "`common` always means the common language; pick another name.")
		language = LanguageTransactions().add(interaction.guild_id, name.strip(), sound=sound.value,
		                                      syllables=parse_syllables(syllables), description=description)
		if language is None :
			return await reply(interaction, f"There already is a language called {name}.")
		sample = Languages.scramble('"Well met, traveller. The road is long."', language.id, language.sound,
		                            language.syllables)
		await reply(interaction, f"Added **{language.name}**. It reads like: {sample}")

	# ============================================================
	@app_commands.command(name="edit", description="Changes a language")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(language=language_autocomplete)
	@app_commands.choices(sound=SOUND_CHOICES)
	async def edit(self, interaction: discord.Interaction, language: str, name: app_commands.Range[str, 1, 50] = None,
	               sound: Choice[str] = None, syllables: app_commands.Range[str, 1, 300] = None,
	               description: app_commands.Range[str, 1, 1000] = None) :
		"""
		Changes a language's name, sound or description. Posts already made scramble with the new sound.

		**Permissions:**
		- `Manage Messages`
		"""
		record = LanguageTransactions().find(interaction.guild_id, language)
		if record is None :
			return await reply(interaction, f"There is no language called {language}.")
		if name and name.lower() != record.name.lower() and LanguageTransactions().find(interaction.guild_id, name) :
			return await reply(interaction, f"There already is a language called {name}.")
		changes = {key : value for key, value in (("name", name), ("sound", sound.value if sound else None),
		                                          ("syllables", parse_syllables(syllables)),
		                                          ("description", description)) if value}
		LanguageTransactions().update(record.id, **changes)
		await reply(interaction, f"Saved **{name or record.name}**.")

	# ============================================================
	@app_commands.command(name="remove", description="Removes a language")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(language=language_autocomplete)
	async def remove(self, interaction: discord.Interaction, language: str) :
		"""
		Removes a language; characters forget it and its old posts can no longer be understood. The common language
		can't be removed.

		**Permissions:**
		- `Manage Messages`
		"""
		record = LanguageTransactions().find(interaction.guild_id, language)
		if record is None :
			return await reply(interaction, f"There is no language called {language}.")
		if record.common :
			return await reply(interaction, "The common language can't be removed.")
		LanguageTransactions().delete(record.id)
		await reply(interaction, f"Removed **{record.name}**.")

	# ============================================================
	@app_commands.command(name="list", description="Lists the server's languages")
	async def list_languages(self, interaction: discord.Interaction) :
		"""
		Lists the languages with a sample of how each looks scrambled.
		"""
		LanguageFlow.common(interaction.guild_id)
		lines = []
		for language in LanguageTransactions().get_all(interaction.guild_id) :
			if language.common :
				lines.append(f"**{language.name}** (common: everyone speaks it)")
				continue
			sample = Languages.scramble_word("Greetings", language.id, language.sound, language.syllables)
			lines.append(f"**{language.name}** · {sample}"
			             f"{f' · {language.description[:80]}' if language.description else ''}")
		await reply(interaction, "\n".join(lines)[:2000])

	# ============================================================
	@app_commands.command(name="known", description="Shows the languages a character speaks")
	@app_commands.autocomplete(character=AutoComplete().character)
	async def known(self, interaction: discord.Interaction, character: str) :
		"""
		Shows what your character speaks, the language its posts use, and how many starting picks it has left.
		"""
		record = CharacterTransactions().get(interaction.user.id, interaction.guild_id, character)
		if record is None :
			return await reply(interaction, f"You have no character called {character}.")
		common = LanguageFlow.common(interaction.guild_id)
		lines = [f"**{common.name}** (fluent)"]
		for language_id, fluency in LanguageFlow.known(record).items() :
			language = LanguageTransactions().get(language_id)
			if language is not None :
				lines.append(f"**{language.name}** ({'fluent' if fluency == Languages.FLUENT else 'partly'})")
		speaking = LanguageTransactions().get(record.speaking_language_id)
		used, allowed = LanguageFlow.slots(record)
		lines.append(f"Posts in: {speaking.name if speaking else common.name}")
		lines.append(f"Starting picks: {used} of {allowed} used")
		await reply(interaction, f"**{record.name}** speaks:\n" + "\n".join(lines))

	# ============================================================
	@app_commands.command(name="pick", description="Picks one of your character's starting languages")
	@app_commands.autocomplete(character=AutoComplete().character, language=language_autocomplete)
	async def pick(self, interaction: discord.Interaction, character: str, language: str) :
		"""
		Gives your character one of its starting languages (fluently). A character gets LANGUAGE_SLOTS picks, plus 1
		per 2 Intelligence above 5.
		"""
		record = CharacterTransactions().get(interaction.user.id, interaction.guild_id, character)
		target = LanguageTransactions().find(interaction.guild_id, language)
		if record is None :
			return await reply(interaction, f"You have no character called {character}.")
		if target is None or target.common :
			return await reply(interaction, f"There is no language called {language} to pick.")
		if target.id in LanguageFlow.known(record) :
			return await reply(interaction, f"{record.name} already speaks {target.name}.")
		used, allowed = LanguageFlow.slots(record)
		if used >= allowed :
			return await reply(interaction, f"{record.name} has used all {allowed} starting picks; more come from "
			                                f"study in /downtime or from staff.")
		LanguageTransactions().teach(record.id, target.id, Languages.FLUENT, START)
		await reply(interaction, f"{record.name} speaks {target.name} ({used + 1} of {allowed} picks used).")

	# ============================================================
	@app_commands.command(name="speak", description="Sets the language your character's posts use")
	@app_commands.autocomplete(character=AutoComplete().character, language=language_autocomplete)
	@app_commands.describe(language="The language (the common one to go back)")
	async def speak(self, interaction: discord.Interaction, character: str, language: str) :
		"""
		Makes your character's posts use a language unless they switch with `{...}` markers. Pick the common language
		to go back.
		"""
		record = CharacterTransactions().get(interaction.user.id, interaction.guild_id, character)
		target = LanguageTransactions().find(interaction.guild_id, language)
		if record is None :
			return await reply(interaction, f"You have no character called {character}.")
		if target is None :
			return await reply(interaction, f"There is no language called {language}.")
		if target.common :
			CharacterTransactions().update(record.id, speaking_language_id=None)
			return await reply(interaction, f"{record.name} speaks {target.name} again.")
		if target.id not in LanguageFlow.known(record) :
			return await reply(interaction, f"{record.name} doesn't speak {target.name}.")
		CharacterTransactions().update(record.id, speaking_language_id=target.id)
		await reply(interaction, f"{record.name}'s posts are in {target.name} now; `{{}}` in a post switches back for "
		                         f"the rest of it.")

	# ============================================================
	@app_commands.command(name="grant", description="Teaches a member's character a language (staff)")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(character=member_characters, language=language_autocomplete)
	@app_commands.choices(fluency=FLUENCY_CHOICES)
	async def grant(self, interaction: discord.Interaction, member: discord.Member, character: str, language: str,
	                fluency: Choice[str] = None) :
		"""
		Teaches a character a language (fluently unless you say partly), outside its starting picks.

		**Permissions:**
		- `Manage Messages`
		"""
		record = CharacterTransactions().get(member.id, interaction.guild_id, character)
		target = LanguageTransactions().find(interaction.guild_id, language)
		if record is None or target is None or target.common :
			return await reply(interaction, "Pick one of the member's characters and a language that isn't common.")
		level = fluency.value if fluency else Languages.FLUENT
		LanguageTransactions().teach(record.id, target.id, level, GRANTED)
		await reply(interaction, f"{record.name} now speaks {target.name} ({'fluently' if level == Languages.FLUENT else 'partly'}).")

	# ============================================================
	@app_commands.command(name="take", description="Makes a member's character forget a language (staff)")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(character=member_characters, language=language_autocomplete)
	async def take(self, interaction: discord.Interaction, member: discord.Member, character: str, language: str) :
		"""
		Takes a language away from a character (species languages stay).

		**Permissions:**
		- `Manage Messages`
		"""
		record = CharacterTransactions().get(member.id, interaction.guild_id, character)
		target = LanguageTransactions().find(interaction.guild_id, language)
		if record is None or target is None or not LanguageTransactions().forget(record.id, target.id) :
			return await reply(interaction, "That character doesn't know that language (or only through its species).")
		if record.speaking_language_id == target.id :
			CharacterTransactions().update(record.id, speaking_language_id=None)
		await reply(interaction, f"{record.name} forgot {target.name}.")

	# ============================================================
	@app_commands.command(name="species", description="Gives a species a language, or takes it away (staff)")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(species=species_autocomplete, language=language_autocomplete)
	async def species(self, interaction: discord.Interaction, species: str, language: str) :
		"""
		Every character of the species speaks the language fluently. Using it again takes the language away.

		**Permissions:**
		- `Manage Messages`
		"""
		record = SpeciesTransactions().find(interaction.guild_id, species)
		target = LanguageTransactions().find(interaction.guild_id, language)
		if record is None or target is None or target.common :
			return await reply(interaction, "Pick a species and a language that isn't common.")
		current = [int(language_id) for language_id in record.language_ids or []]
		if target.id in current :
			current.remove(target.id)
			text = f"{record.name} no longer speaks {target.name}."
		else :
			current.append(target.id)
			text = f"Every {record.name} speaks {target.name}."
		SpeciesTransactions().update(record.id, language_ids=current)
		await reply(interaction, text)


async def setup(bot) :
	await bot.add_cog(Language(bot))
