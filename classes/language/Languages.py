"""The rules of languages (design/roleplay-tools.md, section 1): reading `{Elvish}` markers, scrambling, partial
understanding and the text each reader sees. No Discord or database here.

A post is split into segments, each in a language (None is the common one). `{Elvish}` switches to that language
for the rest of the post, `{}` switches back to the default (the character's /language speak language, or common).
Scrambling is word by word and deterministic per language, so the same word always comes out the same and players
can learn to recognise words; word length, capitals, punctuation, mentions, links and emoji are kept. In `speech`
mode only quoted text is scrambled, so the narration stays readable.
"""
import hashlib
import random
import re
from dataclasses import dataclass

FLUENT = "fluent"
PARTIAL = "partial"
SPEECH = "speech"
ALL = "all"

SOUNDS = {
	"flowing" : ["ae", "el", "ith", "ri", "on", "la", "sil", "va", "lor", "ien", "tha", "mir", "nae", "yr"],
	"harsh" : ["gr", "uk", "dak", "zug", "kr", "ga", "rok", "thar", "mog", "bru", "ka", "drek", "ug"],
	"clipped" : ["ka", "ti", "po", "ne", "ru", "sa", "mi", "to", "ke", "na", "ho", "ji"],
	"sibilant" : ["ss", "ith", "sa", "zh", "sis", "ess", "ash", "ys", "sha", "is", "xa"],
	"runes" : list("ᚠᚢᚦᚨᚱᚲᚷᚹᚺᚾᛁᛃᛇᛈᛉᛊᛏᛒᛖᛗᛚᛜᛞᛟ"),
	"glyphs" : list("⟟⏃⌇⟒⍜⊑⋏⟊⏁⍀⎍⌰⟟⋔⏚☊⎅"),
}
# Sounds whose pieces are single symbols: every letter becomes one symbol.
SYMBOL_SOUNDS = {"runes", "glyphs"}
MARKER = re.compile(r"\{([^{}\n]{0,50})\}")
QUOTES = re.compile(r"\"[^\"\n]*\"|“[^”\n]*”|«[^»\n]*»")
# Things scrambling never touches: mentions, channels, roles, custom emoji, links and inline code.
KEEP = re.compile(r"<[@#][!&]?\d+>|<a?:\w+:\d+>|https?://\S+|`[^`]*`")
WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*", re.UNICODE)


@dataclass
class Segment :
	language: int | None
	text: str


# ============================================================
def seeded(*parts) -> random.Random :
	digest = hashlib.sha256("␟".join(str(part) for part in parts).encode("utf-8")).hexdigest()
	return random.Random(int(digest[:16], 16))


# ============================================================
def pieces(sound: str | None, syllables: list[str] | None = None) -> list[str] :
	if syllables :
		return [piece for piece in syllables if piece] or SOUNDS["flowing"]
	return SOUNDS.get(sound or "flowing", SOUNDS["flowing"])


# ============================================================
def scramble_word(word: str, language_id: int, sound: str | None, syllables: list[str] | None = None) -> str :
	"""One word in the language: the same length, with the original's capitals."""
	rng = seeded(language_id, word.lower())
	options = pieces(sound, syllables)
	letters = [character for character in word if character != "'"]
	if sound in SYMBOL_SOUNDS and not syllables :
		made = "".join(rng.choice(options) for _ in letters)
	else :
		made = ""
		while len(made) < len(letters) :
			made += rng.choice(options)
		made = made[:len(letters)]
		if word.isupper() and len(word) > 1 :
			made = made.upper()
		elif word[0].isupper() :
			made = made[0].upper() + made[1 :]
	# Put the apostrophes back where they were.
	result, index = [], 0
	for character in word :
		if character == "'" :
			result.append("'")
		else :
			result.append(made[index] if index < len(made) else "")
			index += 1
	return "".join(result)


# ============================================================
def _map_words(text: str, change) -> str :
	"""Applies change to every word outside mentions, links, emoji and code."""
	out, last = [], 0
	for kept in KEEP.finditer(text) :
		out.append(WORD.sub(lambda match : change(match.group(0)), text[last :kept.start()]))
		out.append(kept.group(0))
		last = kept.end()
	out.append(WORD.sub(lambda match : change(match.group(0)), text[last :]))
	return "".join(out)


# ============================================================
def scramble(text: str, language_id: int, sound: str | None, syllables: list[str] | None = None,
             mode: str = SPEECH) -> str :
	"""A segment as readers who don't know the language see it."""

	def change(word: str) -> str :
		return scramble_word(word, language_id, sound, syllables)

	if mode == ALL :
		return _map_words(text, change)
	return QUOTES.sub(lambda match : _map_words(match.group(0), change), text)


# ============================================================
def understood(word: str, language_id: int) -> bool :
	"""Whether a reader who knows the language partly understands a word (about half of them, always the same)."""
	return seeded("partial", language_id, word.lower()).random() < 0.5


# ============================================================
def partial(text: str, language_id: int, sound: str | None, syllables: list[str] | None = None,
            mode: str = SPEECH) -> str :
	"""A segment as a reader who knows the language partly sees it."""

	def change(word: str) -> str :
		return word if understood(word, language_id) else scramble_word(word, language_id, sound, syllables)

	if mode == ALL :
		return _map_words(text, change)
	return QUOTES.sub(lambda match : _map_words(match.group(0), change), text)


# ============================================================
def split(text: str, lookup, default: int | None = None) -> tuple[list[Segment], list[str]] :
	"""Splits a post at its `{Language}` markers.

	@param lookup: a language name → its id (0 for the common language), or None when there is no such language.
	@param default: the language before any marker and after `{}` (None is common).
	@return: the segments (empty ones dropped, the markers removed) and the names that aren't languages.
	"""
	segments, unknown = [], []
	current, last = default, 0
	for match in MARKER.finditer(text) :
		segments.append(Segment(current, text[last :match.start()]))
		name = match.group(1).strip()
		if not name :
			current = default
		else :
			found = lookup(name)
			if found is None :
				unknown.append(name)
			else :
				# 0 is the common language.
				current = found or None
		last = match.end()
	segments.append(Segment(current, text[last :]))
	merged = []
	for segment in segments :
		if not segment.text :
			continue
		if merged and merged[-1].language == segment.language :
			merged[-1] = Segment(segment.language, merged[-1].text + segment.text)
		else :
			merged.append(segment)
	return merged, unknown


# ============================================================
def has_language(segments: list[Segment]) -> bool :
	return any(segment.language is not None for segment in segments)


# ============================================================
def plain(segments: list[Segment]) -> str :
	return "".join(segment.text for segment in segments)


# ============================================================
def render(segments: list[Segment], languages: dict, fluency: dict[int, str] | None = None, mode: str = SPEECH,
           everything: bool = False) -> str :
	"""The text a reader sees.

	@param languages: id → (name, sound, syllables).
	@param fluency: the reader's languages, id → fluent or partial; None reads nothing but common.
	@param everything: staff and fluent readers of every language: the original text.
	"""
	fluency = fluency or {}
	parts = []
	for segment in segments :
		if segment.language is None or everything or fluency.get(segment.language) == FLUENT :
			parts.append(segment.text)
			continue
		_, sound, syllables = languages.get(segment.language, ("?", "flowing", None))
		if fluency.get(segment.language) == PARTIAL :
			parts.append(partial(segment.text, segment.language, sound, syllables, mode))
		else :
			parts.append(scramble(segment.text, segment.language, sound, syllables, mode))
	return "".join(parts)


# ============================================================
def marked(segments: list[Segment], languages: dict, guillemets: bool = True) -> str :
	"""The original text with the language of each part shown: `‹Elvish› text` (or `{Elvish}` markers to edit)."""
	parts = []
	for segment in segments :
		if segment.language is None :
			parts.append(("{common}" if not guillemets and parts else "") + segment.text)
			continue
		name = languages.get(segment.language, ("?",))[0]
		parts.append((f"‹{name}› " if guillemets else f"{{{name}}}") + segment.text)
	return "".join(parts)


# ============================================================
def to_json(segments: list[Segment]) -> list[dict] :
	return [{"language" : segment.language, "text" : segment.text} for segment in segments]


# ============================================================
def from_json(data: list[dict] | None) -> list[Segment] :
	return [Segment(entry.get("language"), entry.get("text") or "") for entry in data or []]


# ============================================================
def starting_slots(base: int, intelligence: int, stat_base: int = 5) -> int :
	"""Languages a new character picks besides common: the setting, plus 1 per 2 Intelligence above the base."""
	return max(0, base + max(0, (int(intelligence) - stat_base) // 2))
