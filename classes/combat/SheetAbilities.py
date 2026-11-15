"""Keeping abilities, spells and weapons inside the bot's own systems.

Sheets used to have free-text questions where players wrote their spells, abilities, weapon proficiencies and shield.
Those can't be resolved by the bot, so they are gone: abilities and spells are built from the effect catalog with
/ability, weapons come from the gear catalog (the shop or a GM), and proficiency is set with /gear proficiency.

This module knows which sheet labels belong to those systems (they can't be added as sheet questions or extra fields,
and old answers under them are hidden from cards), and turns old answers into blank abilities: one per name written,
linked to the character, with no effects until its owner builds it and staff approve it. Weapons can't be made from a
name, so their owners are told what to do instead.
"""
import logging
import re
from dataclasses import dataclass, field

import discord

from classes.combat import Abilities as AbilityRules
from classes.combat.Effects import NORMAL, STRONG, TIERS, WEAK
from database.database import Characters
from database.transactions.AbilityTransactions import AbilityTransactions, DRAFT
from database.transactions.CharacterInfoTransactions import CharacterInfoTransactions
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.SheetFieldTransactions import SheetFieldTransactions

# Words (singular, lowercase) that mark a label as belonging to the ability, spell or gear systems.
SPELL_LABELS = {("magic",), ("spell",), ("spellcasting",), ("cantrip",)}
ABILITY_LABELS = {("ability",), ("power",), ("superpower",), ("passive",), ("special", "ability"),
                  ("special", "move")}
WEAPON_LABELS = {("weapon", "proficiency"), ("weapon",), ("shield",), ("armament",)}
OTHER_LABELS = {("magic", "school"), ("combat", "note")}
RESERVED = SPELL_LABELS | ABILITY_LABELS | WEAPON_LABELS | OTHER_LABELS
# The default sheet's note about combat, which replaces the old combat notes.
NOTE_LABEL = "Combat"
# The suffix an old answer gets once it has been turned into blank abilities, so it is only handled once.
DONE_SUFFIX = " (old)"
MAX_NAMES = 12
NAME_LIMIT = 100
TEXT_LIMIT = 1000
EMPTY = {"", "-", "--", "none", "n/a", "na", "no", "nothing", "tbd", "tba", "?"}
_BULLET = re.compile(r"^[\s*•●▪◦◆◇❖✦✧★☆♦|·\-–—=+>#\d.)]+")
_CUT = re.compile(r"\s+[-–—:]\s+|:\s*|\s*\(")


# ============================================================
def words(label: str) -> tuple[str, ...] :
	"""A label reduced to its words, lowercase, without brackets or plurals: `Magics (max 6)` is ('magic',) and
	`Abilities` ('ability',)."""
	label = re.sub(r"\([^)]*\)|\[[^]]*]", " ", label or "").lower()
	found = re.sub(r"[\W_]+", " ", label).split()
	return tuple(word[:-3] + "y" if len(word) > 4 and word.endswith("ies")
	             else word[:-1] if len(word) > 3 and word.endswith("s") else word for word in found)


# ============================================================
def reserved(label: str) -> bool :
	"""Whether a sheet label belongs to the ability, spell or gear systems."""
	found = words(label)
	return bool(found) and (found in RESERVED or found[-1:] in RESERVED)


# ============================================================
def reserved_problem(label: str) -> str | None :
	"""Why a label can't be a sheet question or an extra field, or None."""
	if not reserved(label) :
		return None
	return (f"**{label}** belongs to the bot's own systems: abilities and spells are built with /ability create, "
	        f"weapons and shields come from the shop or a GM, and proficiency is set with /gear proficiency.")


# ============================================================
def paste_note(label: str, value: str) -> str :
	"""What the interview says about a pasted section the sheet can't hold, like a list of spells."""
	names = [name for name, _, _ in entries(value)]
	written = f" (you wrote: {', '.join(names)[:300]})" if names else ""
	if kind_of(label) == "weapon" :
		return (f"**{label}**{written}: weapons aren't written on the sheet. Get them from the shop or a GM once "
		        f"your character is approved, and set proficiency with /gear proficiency.")
	return (f"**{label}**{written}: spells and abilities aren't written on the sheet. Once your character is "
	        f"approved, build them from catalog effects with /ability create and learn them with /ability learn.")


# ============================================================
def kind_of(label: str) -> str | None :
	"""spell, ability or weapon for an old answer's label; None for the other reserved labels."""
	found = words(label)
	for kind, labels in (("weapon", WEAPON_LABELS), ("spell", SPELL_LABELS), ("ability", ABILITY_LABELS)) :
		if found in labels or found[-1:] in labels :
			return kind
	return None


# ============================================================
def entries(text: str) -> list[tuple[str, str, str]] :
	"""The names written in a free-text answer, as (name, tier, the line it came from). One per line, or split on
	commas and semicolons when the answer is a single line. The tier comes from a tier word on the line (Weak by
	default)."""
	lines = [line for line in (text or "").splitlines() if line.strip()]
	if len(lines) == 1 :
		lines = [part for part in re.split(r"[,;]", lines[0]) if part.strip()]
	found = []
	for line in lines :
		clean = _BULLET.sub("", line).strip().strip("*_`~ ")
		name = _CUT.split(clean, maxsplit=1)[0].strip().strip("*_`~ ").rstrip(".")
		if name.lower() in EMPTY or len(name) < 2 :
			continue
		lowered = line.lower()
		tier = next((tier for tier in (STRONG, NORMAL, WEAK, "cantrip") if tier in lowered), WEAK)
		found.append((name[:NAME_LIMIT], tier if tier in TIERS else WEAK, line.strip()[:TEXT_LIMIT]))
		if len(found) >= MAX_NAMES :
			break
	return found


@dataclass
class Report :
	"""What converting a server's old answers did."""
	removed_fields: list[str] = field(default_factory=list)
	characters: int = 0
	created: int = 0
	linked: int = 0
	weapons: int = 0
	unreached: list[str] = field(default_factory=list)

	# ============================================================
	def text(self) -> str :
		lines = []
		if self.removed_fields :
			lines.append(f"Removed from the sheet: {', '.join(self.removed_fields)}.")
		lines.append(f"Went through {self.characters} character{'s' if self.characters != 1 else ''} with old answers: "
		             f"{self.created} blank abilit{'ies' if self.created != 1 else 'y'} made, {self.linked} linked to "
		             f"abilities that already existed, {self.weapons} weapon list{'s' if self.weapons != 1 else ''} "
		             f"to sort out.")
		if self.unreached :
			lines.append(f"I could not DM {', '.join(self.unreached)}; please let them know.")
		return "\n".join(lines)


class SheetAbilities :

	# ============================================================
	@staticmethod
	def remove_fields(guild_id: int) -> list[str] :
		"""Removes the reserved questions from a server's sheet; their answers stay on characters as extra fields. The
		old combat notes are replaced by the default sheet's note, which points to /ability and the shop."""
		from classes.characters.Sheet import COMBAT_NOTES, INFO

		removed, notes_at = [], None
		for sheet_field in SheetFieldTransactions().get_all(guild_id) :
			if reserved(sheet_field.label) :
				if words(sheet_field.label) == ("combat", "note") :
					notes_at = sheet_field.position
				SheetFieldTransactions().remove(guild_id, sheet_field.label)
				removed.append(sheet_field.label)
		if notes_at is not None and SheetFieldTransactions().find(guild_id, NOTE_LABEL) is None :
			SheetFieldTransactions().add(guild_id, NOTE_LABEL, notes_at, section="Combat", type=INFO, required=False,
			                             help=COMBAT_NOTES)
		return removed

	# ============================================================
	@staticmethod
	def blank_ability(character: Characters, name: str, kind: str, tier: str, line: str) -> tuple[str, str] :
		"""Makes (or finds) the blank ability for one name and links it to the character.

		@return: (what happened: created, linked, exists or skipped, the ability's name)
		"""
		transactions = AbilityTransactions()
		existing = transactions.find(character.guild_id, name)
		if existing is not None and existing.state != DRAFT :
			return "exists", existing.name
		if existing is not None and existing.creator_uid == character.uid :
			transactions.learn(character.id, existing.id)
			return "linked", existing.name
		if existing is not None :
			name = f"{name[:NAME_LIMIT - len(character.name) - 3]} ({character.name})"
			if transactions.find(character.guild_id, name) is not None :
				return "skipped", name
		ability = transactions.add(character.guild_id, name, creator_uid=character.uid, kind=kind, tier=tier,
		                           stat="intelligence" if kind == AbilityRules.SPELL else "strength", effects=[],
		                           description=line, state=DRAFT)
		if ability is None :
			return "skipped", name
		transactions.learn(character.id, ability.id)
		return "created", ability.name

	# ============================================================
	@staticmethod
	def convert_character(character: Characters) -> tuple[list[str], list[str], int, int] :
		"""Turns one character's old answers into blank abilities and marks the answers as handled.

		@return: (lines for the owner's DM, weapon lines, abilities created, abilities linked)
		"""
		infos = CharacterInfoTransactions()
		notes, weapons, created, linked = [], [], 0, 0
		for info in infos.get_extras(character.id) :
			if not reserved(info.key) or info.key.endswith(DONE_SUFFIX) :
				continue
			kind = kind_of(info.key)
			if kind == "weapon" :
				weapons += [line for _, _, line in entries(info.value)]
			elif kind is not None :
				for name, tier, line in entries(info.value) :
					outcome, final = SheetAbilities.blank_ability(character, name, kind, tier, line)
					if outcome == "created" :
						created += 1
						notes.append(f"- **{final}**: a blank {tier.capitalize()} {kind}")
					elif outcome == "linked" :
						linked += 1
						notes.append(f"- **{final}**: your blank {kind}, now linked")
					elif outcome == "exists" :
						notes.append(f"- **{final}** already exists on the server; learn it with /ability learn if "
						             f"it fits")
			infos.rename(character.id, info.key, f"{info.key}{DONE_SUFFIX}")
		return notes, weapons, created, linked

	# ============================================================
	@staticmethod
	def message(character: Characters, guild_name: str, notes: list[str], weapons: list[str]) -> str :
		lines = [f"Abilities, spells and weapons on {guild_name} now come only from the bot's own systems, so the "
		         f"free-text ones on **{character.name}**'s sheet were turned into something the bot understands."]
		if notes :
			lines.append("\n**Abilities and spells**\n" + "\n".join(notes))
			lines.append("Blank abilities do nothing in fights yet. Build each one from catalog effects with "
			             "`/ability edit` (or `/ability passive_edit` for a passive), browse the effects with "
			             "`/ability effects`, and staff will review it. `/ability forget` drops the ones you don't "
			             "want.")
		if weapons :
			lines.append("\n**Weapons**\n" + "\n".join(f"- {line}" for line in weapons[:15]))
			lines.append("Weapons can't be made from a name. Buy them in the shop (or ask a GM), then set how good "
			             f"{character.name} is with each one using `/gear proficiency`.")
		return "\n".join(lines)

	# ============================================================
	@staticmethod
	async def convert(bot: discord.Client, guild: discord.Guild) -> Report :
		"""Removes the reserved sheet questions and turns every character's old answers into blank abilities, with a DM
		to each owner."""
		from classes.characters.CharacterFlow import CharacterFlow

		report = Report(removed_fields=SheetAbilities.remove_fields(guild.id))
		for character in CharacterTransactions().get_in_guild(guild.id) :
			notes, weapons, created, linked = SheetAbilities.convert_character(character)
			if not notes and not weapons :
				continue
			report.characters += 1
			report.created += created
			report.linked += linked
			report.weapons += 1 if weapons else 0
			member = guild.get_member(character.uid)
			try :
				user = member or await bot.fetch_user(character.uid)
			except discord.HTTPException :
				user = None
			text = SheetAbilities.message(character, guild.name, notes, weapons)
			if user is None or not await CharacterFlow.send_dm(user, text) :
				report.unreached.append(f"<@{character.uid}> ({character.name})")
		logging.info(f"Converted old sheet abilities in {guild.name}: {report.created} created, {report.linked} "
		             f"linked, {report.characters} characters")
		return report
