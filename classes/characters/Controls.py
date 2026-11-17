"""The buttons and menus under each interview question: what a step offers, and what pressing one means.

Every control stands for something the player could also type, so the interviews only ever see text (see
Interview.answer and SpeciesInterview.answer): a button is a command such as `back` or `submit`, a menu option the
number or name of what it picks. Menus carry ids rather than numbers where the list can change between sending and
pressing (species, occupations, gear), and turn them into what the player would type at the moment of pressing.

This module holds no Discord code; views/buttons/InterviewControls.py turns it into a message's components.
"""
from dataclasses import dataclass, field

from classes.characters.Sheet import CHOICE

# Discord's limits: options in a menu, characters in a label, value or description, and rows in a message.
MENU_LIMIT = 25
TEXT_LIMIT = 100
ROW_LIMIT = 5

PRIMARY, SECONDARY, SUCCESS, DANGER = "primary", "secondary", "success", "danger"

# What pressing each button types.
TYPED = {"back" : "back", "skip" : "skip", "keep" : "skip", "cancel" : "cancel", "submit" : "submit", "buy" : "buy",
         "roll" : "roll", "done" : "done", "template" : "template"}

# The menu value that starts a new species from the species step.
NEW_SPECIES_VALUE = "+new"


@dataclass
class Option :
	label: str
	value: str
	description: str | None = None
	default: bool = False


@dataclass
class Menu :
	name: str
	placeholder: str
	options: list[Option]


@dataclass
class Button :
	action: str
	label: str
	style: str = SECONDARY


@dataclass
class Controls :
	kind: str
	step: str
	menus: list[Menu] = field(default_factory=list)
	buttons: list[Button] = field(default_factory=list)


# ============================================================
def clip(text, limit: int = TEXT_LIMIT) -> str :
	"""One line of at most limit characters."""
	text = " ".join(str(text or "").split())
	return text if len(text) <= limit else f"{text[:limit - 1]}…"


# ============================================================
def build(draft) -> Controls | None :
	"""The controls for the draft's current step, or None without a draft."""
	from classes.species.SpeciesInterview import KINDS as SPECIES_KINDS

	if draft is None or not isinstance(draft.answers, dict) :
		return None
	if draft.kind in SPECIES_KINDS :
		return _species_controls(draft)
	if "queue" not in draft.answers :
		return None
	return _character_controls(draft)


# ============================================================
def resolve(draft, kind: str, step: str, action: str | None = None, menu: str | None = None,
            value: str | None = None) -> tuple[str, str] | None :
	"""What a press types, with a short echo of what was picked, or None when the control is out of date: the draft
	moved on to another question, or the option is no longer offered."""
	controls = build(draft)
	if controls is None or controls.kind != kind or controls.step != step :
		return None
	if action is not None :
		button = next((button for button in controls.buttons if button.action == action), None)
		if button is None or action not in TYPED :
			return None
		return TYPED[action], button.label
	chosen = next((option for each in controls.menus if each.name == menu for option in each.options
	               if option.value == value), None)
	if chosen is None :
		return None
	text = _typed(draft, menu, value)
	return (text, chosen.label) if text is not None else None


# == character interview ==

# ============================================================
def _character_controls(draft) -> Controls :
	from classes.characters.Interview import CREATE, Interview, RESPEC
	from classes.characters.Sheet import Sheet

	answers = draft.answers
	step = draft.step
	queue = answers["queue"]
	controls = Controls(draft.kind, step)
	first = step == queue[0] and not answers.get("returning")

	if step == "species" :
		controls.menus.append(_species_menu(draft))
	elif step == "occupation" :
		menu = _occupation_menu(draft)
		if menu.options :
			controls.menus.append(menu)
	elif step.startswith("field:") :
		menu = _choice_menu(draft)
		if menu is not None :
			controls.menus.append(menu)
	elif step == "stat_method" :
		controls.buttons += [Button("buy", "Buy points", PRIMARY), Button("roll", "Roll", PRIMARY)]
	elif step == "gear" :
		controls.menus += _gear_menus(draft)
		controls.buttons.append(Button("done", "Done", SUCCESS))
	elif step == "summary" :
		items = Interview._summary_items(draft)
		controls.menus += _summary_menus([label for _, label, _ in items], [value for _, _, value in items])
		label = {"edit" : "Save changes"}.get(draft.kind, "Send to staff")
		controls.buttons.append(Button("submit", label, SUCCESS))

	if step != "summary" and not first :
		controls.buttons.append(Button("back", "Back"))
	if _skippable(draft) :
		controls.buttons.append(Button("skip", "Skip"))
	if draft.kind == CREATE and first and Sheet.questions(draft.guild_id) :
		controls.buttons.append(Button("template", "Blank sheet to fill in"))
	controls.buttons.append(Button("cancel", "Cancel", DANGER))
	return controls


# ============================================================
def _skippable(draft) -> bool :
	"""Whether `skip` moves on from this step: optional questions, and the occupation when none is open."""
	from classes.characters.Interview import Interview
	from database.transactions.SheetFieldTransactions import SheetFieldTransactions

	step = draft.step
	if step.startswith("field:") :
		sheet_field = SheetFieldTransactions().get(int(step.split(":", 1)[1]))
		return sheet_field is None or not sheet_field.required
	if step == "occupation" :
		return not any(choice.locked is None for choice in Interview._occupation_choices(draft))
	return False


# ============================================================
def _species_menu(draft) -> Menu :
	from classes.characters.Interview import Interview
	from classes.characters.Special import Special
	from database.transactions.SpeciesTransactions import APPROVED

	rules = Special.rules(draft.guild_id)
	creatable = Interview.can_make_species(draft)
	choices = Interview.species_choices(draft)[: MENU_LIMIT - (1 if creatable else 0)]
	options = []
	for species in choices :
		description = Interview.species_changes(species, rules) or "No changes to the SPECIAL stats"
		if species.state != APPROVED :
			description = f"Waiting for review · {description}"
		options.append(Option(clip(species.name), f"#{species.id}", clip(description),
		                      default=species.id == draft.answers.get("species_id")))
	if creatable :
		options.append(Option("Make a new species", NEW_SPECIES_VALUE,
		                      "Describe your own species first; staff review it with your character"))
	return Menu("pick", "Pick a species", options)


# ============================================================
def _occupation_menu(draft) -> Menu :
	"""The occupations open to the player (and the one they hold); locked ones are only in the text."""
	from classes.characters.Interview import Interview

	current = draft.answers.get("occupation_id")
	options = []
	for choice in Interview._occupation_choices(draft) :
		if choice.locked is not None and choice.occupation.id != current :
			continue
		options.append(Option(clip(choice.label), f"#{choice.occupation.id}",
		                      clip(choice.occupation.description) or None, default=choice.occupation.id == current))
	return Menu("pick", "Pick an occupation", options[:MENU_LIMIT])


# ============================================================
def _choice_menu(draft) -> Menu | None :
	"""The options of a choice question, numbered as the question lists them."""
	from database.transactions.SheetFieldTransactions import SheetFieldTransactions

	sheet_field = SheetFieldTransactions().get(int(draft.step.split(":", 1)[1]))
	if sheet_field is None or sheet_field.type != CHOICE or not sheet_field.choices :
		return None
	current = draft.answers["fields"].get(str(sheet_field.id))
	options = [Option(clip(choice), str(number), default=choice == current)
	           for number, choice in enumerate(sheet_field.choices[:MENU_LIMIT], start=1)]
	return Menu("pick", clip(f"Pick: {sheet_field.label}", 150), options)


# ============================================================
def _gear_menus(draft) -> list[Menu] :
	"""Add to the bag (what the player can pick and does not have yet) and take out of it."""
	from classes.characters.Interview import Interview
	from classes.gear.Gear import Gear
	from classes.gear.GearCard import GearCard

	basket = Interview._basket(draft)
	picked = {item.id for item in basket}
	left = Interview._money_left(draft, basket)
	economy = Gear.economy(draft.guild_id)
	add = []
	for entry in Interview._shop(draft) :
		if entry.locked or entry.item.id in picked :
			continue
		description = f"{entry.item.kind} · {GearCard.price_text(draft.guild_id, entry.price)}"
		if economy and entry.price > left :
			description += " · more than you have left"
		add.append(Option(clip(entry.item.name), f"#{entry.item.id}", clip(description)))
	menus = []
	if add :
		menus.append(Menu("add", "Add to your bag", add[:MENU_LIMIT]))
	if basket :
		menus.append(Menu("remove", "Take out of your bag",
		                  [Option(clip(item.name), f"#{item.id}") for item in basket[:MENU_LIMIT]]))
	return menus


# ============================================================
def _summary_menus(labels: list[str], values: list[str]) -> list[Menu] :
	"""Change an answer: the summary's numbered items, over as many menus as they need (one row is kept for the
	buttons)."""
	options = [Option(clip(f"{number}. {label}"), str(number), clip(value) or None)
	           for number, (label, value) in enumerate(zip(labels, values), start=1)]
	chunks = [options[start : start + MENU_LIMIT] for start in range(0, len(options), MENU_LIMIT)][: ROW_LIMIT - 1]
	if len(chunks) == 1 :
		return [Menu("change", "Change an answer", chunks[0])]
	return [Menu(f"change{index}", f"Change an answer ({chunk[0].value}-{chunk[-1].value})", chunk)
	        for index, chunk in enumerate(chunks)]


# ============================================================
def _typed(draft, menu: str, value: str) -> str | None :
	"""What picking value in menu types, worked out from the draft as it is now."""
	from classes.characters.Interview import Interview
	from database.transactions.OccupationTransactions import OccupationTransactions
	from database.transactions.SpeciesTransactions import SpeciesTransactions

	if menu.startswith("change") or not value.startswith(("#", "+")) :
		return value
	if value == NEW_SPECIES_VALUE :
		return "new"
	item_id = int(value[1 :])
	step = draft.step
	if step == "species" :
		species = SpeciesTransactions().get(item_id)
		return species.name if species else None
	if step == "occupation" :
		occupation = OccupationTransactions().get(item_id)
		return occupation.name if occupation else None
	if step == "gear" :
		number = next((str(number) for number, entry in enumerate(Interview._shop(draft), start=1)
		               if entry.item.id == item_id), None)
		if menu == "add" :
			return number
		if number is None :
			item = next((item for item in Interview._basket(draft) if item.id == item_id), None)
			return f"remove {item.name}" if item else None
		return f"remove {number}"
	return None


# == species interview ==

# ============================================================
def _species_controls(draft) -> Controls :
	from classes.species.SpeciesInterview import LABELS, STAT_STEPS, STEPS

	answers = draft.answers
	step = draft.step
	controls = Controls(draft.kind, step)
	if step == "summary" :
		labels = [LABELS[each] for each in STEPS[:-1]]
		values = [" ".join(str(item) for item in answers[each]) if each in STAT_STEPS else answers.get(each) or "not set"
		          for each in STEPS[:-1]]
		controls.menus += _summary_menus(labels, values)
		controls.buttons.append(Button("submit", "Send to staff", SUCCESS))
	else :
		if step in STAT_STEPS :
			controls.buttons.append(Button("keep", "Keep these", PRIMARY))
		if step != STEPS[0] or answers.get("returning") :
			controls.buttons.append(Button("back", "Back"))
	cancel = "Cancel species" if answers.get("paused_character") else "Cancel"
	controls.buttons.append(Button("cancel", cancel, DANGER))
	return controls
