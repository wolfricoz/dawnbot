"""Languages on a server (design/roleplay-tools.md, section 1): the common language, what a character knows, turning
a proxied post into what readers see, the Understand button and the chronicle's original text."""
import discord

from classes.characters.Special import Special
from classes.kernel import RoleplaySettings
from classes.language import Languages
from classes.language.Languages import FLUENT, PARTIAL, Segment
from database.database import Characters
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.LanguageTransactions import LanguageTransactions
from database.transactions.ProxyTransactions import ProxyTransactions
from database.transactions.SpeciesTransactions import SpeciesTransactions
from resources.configs.ConfigMapping import ConfigMapping

START = "start"
SPECIES = "species"
STUDY = "study"
GRANTED = "granted"


class LanguageFlow :

	# ============================================================
	@staticmethod
	def common(guild_id: int) :
		"""The server's common language, made on first use (named after COMMON_LANGUAGE)."""
		found = LanguageTransactions().common(guild_id)
		if found is not None :
			return found
		name = RoleplaySettings.text(guild_id, ConfigMapping.COMMON_LANGUAGE)
		existing = LanguageTransactions().find(guild_id, name)
		if existing is not None :
			return LanguageTransactions().update(existing.id, common=True)
		return LanguageTransactions().add(guild_id, name, common=True, sound="flowing",
		                                  description="The language everyone speaks.")

	# ============================================================
	@staticmethod
	def table(guild_id: int) -> dict :
		"""id → (name, sound, syllables) for every language on the server."""
		return {language.id : (language.name, language.sound, language.syllables)
		        for language in LanguageTransactions().get_all(guild_id)}

	# ============================================================
	@staticmethod
	def lookup(guild_id: int) :
		"""A name → language id, 0 for the common language (and the word common), None when unknown."""
		common = LanguageFlow.common(guild_id)

		def find(name: str) :
			if name.lower() == "common" or (common is not None and name.lower() == common.name.lower()) :
				return 0
			language = LanguageTransactions().find(guild_id, name)
			if language is None :
				return None
			return 0 if language.common else language.id

		return find

	# ============================================================
	@staticmethod
	def known(character: Characters) -> dict[int, str] :
		"""What a character speaks, id → fluent or partial (species languages are fluent; common isn't listed)."""
		found = {}
		species = SpeciesTransactions().get(character.species_id) if character.species_id else None
		for language_id in (species.language_ids or []) if species else [] :
			found[int(language_id)] = FLUENT
		for entry in LanguageTransactions().known(character.id) :
			if found.get(entry.language_id) != FLUENT :
				found[entry.language_id] = entry.fluency
		return found

	# ============================================================
	@staticmethod
	def reader_fluency(guild_id: int, uid: int) -> dict[int, str] :
		"""The best a member's approved characters know each language."""
		found = {}
		for character in CharacterTransactions().get_all(uid, guild_id, states=[APPROVED]) :
			for language_id, fluency in LanguageFlow.known(character).items() :
				if found.get(language_id) != FLUENT :
					found[language_id] = fluency
		return found

	# ============================================================
	@staticmethod
	def slots(character: Characters) -> tuple[int, int] :
		"""(starting languages picked, starting languages allowed)."""
		allowed = Languages.starting_slots(RoleplaySettings.number(character.guild_id, ConfigMapping.LANGUAGE_SLOTS),
		                                   character.intelligence, Special.rules(character.guild_id).base)
		used = sum(entry.source == START for entry in LanguageTransactions().known(character.id))
		return used, allowed

	# ============================================================
	@staticmethod
	def mode(guild_id: int) -> str :
		return RoleplaySettings.text(guild_id, ConfigMapping.LANGUAGE_SCRAMBLE)

	# == posts ==

	# ============================================================
	@staticmethod
	def prepare(character: Characters, text: str) -> tuple[str, list[Segment] | None, str | None] :
		"""Turns what a member wrote into what is posted.

		@return: the text to post, the segments when any part is in a language (else None), and why it can't be
		posted (a language that doesn't exist or the character doesn't speak), or None.
		"""
		default = character.speaking_language_id
		if "{" not in text and not default :
			return text, None, None
		guild_id = character.guild_id
		if default and LanguageTransactions().get(default) is None :
			default = None
		segments, unknown = Languages.split(text, LanguageFlow.lookup(guild_id), default)
		if unknown :
			return text, None, f"There is no language called {', '.join(unknown)} on this server."
		known = LanguageFlow.known(character)
		missing = {segment.language for segment in segments if segment.language and segment.language not in known}
		if missing :
			names = ", ".join(LanguageTransactions().get(language_id).name for language_id in missing)
			return text, None, f"{character.name} doesn't speak {names}."
		if not Languages.has_language(segments) :
			return Languages.plain(segments), None, None
		posted = Languages.render(segments, LanguageFlow.table(guild_id), None, LanguageFlow.mode(guild_id))
		return posted, segments, None

	# ============================================================
	@staticmethod
	def save(first_message_id: int, character: Characters, segments: list[Segment]) -> None :
		LanguageTransactions().save_post(first_message_id, character.id, Languages.to_json(segments))

	# ============================================================
	@staticmethod
	def segments_of(message_id: int) -> list[Segment] | None :
		entry = ProxyTransactions().get(message_id)
		first = entry.first_message_id if entry is not None else message_id
		post = LanguageTransactions().post(first)
		segments = Languages.from_json(post.segments) if post is not None else []
		return segments if Languages.has_language(segments) else None

	# ============================================================
	@staticmethod
	def understand_text(guild_id: int, member, message_id: int) -> str :
		"""What the Understand button tells a member about a post."""
		segments = LanguageFlow.segments_of(message_id)
		if segments is None :
			return "That post isn't in another language."
		table = LanguageFlow.table(guild_id)
		from classes.kernel.GMRole import is_gm

		staff = is_gm(member)
		fluency = LanguageFlow.reader_fluency(guild_id, member.id)
		used = {segment.language for segment in segments if segment.language}
		if not staff and not any(language in fluency for language in used) :
			names = ", ".join(table.get(language, ("?",))[0] for language in used)
			return f"None of your characters speak {names}."
		text = Languages.render(segments, table, fluency, LanguageFlow.mode(guild_id), everything=staff)
		partly = [table[language][0] for language in used if fluency.get(language) == PARTIAL and not staff]
		note = f"\n-# You only partly understand {', '.join(partly)}." if partly else ""
		return f"🗣 {text}"[:1900] + note

	# ============================================================
	@staticmethod
	def chronicle_text(first_message_id: int) -> str | None :
		post = LanguageTransactions().post(first_message_id)
		if post is None :
			return None
		character = CharacterTransactions().get_by_id(post.character_id) if post.character_id else None
		table = LanguageFlow.table(character.guild_id) if character else {}
		return Languages.marked(Languages.from_json(post.segments), table)

	# ============================================================
	@staticmethod
	def edit_text(message_id: int, guild_id: int) -> str | None :
		"""A language post as the member wrote it, with `{Language}` markers, for editing."""
		segments = LanguageFlow.segments_of(message_id)
		if segments is None :
			return None
		return Languages.marked(segments, LanguageFlow.table(guild_id), guillemets=False)

	# ============================================================
	@staticmethod
	def letter_text(guild_id: int, language_id: int | None, text: str, reader: Characters | None) -> str :
		"""A letter's text as its reader's character understands it."""
		if not language_id :
			return text
		language = LanguageTransactions().get(language_id)
		if language is None or language.common :
			return text
		fluency = LanguageFlow.known(reader) if reader is not None else {}
		return Languages.render([Segment(language_id, text)], LanguageFlow.table(guild_id), fluency, Languages.ALL)


class UnderstandButton(discord.ui.DynamicItem[discord.ui.Button], template=r"lang:understand") :
	"""Under a post made in a language: tells the member what it says, as far as their characters understand."""

	def __init__(self, label: str = "Understand") :
		super().__init__(discord.ui.Button(label=label[:80], style=discord.ButtonStyle.secondary, emoji="🗣️",
		                                   custom_id="lang:understand"))

	# ============================================================
	@classmethod
	async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match) :
		return cls()

	# ============================================================
	async def callback(self, interaction: discord.Interaction) :
		await interaction.response.send_message(
			LanguageFlow.understand_text(interaction.guild_id, interaction.user, interaction.message.id),
			ephemeral=True)


# ============================================================
def understand_view(segments: list[Segment], guild_id: int) -> discord.ui.View :
	table = LanguageFlow.table(guild_id)
	names = sorted({table.get(segment.language, ("?",))[0] for segment in segments if segment.language})
	view = discord.ui.View(timeout=None)
	view.add_item(UnderstandButton(f"Understand ({', '.join(names)})"))
	return view
