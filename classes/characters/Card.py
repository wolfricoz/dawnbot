"""Turns a character into the embeds shown on its profile, its review card and its post in the character forum."""
import discord

from classes.characters.Special import STATS, Special
from classes.kernel.ConfigData import ConfigData
from database.database import CharacterInfo, Characters, SheetFields
from database.transactions.CharacterInfoTransactions import CharacterInfoTransactions
from database.transactions.CharacterTransactions import APPROVED, DENIED, PENDING, RETIRED
from database.transactions.SheetFieldTransactions import SheetFieldTransactions
from resources.configs.ConfigMapping import ConfigMapping

# An embed's description can hold 4096 characters and a whole embed 6000; this leaves room for the title and fields.
DESCRIPTION_LIMIT = 4000
MESSAGE_LIMIT = 2000
# Answers longer than this get their own lines instead of sharing a line with their label.
INLINE_ANSWER = 80

STATE_LABELS = {PENDING : "Waiting for review", APPROVED : "Approved", DENIED : "Denied", RETIRED : "Retired"}
STATE_COLORS = {PENDING : discord.Color.gold(), APPROVED : discord.Color.green(), DENIED : discord.Color.red(),
                RETIRED : discord.Color.light_grey()}


# ============================================================
def chunk_text(text: str, limit: int) -> list[str] :
	"""Splits text into pieces of at most limit characters, breaking between lines where it can."""
	chunks, current = [], ""
	for line in text.split("\n") :
		while len(line) > limit :
			# A single line that is too long is cut, preferably at a space.
			cut = line.rfind(" ", 0, limit)
			cut = cut if cut > limit // 2 else limit
			if current :
				chunks.append(current)
				current = ""
			chunks.append(line[:cut])
			line = line[cut :].lstrip()
		if current and len(current) + 1 + len(line) > limit :
			chunks.append(current)
			current = line
		else :
			current = f"{current}\n{line}" if current else line
	if current :
		chunks.append(current)
	return chunks or [""]


class Card :

	# ============================================================
	@staticmethod
	def trigger_text(prefix: str | None, suffix: str | None) -> str :
		"""How a message is written to speak as the character, e.g. `Aria: text`."""
		return f"`{prefix or ''}text{suffix or ''}`" if prefix or suffix else "none"

	# ============================================================
	@staticmethod
	def stats_text(character: Characters) -> str :
		return Special.summary({stat : getattr(character, stat) for stat in STATS})

	# ============================================================
	@staticmethod
	def sheet_text(infos: list[CharacterInfo], fields: list[SheetFields]) -> str :
		"""The character's answers and extra fields as text, grouped under the sheet's section headings."""
		sections = {field.id : field.section for field in fields}
		lines, current = [], None
		has_sections = any(sections.get(info.sheet_field_id) for info in infos)
		for info in infos :
			section = sections.get(info.sheet_field_id) if info.sheet_field_id else ("Other" if has_sections else None)
			if section and section != current :
				lines.append(f"\n**__{section}__**")
				current = section
			if len(info.value) > INLINE_ANSWER or "\n" in info.value :
				lines.append(f"**{info.key}**\n{info.value}")
			else :
				lines.append(f"**{info.key}:** {info.value}")
		return "\n".join(lines).strip()

	# ============================================================
	@staticmethod
	def embeds(character: Characters, avatar_url: str | None = None, show_state: bool = True,
	           infos: list[CharacterInfo] | None = None) -> list[discord.Embed] :
		"""The character as one or more embeds; a long sheet continues in further embeds, one per message."""
		if infos is None :
			infos = CharacterInfoTransactions().get_all(character.id)
		text = Card.sheet_text(infos, SheetFieldTransactions().get_all(character.guild_id))
		chunks = chunk_text(text, DESCRIPTION_LIMIT)
		color = STATE_COLORS.get(character.state, discord.Color.blurple())

		first = discord.Embed(title=character.name[:256], description=chunks[0] or None, color=color)
		if avatar_url :
			first.set_thumbnail(url=avatar_url)
		first.add_field(name="SPECIAL", value=Card.stats_text(character), inline=False)
		first.add_field(name="Level", value=f"{character.level} ({character.xp} XP)")
		if character.unspent_points :
			first.add_field(name="Unspent points", value=str(character.unspent_points))
		currency_name = ConfigData().get_key(character.guild_id, ConfigMapping.CURRENCY_NAME)
		first.add_field(name=str(currency_name).capitalize(), value=str(character.currency))
		first.add_field(name="Speaks with", value=Card.trigger_text(character.prefix, character.suffix))
		if show_state :
			first.set_footer(text=STATE_LABELS.get(character.state, character.state))

		embeds = [first]
		for chunk in chunks[1 :] :
			embeds.append(discord.Embed(description=chunk, color=color))
		return embeds
