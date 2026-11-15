"""Reading a character sheet a player wrote somewhere else and pasted into the interview in one message.

Sheets copied from character sites, documents or old forum posts mostly look alike: `Label: value` lines, sometimes
with a heading on its own line and an answer of several paragraphs under it. This module finds those labels, matches
them to the server's questions (and to the questions the interview asks itself: name, proxy, species, occupation) and
hands back what it found. It does not check the answers against the server's rules; the interview does that.

It also writes the blank template a player can copy, fill in and paste back.
"""
import re
from dataclasses import dataclass

from classes.characters.Sheet import CHOICE, INFO, LONG, NUMBER, SHORT, Sheet
from database.database import SheetFields

# What an entry can stand for, besides a sheet question (("field", id)). None means a label the server does not ask.
FIELD = "field"
NAME = "name"
PROXY = "proxy"
PREFIX = "prefix"
SUFFIX = "suffix"
SPECIES = "species"
OCCUPATION = "occupation"

BUILTIN_LABELS = {
	NAME       : ["name", "character name", "full name"],
	PROXY      : ["proxy", "proxy tag", "proxy tags", "trigger", "brackets"],
	PREFIX     : ["prefix"],
	SUFFIX     : ["suffix"],
	SPECIES    : ["species", "race"],
	OCCUPATION : ["occupation", "job", "profession"],
}

# Other words players use for the default sheet's questions. A synonym only counts when the server's sheet has a
# question it leads to.
SYNONYMS = {
	"backstory"          : "history",
	"background"         : "history",
	"bio"                : "history",
	"biography"          : "history",
	"appearance"         : "physical description",
	"looks"              : "physical description",
	"description"        : "physical description",
	"clothing"           : "apparel",
	"clothes"            : "apparel",
	"outfit"             : "apparel",
	"attire"             : "apparel",
	"sexuality"          : "sexual orientation",
	"gender identity"    : "gender representation",
	"nickname"           : "known alias",
	"alias"              : "known alias",
	"hobbies"            : "interests",
	"traits"             : "personality",
	"personality traits" : "personality",
	"faith"              : "religion",
	"powers"             : "abilities",
	"spells"             : "magics",
}

# Answers that mean "nothing written here", as left behind in a template.
EMPTY_VALUES = {"", "-", "--", "—", "–", "n/a", "na", "tbd", "tba", "?", "..."}

# How many questions a message has to answer before it is read as a pasted sheet.
SHEET_THRESHOLD = 2

# Labels the sheet does not ask become extra fields only when they look like a label and not like a sentence.
UNKNOWN_LABEL_WORDS = 4
UNKNOWN_LABEL_LENGTH = 40

# Bullets and markup a line can start with before its label.
_DECORATION = "*_~`#>•●▪◦◆◇❖✦✧★☆♦♥♡|·-–—=+ \t"
_HEADING_MARKUP = re.compile(r"^(#{1,6}\s+|={2,}\s*|\[\s*)(.*?)(\s*={2,}|\s*\])?$")
_WRAPPED = re.compile(r"^(\*\*|__)+(.+?)(\*\*|__)+$")
_DIVIDER = re.compile(r"^[\W_]{3,}$")
_NUMBER = re.compile(r"^(-?\d+)(?!\w)")
_TEMPLATE_CHUNK = 1900


@dataclass
class Entry :
	"""One label from the pasted text and the answer under it."""
	label: str
	target: tuple | None
	value: str = ""
	formatted: bool = False


# ============================================================
def _words(label: str) -> tuple[str, ...] :
	"""A label reduced to its words, lowercase, without brackets, markup or plurals: `Fears (up to 3)*` is
	('fear',)."""
	label = re.sub(r"\([^)]*\)|\[[^]]*]", " ", label).lower().replace("&", " and ")
	words = re.sub(r"[\W_]+", " ", label).split()
	return tuple(word[:-1] if len(word) > 3 and word.endswith("s") else word for word in words)


class Matcher :
	"""Matches labels to the questions a server asks."""

	def __init__(self, fields: list[SheetFields], builtins: set[str]) :
		self.fields = [sheet_field for sheet_field in fields if sheet_field.type != INFO]
		self.sections = {_words(sheet_field.section) for sheet_field in fields if sheet_field.section}
		# (words, target), sheet questions first so they win over the interview's own questions.
		self.names: list[tuple[tuple, tuple]] = []
		self.alternates: list[tuple[tuple, tuple]] = []
		for sheet_field in self.fields :
			target = (FIELD, sheet_field.id)
			self.names.append((_words(sheet_field.label), target))
			parts = [part for part in re.split(r"[/,]| or | and ", sheet_field.label) if part.strip()]
			if len(parts) > 1 :
				self.alternates += [(_words(part), target) for part in parts]
		for builtin, labels in BUILTIN_LABELS.items() :
			if builtin in builtins :
				self.names += [(_words(label), (builtin,)) for label in labels]
		self.long_targets = {(FIELD, sheet_field.id) for sheet_field in self.fields if sheet_field.type == LONG}

	# ============================================================
	def _unique(self, candidates: list[tuple]) -> tuple | None :
		targets = list(dict.fromkeys(candidates))
		return targets[0] if len(targets) == 1 else None

	# ============================================================
	def match(self, label: str) -> tuple | None :
		"""The question a label stands for, or None."""
		words = _words(label)
		if not words or len(words) > 8 :
			return None
		for candidate in (words, _words(SYNONYMS.get(" ".join(words), ""))) :
			if not candidate :
				continue
			exact = next((target for name, target in self.names if name == candidate), None)
			if exact is not None :
				return exact
			found = self._unique([target for name, target in self.alternates if name == candidate])
			if found is not None :
				return found
		# `Gender` for `Gender representation`, `Skills` for `Non-combat skills`: every word of the label appears in
		# exactly one question.
		return self._unique([target for name, target in self.names
		                     if target[0] == FIELD and set(words) <= set(name) and len(name) > len(words)])

	# ============================================================
	def is_section(self, label: str) -> bool :
		return _words(label) in self.sections


# ============================================================
def _split_label(line: str) -> tuple[str, str] | None :
	"""Splits `Label: value` at the first colon outside brackets; None when the line has no such colon."""
	depth = 0
	for index, character in enumerate(line) :
		if character in "([{" :
			depth += 1
		elif character in ")]}" :
			depth = max(0, depth - 1)
		elif character in ":：" and depth == 0 :
			return line[:index], line[index + 1 :]
	return None


# ============================================================
def _clean_label(raw: str) -> str :
	label = raw.strip().strip(_DECORATION).strip()
	# A template's hint in brackets and its required mark: `Age* (a number, at least 18)` is `Age`.
	label = re.sub(r"\s*\([^)]*\)\s*$", "", label)
	return re.sub(r"\s*\*+$", "", label).strip()


# ============================================================
def _clean_value(value: str) -> str :
	"""Takes the markup off an answer that the label's markup was wrapped around: `**Name:** Aria`."""
	value = re.sub(r"^[*_]+\s*", "", value.strip())
	for markup in ("**", "__") :
		if value.endswith(markup) and value.count(markup) % 2 == 1 :
			value = value[: -len(markup)].rstrip()
	return value


# ============================================================
def _label_like(label: str) -> bool :
	"""Whether text before a colon reads like a label of its own: short, with letters, and not a sentence."""
	return (0 < len(label) <= UNKNOWN_LABEL_LENGTH and len(label.split()) <= UNKNOWN_LABEL_WORDS
	        and re.search(r"[^\W\d_]", label) is not None and not re.search(r"[.!?,;\"“”]", label))


# ============================================================
def _heading(line: str) -> str | None :
	"""The text of a line that is a heading on its own: `# History`, `**History**`, `== History ==`, `HISTORY`."""
	match = _HEADING_MARKUP.match(line)
	if match and match.group(1).strip() and match.group(2).strip() :
		return _clean_label(match.group(2))
	match = _WRAPPED.match(line)
	if match :
		return _clean_label(match.group(2))
	letters = re.sub(r"[^\w\s]", "", line).strip()
	if letters and letters.upper() == letters and re.search(r"[A-Z]", letters) and len(letters.split()) <= 5 :
		return _clean_label(line)
	return None


# ============================================================
def parse(text: str, fields: list[SheetFields], builtins: set[str]) -> list[Entry] :
	"""Reads the labels and answers out of a pasted sheet.

	fields are the server's sheet fields; builtins the interview's own questions that can be answered here (NAME,
	PROXY, PREFIX, SUFFIX, SPECIES, OCCUPATION). A label asked twice keeps its last answer.
	"""
	matcher = Matcher(fields, builtins)
	entries: list[Entry] = []
	current: Entry | None = None
	lines: list[str] = []

	def close() :
		nonlocal current, lines
		if current is not None :
			value = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
			current.value = "" if value.lower() in EMPTY_VALUES else value
			entries.append(current)
		current, lines = None, []

	for raw_line in (text or "").splitlines() :
		line = raw_line.strip()
		if not line :
			if current is not None :
				lines.append("")
			continue
		if _DIVIDER.match(line) :
			close()
			continue
		# Inside a long answer that already runs over several lines, `Word: more words` is more likely part of the
		# answer than a label of its own; a one-line long answer is still followed by the next label.
		written = [part for part in lines if part]
		within_long = current is not None and current.target in matcher.long_targets 		              and (len(written) > 1 or (bool(written) and not lines[0]))

		split = _split_label(line)
		if split is None :
			# `Weight - 130lbs`: a dash or equals sign separates a label only when the label is one the server asks.
			dashed = re.match(r"^(.{1,60}?)\s+[-–—=]\s+(.+)$", line)
			if dashed and matcher.match(_clean_label(dashed.group(1))) is not None :
				split = (dashed.group(1), dashed.group(2))
		if split is not None and not split[1].startswith("//") :
			raw_label, value = split
			label = _clean_label(raw_label)
			formatted = any(markup in raw_label for markup in ("**", "__", "#"))
			target = matcher.match(label)
			if target is not None or (_label_like(label) and (formatted or not within_long)
			                          and not matcher.is_section(label)) :
				close()
				current, lines = Entry(label, target, formatted=formatted), [_clean_value(value)]
				continue
			if matcher.is_section(label) and not value.strip() :
				close()
				continue

		heading = _heading(line) if split is None else None
		if heading is not None :
			target = matcher.match(heading)
			if target is not None :
				close()
				current, lines = Entry(heading, target, formatted=True), [""]
				continue
			if matcher.is_section(heading) or not _label_like(heading) :
				close()
				continue
			if not within_long or line.startswith(("#", "*", "_", "=")) :
				close()
				current, lines = Entry(heading, None, formatted=True), [""]
				continue

		if current is not None :
			lines.append(line)
	close()

	merged: dict = {}
	for entry in entries :
		key = entry.target if entry.target is not None else ("extra", entry.label.lower())
		merged.pop(key, None)
		merged[key] = entry
	return list(merged.values())


# ============================================================
def is_sheet(entries: list[Entry], threshold: int = SHEET_THRESHOLD) -> bool :
	"""Whether the message answers enough of the server's questions to be read as a pasted sheet."""
	return len({entry.target for entry in entries if entry.target is not None}) >= threshold


# ============================================================
def coerce(sheet_field: SheetFields, value: str) -> tuple[str | None, str | None] :
	"""Checks a pasted answer to a sheet question, after making allowances for how sheets are written elsewhere:
	`24 years old` for a number, `Melee fighter` for the option Melee, line breaks in a short answer."""
	value = value.strip()
	if sheet_field.type == NUMBER :
		match = _NUMBER.match(value)
		if match :
			value = match.group(1)
	elif sheet_field.type == CHOICE :
		choices = sheet_field.choices or []
		if not any(choice.lower() == value.lower() for choice in choices) :
			found = [choice for choice in choices
			         if re.search(rf"(?<!\w){re.escape(choice.lower())}(?!\w)", value.lower())]
			if len(found) == 1 :
				value = found[0]
	elif sheet_field.type == SHORT :
		value = " ".join(value.split())
	return Sheet.check(sheet_field, value)


# ============================================================
def template(fields: list[SheetFields], builtins: set[str]) -> list[str] :
	"""A blank sheet to copy and fill in, as code blocks that each fit in a Discord message.

	Required questions are marked with `*`; hints go in brackets, which reading the sheet back ignores.
	"""
	head = ["Name*:", "Proxy* (put the word text where your message goes, like [text] or Aria: text):"]
	if SPECIES in builtins :
		head.append("Species*:")
	if OCCUPATION in builtins :
		head.append("Occupation:")
	blocks = [head]
	section = None
	for sheet_field in fields :
		if sheet_field.type == INFO :
			continue
		if sheet_field.section != section or len(blocks) == 1 :
			section = sheet_field.section
			blocks.append([f"== {section} ==" if section else "== Other =="])
		hint = []
		if sheet_field.type == CHOICE :
			hint.append(" / ".join(sheet_field.choices or []))
		elif sheet_field.type == NUMBER :
			if sheet_field.min_value is not None and sheet_field.max_value is not None :
				hint.append(f"a number from {sheet_field.min_value} to {sheet_field.max_value}")
			elif sheet_field.min_value is not None :
				hint.append(f"a number, at least {sheet_field.min_value}")
			elif sheet_field.max_value is not None :
				hint.append(f"a number, at most {sheet_field.max_value}")
			else :
				hint.append("a number")
		label = sheet_field.label + ("*" if sheet_field.required else "")
		line = f"{label} ({'; '.join(hint)}):" if hint else f"{label}:"
		blocks[-1].append(line)

	chunks, current = [], ""
	for block in blocks :
		text = "\n".join(block)
		if current and len(current) + len(text) + 2 > _TEMPLATE_CHUNK - 8 :
			chunks.append(current)
			current = ""
		current = f"{current}\n\n{text}" if current else text
	if current :
		chunks.append(current)
	return [f"```\n{chunk[: _TEMPLATE_CHUNK - 8]}\n```" for chunk in chunks]
