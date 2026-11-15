"""Turns a character into the embeds shown on its profile, its review card and its post in the character forum."""
import discord

from classes.characters.Special import STATS, Special
from classes.gear.Gear import ARMOR, Gear
from classes.kernel.ConfigData import ConfigData
from database.database import CharacterInfo, Characters, SheetFields
from database.transactions.CharacterInfoTransactions import CharacterInfoTransactions
from database.transactions.CharacterTransactions import APPROVED, DEAD, DENIED, PENDING, RETIRED
from database.transactions.OccupationTransactions import OccupationTransactions
from database.transactions.SheetFieldTransactions import SheetFieldTransactions
from database.transactions.SpeciesTransactions import SpeciesTransactions
from resources.configs.ConfigMapping import ConfigMapping

# An embed's description can hold 4096 characters and a whole embed 6000; this leaves room for the title and fields.
DESCRIPTION_LIMIT = 4000
MESSAGE_LIMIT = 2000
FIELD_LIMIT = 1024
# Answers longer than this get their own lines instead of sharing a line with their label.
INLINE_ANSWER = 80

STATE_LABELS = {PENDING : "Waiting for review", APPROVED : "Approved", DENIED : "Denied", RETIRED : "Retired",
                DEAD : "Dead"}
STATE_COLORS = {PENDING : discord.Color.gold(), APPROVED : discord.Color.green(), DENIED : discord.Color.red(),
                RETIRED : discord.Color.light_grey(), DEAD : discord.Color.darker_grey()}


# ============================================================
def chunk_text(text: str, limit: int) -> list[str] :
	"""Splits text into pieces of at most limit characters, breaking between lines where it can.

	A line too long for one piece is cut, preferably at a space; its first part fills up the piece before it, so a
	short first line (such as a reply line) stays with the text after it.
	"""
	chunks, current = [], ""
	for line in text.split("\n") :
		while len(line) > limit :
			room = limit - (len(current) + 1 if current else 0)
			if room < limit // 4 :
				chunks.append(current)
				current, room = "", limit
			cut = line.rfind(" ", 0, room)
			cut = cut if cut > room // 2 else room
			chunks.append(f"{current}\n{line[:cut]}" if current else line[:cut])
			current = ""
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
		from classes.combat.SheetAbilities import reserved

		sections = {field.id : field.section for field in fields}
		# Spells, abilities and weapons come from the bot's own systems; old free-text answers about them stay hidden.
		infos = [info for info in infos if not reserved(info.key)]
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
	def gear_text(character: Characters) -> str :
		"""The gear the character carries, one item per line, worn and equipped items first.

		Each line notes what is worn or equipped and the SPECIAL requirements the character does not meet, like
		`Plate (worn; needs Strength 8)`. Lines that do not fit in one embed field become `…and 3 more`.
		"""
		stats = Gear.stats_of(character)
		lines = []
		for entry, item in sorted(Gear.inventory(character.id), key=lambda pair : not pair[0].equipped) :
			notes = []
			if entry.equipped :
				notes.append("worn" if entry.kind == ARMOR else "equipped")
			unmet = Gear.unmet_requirements(stats, item) if item is not None else []
			if unmet :
				notes.append(f"needs {', '.join(unmet)}")
			lines.append(f"{entry.name} ({'; '.join(notes)})" if notes else entry.name)
		shown = []
		for number, line in enumerate(lines) :
			rest = len(lines) - number - 1
			more = f"\n…and {rest} more" if rest else ""
			if len("\n".join(shown + [line]) + more) > FIELD_LIMIT :
				return "\n".join(shown + [f"…and {len(lines) - number} more"])
			shown.append(line)
		return "\n".join(shown)

	# ============================================================
	@staticmethod
	def abilities_text(character: Characters) -> str :
		"""The abilities the character knows, one per line, like `Firebolt (Weak spell)` or `Iron Skin (Normal
		passive)`."""
		from database.transactions.AbilityTransactions import AbilityTransactions

		lines = []
		for link, ability in AbilityTransactions().known(character.id) :
			note = " · event" if link.event else ("" if ability.state == "approved" else " · blank" if ability.state == "draft" else f" · {ability.state}")
			kind = "passive" if ability.activation == "passive" else ability.kind
			lines.append(f"{ability.name} ({ability.tier.capitalize()} {kind}{note})")
		return "\n".join(lines)[:1024]

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

		legendary = bool(getattr(character, "legendary", False))
		title = f"🌟 {character.name}" if legendary else character.name
		first = discord.Embed(title=title[:256], description=chunks[0] or None, color=color)
		if avatar_url :
			first.set_thumbnail(url=avatar_url)
		first.add_field(name="SPECIAL", value=Card.stats_text(character), inline=False)
		first.add_field(name="Level", value=f"{character.level} ({character.xp} XP)"
		                                    + (" · Legendary" if legendary else ""))
		if character.unspent_points :
			first.add_field(name="Unspent points", value=str(character.unspent_points))
		currency_name = ConfigData().get_key(character.guild_id, ConfigMapping.CURRENCY_NAME)
		first.add_field(name=str(currency_name).capitalize(), value=str(character.currency))
		species = SpeciesTransactions().get(character.species_id)
		if species is not None :
			first.add_field(name="Species", value=species.name)
		occupation = OccupationTransactions().get(character.occupation_id)
		if occupation is not None :
			first.add_field(name="Occupation", value=occupation.name)
		first.add_field(name="Speaks with", value=Card.trigger_text(character.prefix, character.suffix))
		gear = Card.gear_text(character)
		if gear :
			first.add_field(name="Gear", value=gear, inline=False)
		abilities = Card.abilities_text(character)
		if abilities :
			first.add_field(name="Abilities", value=abilities, inline=False)
		if show_state :
			first.set_footer(text=STATE_LABELS.get(character.state, character.state))

		embeds = [first]
		for chunk in chunks[1 :] :
			embeds.append(discord.Embed(description=chunk, color=color))
		return embeds
