"""A server's character sheet: the default questions, and checking the answers players give."""
from classes.kernel.ConfigData import ConfigData
from database.database import SheetFields
from database.transactions.SheetFieldTransactions import SheetFieldTransactions

SHORT = "short"
LONG = "long"
NUMBER = "number"
CHOICE = "choice"
# Asks nothing; its help text is shown as a note between questions.
INFO = "info"
TYPES = [SHORT, LONG, NUMBER, CHOICE, INFO]

# The longest answer a field accepts when it has no max_length of its own, and the highest max_length it can be given.
DEFAULT_LENGTH = {SHORT : 200, LONG : 6000}
LENGTH_CAP = {SHORT : 1000, LONG : 10000}
MAX_CHOICES = 25
MAX_FIELDS = 60

# Config row that marks a server's sheet as set up, so an owner who empties the sheet does not get the default back.
SEEDED_KEY = "SHEET_SEEDED"

COMBAT_NOTES = (
	"Spells, abilities and weapons aren't written on the sheet. Once your character is approved:\n"
	"- build spells (magic effects, from a magic school) or abilities (physical effects) with /ability create, "
	"browse the effects with /ability effects, and learn them with /ability learn;\n"
	"- get weapons, armor and shields from the shop (or a GM) and set your weapon proficiency with /gear proficiency.\n"
	"Spellcasters know up to 6 spells; everyone else has 3 ability slots. A character can't have both unless an event "
	"grants them."
)


def _field(section: str, label: str, type: str = SHORT, required: bool = False, help: str | None = None,
           **limits) -> dict :
	return {"section" : section, "label" : label, "type" : type, "required" : required, "help" : help, **limits}


# The sheet new servers start with. Name, prefix/suffix, avatar and SPECIAL are asked by the interview itself.
DEFAULT_SHEET = [
	_field("Basic information", "Known alias", required=True),
	_field("Basic information", "Age", NUMBER, required=True, min_value=18),
	_field("Basic information", "Relationship status", required=True),
	_field("Basic information", "Sexual orientation", required=True),
	_field("Basic information", "Gender representation", required=True),
	_field("Appearance", "Height", required=True),
	_field("Appearance", "Weight", required=True),
	_field("Appearance", "Physical description", LONG, help="Optional if your avatar shows it."),
	_field("Appearance", "Apparel", LONG, required=True),
	_field("Appearance", "Voice"),
	_field("Appearance", "Distinguishing features", LONG, help="Tattoos, scars, etc."),
	_field("Personality", "Personality", LONG, help="You can use traits, or describe your character's personality."),
	_field("About", "Strengths", LONG, help="Up to 3."),
	_field("About", "Weaknesses", LONG, help="Up to 3."),
	_field("About", "Fears", LONG, help="Up to 3."),
	_field("About", "Non-combat skills", LONG, required=True, help="Max of 5."),
	_field("About", "Interests / quirks", LONG),
	_field("About", "Known associates", LONG),
	_field("About", "Religion"),
	_field("About", "Goals / ambitions", LONG, required=True),
	_field("About", "Past occupations", LONG),
	_field("Character history", "History", LONG),
	_field("Combat", "Combat", INFO, help=COMBAT_NOTES),
	_field("Combat", "Combat archetype", CHOICE, choices=["Spellcaster", "Melee", "Ranged"]),
	_field("Combat", "Armor proficiency", CHOICE, choices=["Unarmored", "Light", "Medium", "Heavy"]),
]


class Sheet :

	# ============================================================
	@staticmethod
	def ensure(guild_id: int) -> bool :
		"""Gives a server the default sheet the first time it is seen. The server must be in the servers table.

		@return: True when the default sheet was added.
		"""
		if ConfigData().get_guild(guild_id).get(SEEDED_KEY) :
			return False
		added = False
		if not SheetFieldTransactions().get_all(guild_id) :
			SheetFieldTransactions().add_many(guild_id, DEFAULT_SHEET)
			added = True
		ConfigData().add_key(guild_id, SEEDED_KEY, "yes", overwrite=True)
		return added

	# ============================================================
	@staticmethod
	def reset(guild_id: int) -> None :
		"""Replaces the server's sheet with the default one. Answers already given stay on the characters as extra
		fields."""
		SheetFieldTransactions().clear(guild_id)
		SheetFieldTransactions().add_many(guild_id, DEFAULT_SHEET)
		ConfigData().add_key(guild_id, SEEDED_KEY, "yes", overwrite=True)

	# ============================================================
	@staticmethod
	def questions(guild_id: int) -> list[SheetFields] :
		"""The fields that ask something, in order (info notes left out)."""
		return [field for field in SheetFieldTransactions().get_all(guild_id) if field.type != INFO]

	# ============================================================
	@staticmethod
	def max_length(field: SheetFields) -> int :
		return field.max_length or DEFAULT_LENGTH.get(field.type, DEFAULT_LENGTH[SHORT])

	# ============================================================
	@staticmethod
	def check(field: SheetFields, text: str) -> tuple[str | None, str | None] :
		"""Checks an answer to a question.

		@return: (the value to store, None) when it is fine, otherwise (None, why it was refused).
		"""
		text = (text or "").strip()
		if not text :
			return None, "That answer is empty."
		if field.type == NUMBER :
			try :
				number = int(text)
			except ValueError :
				return None, "Please answer with a whole number."
			if field.min_value is not None and number < field.min_value :
				return None, f"That has to be at least {field.min_value}."
			if field.max_value is not None and number > field.max_value :
				return None, f"That can be at most {field.max_value}."
			return str(number), None
		if field.type == CHOICE :
			choices = field.choices or []
			if text.isdigit() and 1 <= int(text) <= len(choices) :
				return choices[int(text) - 1], None
			match = next((choice for choice in choices if choice.lower() == text.lower()), None)
			if match is None :
				return None, "Please pick one of the options, by its number or its name."
			return match, None
		limit = Sheet.max_length(field)
		if len(text) > limit :
			return None, f"That is {len(text)} characters, but this answer can be at most {limit}."
		return text, None

	# ============================================================
	@staticmethod
	def describe(field: SheetFields) -> str :
		"""The question as it is asked in the interview."""
		lines = [f"**{field.label}**" + ("" if field.required or field.type == INFO else " (optional)")]
		if field.help :
			lines.append(field.help)
		if field.type == CHOICE :
			lines.extend(f"{number}. {choice}" for number, choice in enumerate(field.choices or [], start=1))
			lines.append("Answer with the number or the name of an option.")
		elif field.type == NUMBER :
			if field.min_value is not None and field.max_value is not None :
				lines.append(f"Answer with a whole number from {field.min_value} to {field.max_value}.")
			elif field.min_value is not None :
				lines.append(f"Answer with a whole number of at least {field.min_value}.")
			elif field.max_value is not None :
				lines.append(f"Answer with a whole number of at most {field.max_value}.")
			else :
				lines.append("Answer with a whole number.")
		return "\n".join(lines)

	# ============================================================
	@staticmethod
	def missing_required(guild_id: int, answers: dict) -> list[SheetFields] :
		"""The required questions that have no answer yet; answers is keyed by field id (int or str)."""
		answered = {str(key) for key, value in answers.items() if value not in (None, "")}
		return [field for field in Sheet.questions(guild_id) if field.required and str(field.id) not in answered]

	# ============================================================
	@staticmethod
	def validate_definition(type: str, max_length: int | None, min_value: int | None, max_value: int | None,
	                        choices: list[str] | None) -> str | None :
		"""Why a question cannot be saved like this, or None when it can."""
		if type not in TYPES :
			return f"The type has to be one of: {', '.join(TYPES)}."
		if type == CHOICE :
			if not choices or len(choices) < 2 :
				return "A choice question needs at least 2 options, separated by commas."
			if len(choices) > MAX_CHOICES :
				return f"A choice question can have at most {MAX_CHOICES} options."
			if len({choice.lower() for choice in choices}) != len(choices) :
				return "Every option has to be different."
		if max_length is not None :
			if type not in LENGTH_CAP :
				return "Only short and long text questions have a maximum length."
			if not 1 <= max_length <= LENGTH_CAP[type] :
				return f"The maximum length of a {type} text question has to be between 1 and {LENGTH_CAP[type]}."
		if (min_value is not None or max_value is not None) and type != NUMBER :
			return "Only number questions have a minimum and maximum."
		if min_value is not None and max_value is not None and min_value > max_value :
			return "The minimum cannot be higher than the maximum."
		return None
