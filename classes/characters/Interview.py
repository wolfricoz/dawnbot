"""The DM interview that creates or edits a character, one question at a time.

Everything a player answers is saved in their draft (the drafts table) right away, so an interview has no time limit
and survives restarts. This module holds the questions and the rules; it never talks to Discord. The caller sends
the returned text to the player and acts on the outcome (see CharacterFlow).

A draft walks through its queue of steps:
  name, trigger, avatar          asked for every new character
  species                        when the server has species; a new character can also make one here
  occupation                     when the server has occupations
  field:<id>                     one per question on the server's sheet
  stat_method, stats             how the SPECIAL stats are set, and their values
  gear                           starting gear from the server's catalog, when it has items the member can see
  summary                        the answers so far; from here the player changes answers or submits
"""
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from classes.characters.Access import Access
from classes.characters.Card import Card
from classes.characters.Choices import Choices
from classes.characters.Edits import Edits
from classes.characters.ImageStorage import ImageError, ImageStorage
from classes.characters import SheetPaste
from classes.characters.Sheet import INFO, LONG, Sheet
from classes.characters.SpeciesRules import NO_CHANGES, SpeciesRules
from classes.characters.Special import POINT_BUY, ROLLED, STATS, Special
from classes.gear.Gear import ARMOR, CREATION, Gear, ShopItem
from classes.gear.GearCard import GearCard
from classes.kernel.ConfigData import ConfigData
from database.database import Characters, Drafts, GearItems
from database.transactions.CharacterInfoTransactions import CharacterInfoTransactions
from database.transactions.CharacterTransactions import CharacterTransactions, PENDING
from database.transactions.CurrencyTransactions import CurrencyTransactions, START
from database.transactions.DraftTransactions import DraftTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from database.transactions.OccupationTransactions import OccupationTransactions
from database.transactions.SheetFieldTransactions import SheetFieldTransactions
from database.transactions.SpeciesTransactions import APPROVED as SPECIES_APPROVED, PENDING as SPECIES_PENDING, \
	SpeciesTransactions
from resources.configs.ConfigMapping import ConfigMapping

CREATE = "create"
EDIT = "edit"
RESPEC = "respec"
# A copy of a character from another server: a new character that starts from the copied answers.
IMPORT = "import"

# Outcomes of an answer that ends the interview; the outcomes of Edits.submit are used as well.
CREATED = "created"
CANCELLED = "cancelled"

# Webhook names can be 80 characters, and Discord refuses these words in them.
NAME_LIMIT = 80
FORBIDDEN_NAME_PARTS = ["discord", "clyde"]
TRIGGER_LIMIT = 50
# The word that stands for the player's message when they describe their prefix and suffix.
PLACEHOLDER = "text"
# Typed at the species step (or picked from its menu) to make a new species first.
NEW_SPECIES = ("new", "new species")
SUMMARY_VALUE_LIMIT = 150

STAT_ORDER = ", ".join(stat.capitalize() for stat in STATS)


@dataclass
class Reply :
	"""What to tell the player, and what happened when the interview ended."""
	text: str
	finished: bool = False
	outcome: str | None = None
	character: Characters | None = None
	# The species a species interview created or changed.
	species: object = None
	# Stored images that are no longer used and should be removed from storage.
	discard_images: list[int] = field(default_factory=list)


class Interview :

	# == starting ==

	# ============================================================
	@staticmethod
	def start(uid: int, guild_id: int, guild_name: str, kind: str, character: Characters | None = None,
	          access: Access | None = None, avatar_id: int | None = None,
	          source_guild_name: str | None = None) -> tuple[Drafts | None, str] :
		"""Starts an interview and returns its draft with the first message to send.

		access describes the member, for the species and occupations they may pick. For an import, character is the
		character being copied, avatar_id the copy of its picture, and source_guild_name the server it comes from.
		Returns (None, why) when the user is already in an interview.
		"""
		existing = DraftTransactions().get(uid)
		if existing is not None :
			return None, Interview.busy_text(existing)

		answers = {"guild_name" : guild_name, "fields" : {}, "access" : (access or Access()).to_dict()}
		if kind == IMPORT :
			answers |= Interview._import_answers(guild_id, character, avatar_id, source_guild_name)
		elif character is not None :
			answers |= {
				"name"          : character.name,
				"prefix"        : character.prefix,
				"suffix"        : character.suffix,
				"avatar_id"     : character.avatar_id,
				"species_id"    : character.species_id,
				"occupation_id" : character.occupation_id,
				"fields"        : {str(key) : value for key, value in
				                   CharacterInfoTransactions().get_answers(character.id).items()},
			}
		if kind == RESPEC :
			answers["stat_method"] = POINT_BUY
			answers["budget"] = sum(getattr(character, stat) for stat in STATS) + character.unspent_points
		answers["queue"] = Interview._queue(guild_id, kind, answers, uid)

		draft = DraftTransactions().create(uid, guild_id, kind, answers["queue"][0],
		                                   target_id=character.id if character and kind != IMPORT else None,
		                                   answers=answers)
		intro = {
			IMPORT : f"**Bringing {character.name if character else ''} to {guild_name}**\n"
			         f"I copied their name, how you speak as them, their picture and their written answers. Experience, "
			         f"stats, gear and currency start fresh here. I'll ask what this server needs; there is no time "
			         f"limit. Use the buttons under each question, or type **back** or **cancel**. You can also paste "
			         f"a sheet here to fill in several answers at once.",
			CREATE : f"**Creating a character on {guild_name}**\n"
			         f"I'll ask you some questions, one at a time. There is no time limit: every answer is saved, so "
			         f"you can stop and come back later.\n"
			         f"Use the buttons under each question, or type **back** for the previous question, **skip** to "
			         f"leave an optional question empty, or **cancel** to stop.\n"
			         f"Already wrote this character down somewhere? Paste the whole sheet here in one message and "
			         f"I'll fill in what I can, then only ask what's missing. Type **template** for a blank copy of "
			         f"this server's sheet to fill in.",
			EDIT   : f"**Editing {character.name if character else ''} on {guild_name}**",
			RESPEC : f"**Changing the SPECIAL stats of {character.name if character else ''} on {guild_name}**\n"
			         f"Staff review a respec before it applies. Type **cancel** to stop.",
		}[kind]
		return draft, f"{intro}\n\n{Interview.prompt(draft)}"

	# ============================================================
	@staticmethod
	def busy_text(draft: Drafts) -> str :
		answers = draft.answers or {}
		what = {CREATE : "creating a character", IMPORT : f"bringing {answers.get('name', 'a character')} over",
		        EDIT : f"editing {answers.get('name', 'a character')}",
		        RESPEC : f"changing the stats of {answers.get('name', 'a character')}"}.get(draft.kind, "an interview")
		return (f"You are still {what} on {answers.get('guild_name', 'another server')}. Finish it in our DMs, or "
		        f"type **cancel** there to stop it, before starting something new.")

	# ============================================================
	@staticmethod
	def _is_new(draft: Drafts) -> bool :
		"""Whether the interview makes a new character (created here or copied from another server)."""
		return draft.kind in (CREATE, IMPORT)

	# ============================================================
	@staticmethod
	def _import_answers(guild_id: int, source: Characters, avatar_id: int | None, source_guild_name: str | None) -> dict :
		"""The answers an import starts from: the character's name, prefix and suffix, the copy of its picture, its
		answers to questions this server's sheet also asks (matched by name), and its other fields as extra fields."""
		labels = {sheet_field.label.lower() : sheet_field.id for sheet_field in Sheet.questions(guild_id)}
		fields, extras = {}, []
		for info in CharacterInfoTransactions().get_all(source.id) :
			field_id = labels.get(info.key.lower())
			if field_id is not None :
				fields[str(field_id)] = info.value
			else :
				extras.append({"key" : info.key, "value" : info.value})
		return {"name" : source.name, "prefix" : source.prefix, "suffix" : source.suffix, "avatar_id" : avatar_id,
		        "fields" : fields, "extras" : extras, "imported_from" : source.id,
		        "source_guild" : source_guild_name or "another server"}

	# ============================================================
	@staticmethod
	def _import_queue(guild_id: int, uid: int, answers: dict) -> list[str] :
		"""An import asks only what the copy is missing or what clashes with this server."""
		steps = []
		if Interview.check_name(answers["name"], uid, guild_id) :
			steps.append("name")
		if CharacterTransactions().trigger_taken(uid, guild_id, answers.get("prefix"), answers.get("suffix")) :
			steps.append("trigger")
		if ImageStorage.configured() and not answers.get("avatar_id") :
			steps.append("avatar")
		return steps

	# ============================================================
	@staticmethod
	def _queue(guild_id: int, kind: str, answers: dict, uid: int | None = None) -> list[str] :
		"""The steps this interview walks through, decided once when it starts."""
		if kind == RESPEC :
			return ["stats", "summary"]
		if kind == EDIT :
			# Only questions that became required since the character was made are asked up front.
			missing = Sheet.missing_required(guild_id, answers["fields"])
			return [f"field:{sheet_field.id}" for sheet_field in missing] + ["summary"]
		if kind == IMPORT :
			steps = Interview._import_queue(guild_id, uid, answers)
		else :
			steps = ["name", "trigger"]
			if ImageStorage.configured() :
				steps.append("avatar")
		# Asked even with one species to pick from: the player sees it, and can make a new one instead.
		if Choices.species(guild_id, Access.from_dict(answers["access"])) :
			steps.append("species")
		if OccupationTransactions().get_all(guild_id) :
			steps.append("occupation")
		if kind == IMPORT :
			# Questions the copy already answers are not asked again; they can be changed from the summary.
			steps += [f"field:{sheet_field.id}" for sheet_field in Sheet.missing_required(guild_id, answers["fields"])]
		else :
			steps += [f"field:{sheet_field.id}" for sheet_field in Sheet.questions(guild_id)]
		if len(Special.rules(guild_id).methods) > 1 :
			steps.append("stat_method")
		steps.append("stats")
		if Gear.shop_items(guild_id, Access.from_dict(answers["access"])) :
			steps.append("gear")
		return steps + ["summary"]

	# == asking ==

	# ============================================================
	@staticmethod
	def prompt(draft: Drafts) -> str :
		"""The message that asks for the draft's current step."""
		answers = draft.answers
		step = draft.step
		if step == "name" :
			text = "**What is your character's name?**"
			if answers.get("name") :
				text += f"\nCurrently: {answers['name']}"
			return text
		if step == "trigger" :
			text = (f"**How will you speak as {answers.get('name', 'your character')}?**\n"
			        f"Send an example message, with the word `{PLACEHOLDER}` where your message goes. What you put "
			        f"before it becomes the prefix, what you put after it the suffix.\n"
			        f"`Aria: {PLACEHOLDER}` means you write `Aria: Hello there`.\n"
			        f"`{PLACEHOLDER} -a` means you write `Hello there -a`.\n"
			        f"`[{PLACEHOLDER}]` means you write `[Hello there]`.")
			if answers.get("prefix") or answers.get("suffix") :
				text += f"\nCurrently: {Card.trigger_text(answers.get('prefix'), answers.get('suffix'))}"
			return text
		if step == "avatar" :
			text = (f"**Send a picture for {answers.get('name', 'your character')}.**\n"
			        f"Upload an image here (PNG, JPG, WEBP or GIF, up to 8 MB).")
			if answers.get("avatar_id") :
				text += "\nYou already sent one; a new image replaces it."
			return text
		if step.startswith("field:") :
			return Interview._field_prompt(draft)
		if step == "species" :
			return Interview._species_prompt(draft)
		if step == "occupation" :
			return Interview._occupation_prompt(draft)
		if step == "stat_method" :
			rules = Special.rules(draft.guild_id)
			return (f"**How do you want to set your SPECIAL stats?**\n"
			        f"1. **buy**: every stat starts at {rules.base} and you get {rules.bonus} extra points to spend. "
			        f"You can lower a stat to free up points.\n"
			        f"2. **roll**: I roll seven values and you decide which stat gets which. The total is never "
			        f"higher than buying gives you, and you can reroll as often as you like.\n"
			        f"Type **buy** or **roll**.")
		if step == "stats" :
			return Interview._stats_prompt(draft)
		if step == "gear" :
			return Interview._gear_prompt(draft)
		return Interview._summary(draft)

	# ============================================================
	@staticmethod
	def _field_prompt(draft: Drafts) -> str :
		fields = SheetFieldTransactions().get_all(draft.guild_id)
		index = next((i for i, sheet_field in enumerate(fields) if f"field:{sheet_field.id}" == draft.step), None)
		if index is None :
			return "That question is no longer on the sheet. Type **skip** to continue."
		current = fields[index]
		lines = []
		# The notes right above this question, and its section heading when it is the first question under it.
		notes = []
		for earlier in reversed(fields[:index]) :
			if earlier.type != INFO :
				break
			notes.insert(0, earlier)
		previous = fields[index - len(notes) - 1] if index - len(notes) - 1 >= 0 else None
		if current.section and (previous is None or previous.section != current.section) :
			lines.append(f"__**{current.section}**__")
		for note in notes :
			lines.append(f"*{note.label}*\n{note.help or ''}".strip())
		lines.append(Sheet.describe(current))
		answer = draft.answers["fields"].get(str(current.id))
		if answer :
			lines.append(f"Current answer: {Interview._shorten(answer)}")
		return "\n".join(lines)

	# ============================================================
	@staticmethod
	def _species(draft: Drafts) :
		"""The species the draft's character is (or is becoming), or None."""
		return SpeciesTransactions().get(draft.answers.get("species_id"))

	# ============================================================
	@staticmethod
	def _limits(draft: Drafts) -> dict :
		return SpeciesRules.limits(Interview._species(draft), Special.rules(draft.guild_id))

	# ============================================================
	@staticmethod
	def _modifiers(draft: Drafts) -> dict :
		"""A species changes the starting values only when the character is made."""
		if not Interview._is_new(draft) :
			return {stat : 0 for stat in STATS}
		return SpeciesRules.modifiers(Interview._species(draft))

	# ============================================================
	@staticmethod
	def _budget(draft: Drafts) -> int :
		if draft.answers.get("budget") :
			return draft.answers["budget"]
		rules = Special.rules(draft.guild_id)
		return sum(SpeciesRules.start_values(rules, Interview._limits(draft), Interview._modifiers(draft)).values()) \
			+ rules.bonus

	# ============================================================
	@staticmethod
	def species_choices(draft: Drafts) -> list :
		"""The species the player may pick: the approved ones open to them, and the ones they made that are still
		waiting for review (a character can be sent in with one; staff approve the species first)."""
		species = Choices.species(draft.guild_id, Access.from_dict(draft.answers.get("access")))
		if Interview._is_new(draft) :
			species += [own for own in SpeciesTransactions().get_all(draft.guild_id, states=[SPECIES_PENDING])
			            if own.creator_uid == draft.uid]
		return species

	# ============================================================
	@staticmethod
	def species_changes(option, rules) -> str | None :
		"""What a species changes, on one line, or None when it changes nothing."""
		described = SpeciesRules.describe(option, rules)
		return None if described == NO_CHANGES else described.replace("\n", ", ").replace("**", "")

	# ============================================================
	@staticmethod
	def can_make_species(draft: Drafts) -> bool :
		"""Whether the player can make a new species from the species step."""
		from classes.species.SpeciesInterview import SpeciesInterview

		return Interview._is_new(draft) and SpeciesInterview.can_create(
			draft.guild_id, Access.from_dict(draft.answers.get("access")).staff) is None

	# ============================================================
	@staticmethod
	def _species_prompt(draft: Drafts) -> str :
		rules = Special.rules(draft.guild_id)
		lines = ["**What species is your character?**"]
		for number, option in enumerate(Interview.species_choices(draft), start=1) :
			line = f"{number}. **{option.name}**"
			if option.description :
				line += f": {Interview._shorten(option.description, 100)}"
			if option.state != SPECIES_APPROVED :
				line += " (waiting for review)"
			changes = Interview.species_changes(option, rules)
			# A species that changes nothing usually says so in its description already.
			if changes :
				line += f"\n-# {changes}"
			lines.append(line)
		answer = "Pick one from the menu, or type its number or name."
		if Interview.can_make_species(draft) :
			answer += " Not listed? Pick **Make a new species** (or type **new**) and I'll ask about it first."
		lines.append(answer)
		lines.append("-# Every species has a post in the species forum.")
		current = Interview._species(draft)
		if current :
			lines.append(f"Currently: {current.name}")
		return "\n".join(lines)

	# ============================================================
	@staticmethod
	def _occupation_choices(draft: Drafts) :
		return Choices.occupations(draft.guild_id, Access.from_dict(draft.answers.get("access")), draft.target_id)

	# ============================================================
	@staticmethod
	def _occupation_prompt(draft: Drafts) -> str :
		choices = Interview._occupation_choices(draft)
		lines = ["**What is your character's occupation?**"]
		for number, choice in enumerate(choices, start=1) :
			line = f"{number}. {choice.label}"
			if choice.occupation.description :
				line += f": {Interview._shorten(choice.occupation.description, 100)}"
			if choice.locked :
				line += f" (unavailable: {choice.locked})"
			lines.append(line)
		if any(choice.locked is None for choice in choices) :
			lines.append("Answer with the number or the name. The numbers in brackets show how many characters hold "
			             "it and how many can.")
		else :
			lines.append("None of these are open to you right now. Type **skip**; staff can give your character an "
			             "occupation later.")
		current = OccupationTransactions().get(draft.answers.get("occupation_id"))
		if current :
			lines.append(f"Currently: {current.name}")
		return "\n".join(lines)

	# ============================================================
	@staticmethod
	def _stats_prompt(draft: Drafts) -> str :
		rules = Special.rules(draft.guild_id)
		method = draft.answers.get("stat_method") or rules.methods[0]
		if method == ROLLED :
			Interview._ensure_roll(draft)
			modifiers = Interview._modifiers(draft)
			note = ""
			if any(modifiers.values()) :
				note = ("\nYour species then changes them: " + ", ".join(
					f"{stat.capitalize()} {change:+d}" for stat, change in modifiers.items() if change) + ".")
			return (f"**Your SPECIAL roll:** {', '.join(str(value) for value in draft.rolled_values)}\n"
			        f"Decide which stat gets which value: send the seven values in this order:\n"
			        f"{STAT_ORDER}{note}\n"
			        f"Type **reroll** to roll again (rerolls so far: {draft.rerolls}).\n"
			        f"-# Or place each value with the menus below.")
		budget = Interview._budget(draft)
		limits = Interview._limits(draft)
		starts = SpeciesRules.start_values(rules, limits, Interview._modifiers(draft))
		if not Interview._is_new(draft) :
			intro = f"You have **{budget}** points to divide over your stats."
		elif all(value == rules.base for value in starts.values()) :
			intro = (f"Every stat starts at {rules.base} and you have {rules.bonus} extra points, so **{budget}** "
			         f"points in total. Lower a stat to free up points for another.")
		else :
			intro = (f"Your species starts you at {Special.summary(starts)}, and you have {rules.bonus} extra points, "
			         f"so **{budget}** points in total. Lower a stat to free up points for another.")
		if all(limit == (rules.minimum, rules.maximum) for limit in limits.values()) :
			bounds = f"Every stat has to be between {rules.minimum} and {rules.maximum}."
		else :
			bounds = "Your species' limits: " + ", ".join(
				f"{stat[0].upper()} {low}-{high}" for stat, (low, high) in limits.items()) + "."
		return (f"**Set your SPECIAL stats.**\n{intro} {bounds}\n"
		        f"Send seven numbers in this order:\n{STAT_ORDER}\n"
		        f"For example: `{' '.join(str(starts[stat]) for stat in STATS)}`. Points you do not spend are kept "
		        f"for later.\n"
		        f"-# Or pick each value with the menus below; they keep count of your points.")

	# ============================================================
	@staticmethod
	def _ensure_roll(draft: Drafts) -> None :
		if draft.rolled_values is None :
			draft.rolled_values = Special.roll(Special.rules(draft.guild_id))
			DraftTransactions().save(draft)

	# ============================================================
	@staticmethod
	def _shop(draft: Drafts) -> list[ShopItem] :
		"""The catalog as the member sees it, numbered in this order in the gear prompt."""
		return Gear.shop_items(draft.guild_id, Access.from_dict(draft.answers.get("access")))

	# ============================================================
	@staticmethod
	def _starting_currency(guild_id: int) -> int :
		return ConfigData().get_int(guild_id, ConfigMapping.STARTING_CURRENCY) or 0

	# ============================================================
	@staticmethod
	def _basket(draft: Drafts) -> list[GearItems] :
		"""The picked starting gear that is still in the server's catalog, in the order it was picked."""
		items = []
		for item_id in draft.answers.get("gear") or [] :
			item = GearItemTransactions().get(item_id)
			if item is not None and item.guild_id == draft.guild_id :
				items.append(item)
		return items

	# ============================================================
	@staticmethod
	def _basket_text(draft: Drafts, basket: list[GearItems]) -> str :
		"""`Sword, Leather (300 of 3000 caps)`, `Sword (free)`, or `none`."""
		if not basket :
			return "none"
		names = Interview._shorten(", ".join(item.name for item in basket), 110)
		if not Gear.economy(draft.guild_id) :
			return f"{names} (free)"
		currency = ConfigData().get_key(draft.guild_id, ConfigMapping.CURRENCY_NAME)
		total = sum(Gear.price(item) for item in basket)
		return f"{names} ({total} of {Interview._starting_currency(draft.guild_id)} {currency})"

	# ============================================================
	@staticmethod
	def _money_left(draft: Drafts, basket: list[GearItems]) -> int :
		"""The starting currency minus the price of the picked gear."""
		return Interview._starting_currency(draft.guild_id) - sum(Gear.price(item) for item in basket)

	# ============================================================
	@staticmethod
	def _gear_prompt(draft: Drafts) -> str :
		"""The catalog with numbers, the money left and what is in the bag; one line per item."""
		shop = Interview._shop(draft)
		basket = Interview._basket(draft)
		picked = {item.id for item in basket}
		lines = ["**Pick your starting gear.**"]
		if Gear.economy(draft.guild_id) :
			currency = ConfigData().get_key(draft.guild_id, ConfigMapping.CURRENCY_NAME)
			lines.append(f"You start with {Interview._starting_currency(draft.guild_id)} {currency}; what you don't "
			             f"spend is kept. Left to spend: **{Interview._money_left(draft, basket)} {currency}**.")
		else :
			lines.append("Gear is free on this server, so take what your character carries.")
		if not shop :
			lines.append("There is no gear to pick right now. Type **done** to continue.")
			return "\n".join(lines)
		for number, entry in enumerate(shop, start=1) :
			line = f"{number}. {GearCard.line(entry.item, entry.locked)}"
			if entry.item.id in picked :
				line += " · in your bag"
			lines.append(line)
		lines.append(f"In your bag: {Interview._basket_text(draft, basket) if basket else 'nothing yet'}")
		lines.append("Send a number or name to add an item (one of each), **remove** and a number or name to take one "
		             "out, and **done** when you are finished.")
		return "\n".join(lines)

	# ============================================================
	@staticmethod
	def _shorten(value: str, limit: int = SUMMARY_VALUE_LIMIT) -> str :
		value = " ".join(str(value).split())
		return value if len(value) <= limit else f"{value[:limit - 1]}…"

	# ============================================================
	@staticmethod
	def _summary_items(draft: Drafts) -> list[tuple[str, str, str]] :
		"""The answers on the summary as (step to change it, label, value)."""
		answers = draft.answers
		items = []
		if draft.kind != RESPEC :
			items.append(("name", "Name", answers.get("name") or "not set"))
			items.append(("trigger", "Speaks with", Card.trigger_text(answers.get("prefix"), answers.get("suffix"))))
			if ImageStorage.configured() :
				items.append(("avatar", "Picture", "set" if answers.get("avatar_id") else "not set"))
			if SpeciesTransactions().get_all(draft.guild_id, states=[SPECIES_APPROVED]) :
				species = Interview._species(draft)
				value = species.name if species else "not set"
				if species is not None and species.state != SPECIES_APPROVED :
					value += " (waiting for review)"
				items.append(("species", "Species", value))
			if OccupationTransactions().get_all(draft.guild_id) :
				occupation = OccupationTransactions().get(answers.get("occupation_id"))
				items.append(("occupation", "Occupation", occupation.name if occupation else "none"))
			for sheet_field in Sheet.questions(draft.guild_id) :
				value = answers["fields"].get(str(sheet_field.id))
				items.append((f"field:{sheet_field.id}", sheet_field.label,
				              Interview._shorten(value) if value else "not answered"))
		if draft.kind != EDIT or answers.get("stats_required") :
			stats = answers.get("stats")
			value = "not set"
			if stats :
				value = Special.summary(stats)
				if answers.get("stat_method") == ROLLED :
					value += f" (rolled, {draft.rerolls} rerolls)"
			first = "stat_method" if "stat_method" in answers.get("queue", []) else "stats"
			items.append((first, "SPECIAL", value))
		if Interview._is_new(draft) :
			# Shown while the catalog has something to pick, or something was picked before it emptied.
			basket = Interview._basket(draft)
			if basket or Interview._shop(draft) :
				items.append(("gear", "Starting gear", Interview._basket_text(draft, basket)))
		return items

	# ============================================================
	@staticmethod
	def _problems(draft: Drafts) -> list[str] :
		"""What still stops this draft from being submitted."""
		answers = draft.answers
		problems = []
		if draft.kind != RESPEC :
			if not answers.get("name") :
				problems.append("a name")
			if not answers.get("prefix") and not answers.get("suffix") :
				problems.append("a prefix or suffix")
			if Interview._is_new(draft) and ImageStorage.configured() and not answers.get("avatar_id") :
				problems.append("a picture")
			if SpeciesTransactions().get_all(draft.guild_id, states=[SPECIES_APPROVED]) \
					and Interview._species(draft) is None :
				problems.append("a species")
			if Interview._is_new(draft) and answers.get("occupation_id") is None \
					and any(choice.locked is None for choice in Interview._occupation_choices(draft)) :
				problems.append("an occupation")
			problems += [sheet_field.label for sheet_field in Sheet.missing_required(draft.guild_id, answers["fields"])]
		if (draft.kind != EDIT or answers.get("stats_required")) and not answers.get("stats") :
			problems.append("SPECIAL stats")
		return problems

	# ============================================================
	@staticmethod
	def _summary(draft: Drafts) -> str :
		lines = ["**Summary**"]
		for number, (_, label, value) in enumerate(Interview._summary_items(draft), start=1) :
			lines.append(f"{number}. **{label}:** {value}")
		extras = draft.answers.get("extras") or []
		if extras and Interview._is_new(draft) :
			lines.append(f"**Extra fields:** {Interview._shorten(', '.join(extra['key'] for extra in extras))}")
		problems = Interview._problems(draft)
		if problems :
			lines.append(f"\nStill needed: {', '.join(problems)}.")
		send = "apply your changes" if draft.kind == EDIT else "send it to staff"
		lines.append(f"\nType a number to change that answer, **submit** to {send}, or **cancel** to stop.")
		if draft.kind != RESPEC :
			lines.append("-# You can also paste a sheet here to change several answers at once.")
		return "\n".join(lines)

	# == answering ==

	# ============================================================
	@staticmethod
	async def answer(draft: Drafts, text: str, attachments: list | None = None,
	                 store_image: Callable[[object], Awaitable[int]] | None = None,
	                 access: Access | None = None) -> Reply :
		"""Handles one message from the player and returns what to send back.

		attachments are the message's uploads; store_image saves one and returns its stored image id, or raises
		ImageError. access is the member as they are now (roles change); without it the last known access is used.
		"""
		text = (text or "").strip()
		command = text.lower()
		answers = draft.answers
		if access is not None :
			answers["access"] = access.to_dict()
		if command == "cancel" :
			return Interview._cancel(draft)
		if command == "back" :
			return Interview._back(draft)
		if command == "template" and draft.kind != RESPEC :
			return Reply("Copy this, fill it in and paste it back here in one message. Leave out what you don't "
			             "know yet; I'll ask for anything required that's missing.\n"
			             + "\n".join(Interview.template(draft)))
		if draft.kind != RESPEC :
			entries = SheetPaste.parse(text, SheetFieldTransactions().get_all(draft.guild_id), Interview._builtins(draft))
			if SheetPaste.is_sheet(entries, Interview._paste_threshold(draft)) :
				return await Interview._paste(draft, entries, attachments or [], store_image)

		step = draft.step
		problem = None
		if command == "skip" and step == "occupation" :
			if any(choice.locked is None for choice in Interview._occupation_choices(draft)) :
				return Reply("Please pick an occupation.")
			answers["occupation_id"] = None
			Interview._advance(draft)
			return Reply(Interview.prompt(draft))
		if command == "skip" and not step.startswith("field:") and step != "gear" :
			return Reply("This one cannot be skipped. Type **back** to return to the previous question."
			             if step != "summary" else "Type the number of an answer to change it, **submit**, or **cancel**.")
		if step == "summary" :
			if command == "submit" :
				return Interview._submit(draft)
			items = Interview._summary_items(draft)
			if command.isdigit() and 1 <= int(command) <= len(items) :
				draft.step = items[int(command) - 1][0]
				answers["returning"] = True
				DraftTransactions().save(draft)
				return Reply(Interview.prompt(draft))
			return Reply("Type the number of an answer to change it, **submit**, or **cancel**.")
		elif step == "name" :
			problem = Interview._answer_name(draft, text)
		elif step == "trigger" :
			problem = Interview._answer_trigger(draft, text)
		elif step == "avatar" :
			return await Interview._answer_avatar(draft, attachments or [], store_image)
		elif step.startswith("field:") :
			problem = Interview._answer_field(draft, text, command)
		elif step == "species" :
			if command in NEW_SPECIES :
				return Interview._new_species(draft)
			problem = Interview._answer_species(draft, text)
			if problem is None and draft.kind == EDIT and answers.get("stats_required") :
				# The character's stats do not fit the new species, so they are set again before the summary.
				draft.step = "stats"
				answers["returning"] = True
				DraftTransactions().save(draft)
				return Reply("Your current stats do not fit that species, so please set them again.\n\n"
				             + Interview.prompt(draft))
		elif step == "occupation" :
			problem = Interview._answer_occupation(draft, text)
		elif step == "stat_method" :
			problem = Interview._answer_method(draft, command)
		elif step == "stats" :
			if command == "reroll" and answers.get("stat_method") == ROLLED :
				draft.rolled_values = Special.roll(Special.rules(draft.guild_id))
				draft.rerolls += 1
				answers.pop("stat_assign", None)
				DraftTransactions().save(draft)
				return Reply(Interview.prompt(draft))
			problem = Interview._answer_stats(draft, text)
		elif step == "gear" :
			return Interview._answer_gear(draft, text, command)

		if problem :
			return Reply(problem)
		Interview._advance(draft)
		return Reply(Interview.prompt(draft))

	# ============================================================
	@staticmethod
	def _advance(draft: Drafts) -> None :
		"""Moves to the next step: back to the summary after changing one answer from it, else along the queue."""
		answers = draft.answers
		queue = answers["queue"]
		if draft.step == "stat_method" :
			draft.step = "stats"
		elif answers.pop("returning", False) or draft.step not in queue :
			draft.step = "summary"
		else :
			draft.step = queue[min(queue.index(draft.step) + 1, len(queue) - 1)]
		if draft.step == "summary" :
			answers.pop("returning", None)
		DraftTransactions().save(draft)

	# ============================================================
	@staticmethod
	def _back(draft: Drafts) -> Reply :
		answers = draft.answers
		queue = answers["queue"]
		if draft.step == "summary" :
			return Reply("You are at the summary. Type a number to change that answer.\n\n" + Interview.prompt(draft))
		if draft.step == "stats" and "stat_method" in queue and len(Special.rules(draft.guild_id).methods) > 1 :
			draft.step = "stat_method"
		elif answers.get("returning") or draft.step not in queue :
			answers.pop("returning", None)
			draft.step = "summary"
		elif queue.index(draft.step) == 0 :
			return Reply("This is the first question.\n\n" + Interview.prompt(draft))
		else :
			draft.step = queue[queue.index(draft.step) - 1]
		DraftTransactions().save(draft)
		return Reply(Interview.prompt(draft))

	# ============================================================
	@staticmethod
	def _new_images(draft: Drafts) -> list[int] :
		"""The picture uploaded during this interview, unless it is the character's current one."""
		avatar_id = draft.answers.get("avatar_id")
		if avatar_id is None :
			return []
		if draft.target_id is not None :
			character = CharacterTransactions().get_by_id(draft.target_id)
			if character is not None and character.avatar_id == avatar_id :
				return []
		return [avatar_id]

	# ============================================================
	@staticmethod
	def _cancel(draft: Drafts) -> Reply :
		images = Interview._new_images(draft)
		DraftTransactions().delete(draft.uid)
		return Reply("Cancelled. Nothing was changed.", finished=True, outcome=CANCELLED, discard_images=images)

	# ============================================================
	@staticmethod
	def check_name(name: str, uid: int, guild_id: int, exclude_id: int | None = None) -> str | None :
		"""Why a character name is refused, or None when it is fine."""
		if not name :
			return "Please send a name."
		if len(name) > NAME_LIMIT :
			return f"That name is {len(name)} characters long; the limit is {NAME_LIMIT}."
		if "\n" in name :
			return "A name has to fit on one line."
		for part in FORBIDDEN_NAME_PARTS :
			if part in name.lower() :
				return f"Discord does not allow names with \"{part}\" in them. Please pick another."
		other = CharacterTransactions().get(uid, guild_id, name)
		if other is not None and other.id != exclude_id :
			return f"You already have a character called {other.name} on this server."
		return None

	# ============================================================
	@staticmethod
	def parse_trigger(text: str) -> tuple[str | None, str | None] | None :
		"""Splits an example like `Aria: text` into (prefix, suffix); None when it has no single placeholder."""
		lowered = text.lower()
		if lowered.count(PLACEHOLDER) != 1 :
			return None
		index = lowered.index(PLACEHOLDER)
		prefix = text[:index].strip() or None
		suffix = text[index + len(PLACEHOLDER) :].strip() or None
		return prefix, suffix

	# ============================================================
	@staticmethod
	def check_trigger(text: str, uid: int, guild_id: int,
	                  exclude_id: int | None = None) -> tuple[tuple[str | None, str | None] | None, str | None] :
		"""Reads a prefix and suffix from an example message.

		@return: ((prefix, suffix), None) when it is fine, otherwise (None, why it was refused).
		"""
		parsed = Interview.parse_trigger(text.strip().strip("`"))
		if parsed is None :
			return None, (f"Please send an example with the word `{PLACEHOLDER}` in it exactly once, like "
			              f"`Aria: {PLACEHOLDER}`.")
		return Interview.check_trigger_parts(parsed[0], parsed[1], uid, guild_id, exclude_id)

	# ============================================================
	@staticmethod
	def check_trigger_parts(prefix: str | None, suffix: str | None, uid: int, guild_id: int,
	                        exclude_id: int | None = None) -> tuple[tuple[str | None, str | None] | None, str | None] :
		"""Checks a prefix and suffix given separately; returns like check_trigger."""
		prefix, suffix = (prefix or "").strip() or None, (suffix or "").strip() or None
		if not prefix and not suffix :
			return None, f"Put something before or after `{PLACEHOLDER}`, like `Aria: {PLACEHOLDER}`."
		if len(prefix or "") > TRIGGER_LIMIT or len(suffix or "") > TRIGGER_LIMIT :
			return None, f"A prefix or suffix can be at most {TRIGGER_LIMIT} characters."
		if CharacterTransactions().trigger_taken(uid, guild_id, prefix, suffix, exclude_id) :
			return None, "Another of your characters on this server already uses that. Please pick something else."
		return (prefix, suffix), None

	# ============================================================
	@staticmethod
	def _answer_name(draft: Drafts, text: str) -> str | None :
		problem = Interview.check_name(text, draft.uid, draft.guild_id, draft.target_id)
		if problem is None :
			draft.answers["name"] = text
		return problem

	# ============================================================
	@staticmethod
	def _answer_trigger(draft: Drafts, text: str) -> str | None :
		parsed, problem = Interview.check_trigger(text, draft.uid, draft.guild_id, draft.target_id)
		if parsed is not None :
			draft.answers["prefix"], draft.answers["suffix"] = parsed
		return problem

	# ============================================================
	@staticmethod
	async def _answer_avatar(draft: Drafts, attachments: list, store_image) -> Reply :
		"""Stores the uploaded picture and moves on; a picture it replaces is handed back to be removed."""
		if not attachments :
			return Reply("Please upload an image as a file in this chat.")
		if store_image is None :
			return Reply("Pictures cannot be saved right now. Please try again later.")
		previous = Interview._new_images(draft)
		try :
			draft.answers["avatar_id"] = await store_image(attachments[0])
		except ImageError as e :
			return Reply(str(e))
		Interview._advance(draft)
		return Reply(Interview.prompt(draft), discard_images=previous)

	# ============================================================
	@staticmethod
	def _answer_field(draft: Drafts, text: str, command: str) -> str | None :
		field_id = draft.step.split(":", 1)[1]
		sheet_field = SheetFieldTransactions().get(int(field_id))
		if sheet_field is None or sheet_field.guild_id != draft.guild_id :
			# The question was removed from the sheet while the player was answering.
			draft.answers["fields"].pop(field_id, None)
			return None
		if command == "skip" :
			if sheet_field.required :
				return "This question is required, so it cannot be skipped."
			draft.answers["fields"].pop(field_id, None)
			return None
		value, problem = Sheet.check(sheet_field, text)
		if problem is None :
			draft.answers["fields"][field_id] = value
		return problem

	# ============================================================
	@staticmethod
	def _pick(options: list, text: str, name) :
		"""The option the player means, by its number or its name, or None."""
		if text.isdigit() and 1 <= int(text) <= len(options) :
			return options[int(text) - 1]
		return next((option for option in options if name(option).lower() == text.lower()), None)

	# ============================================================
	@staticmethod
	def _answer_species(draft: Drafts, text: str) -> str | None :
		species = Interview._pick(Interview.species_choices(draft), text, lambda option : option.name)
		if species is None :
			return "Please pick one of the species, by its number or its name."
		return Interview._set_species(draft, species)

	# ============================================================
	@staticmethod
	def _set_species(draft: Drafts, species) -> None :
		"""Gives the draft's character the species, dropping stats that no longer fit it."""
		answers = draft.answers
		answers["species_id"] = species.id
		limits = SpeciesRules.limits(species, Special.rules(draft.guild_id))
		if Interview._is_new(draft) :
			# Stats chosen for another species may not fit this one.
			stats = answers.get("stats")
			if stats and (answers.get("stat_method") == ROLLED or Special.check_values(
					[stats[stat] for stat in STATS], Special.rules(draft.guild_id), Interview._budget(draft), limits)) :
				answers.pop("stats", None)
			return None
		character = CharacterTransactions().get_by_id(draft.target_id)
		current = [getattr(character, stat) for stat in STATS]
		fits = all(limits[stat][0] <= value <= limits[stat][1] for stat, value in zip(STATS, current))
		answers["stats_required"] = not fits
		answers.pop("stats", None)
		if not fits :
			answers["stat_method"] = POINT_BUY
			answers["budget"] = sum(current) + character.unspent_points
		return None

	# ============================================================
	@staticmethod
	def _new_species(draft: Drafts) -> Reply :
		"""Puts the character aside and starts the species interview; the character comes back when it ends."""
		from classes.species.SpeciesInterview import SpeciesInterview

		if not Interview._is_new(draft) :
			return Reply("A new species can be made with `/species create`; once approved, pick it here.")
		problem = SpeciesInterview.can_create(draft.guild_id, Access.from_dict(draft.answers.get("access")).staff)
		if problem :
			return Reply(f"{problem} Please pick one of the species.")
		paused = {"kind" : draft.kind, "step" : draft.step, "target_id" : draft.target_id, "answers" : draft.answers,
		          "rolled_values" : draft.rolled_values, "rerolls" : draft.rerolls}
		DraftTransactions().delete(draft.uid)
		_, text = SpeciesInterview.start(draft.uid, draft.guild_id, draft.answers.get("guild_name", "the server"),
		                                 paused_character=paused)
		return Reply(text)

	# ============================================================
	@staticmethod
	def resume(uid: int, guild_id: int, paused: dict, species=None) -> str :
		"""Brings back a character draft put aside for a new species and returns its next question.

		With species (the one just made), the character gets it and moves past the species step.
		"""
		draft = DraftTransactions().create(uid, guild_id, paused["kind"], paused["step"], target_id=paused["target_id"],
		                                   answers=paused["answers"])
		draft.rolled_values = paused.get("rolled_values")
		draft.rerolls = paused.get("rerolls") or 0
		if species is not None :
			Interview._set_species(draft, species)
			Interview._advance(draft)
		else :
			DraftTransactions().save(draft)
		return Interview.prompt(draft)

	# ============================================================
	@staticmethod
	def _answer_occupation(draft: Drafts, text: str) -> str | None :
		choice = Interview._pick(Interview._occupation_choices(draft), text, lambda option : option.occupation.name)
		if choice is None :
			return "Please pick one of the occupations, by its number or its name."
		if choice.locked and choice.occupation.id != draft.answers.get("occupation_id") :
			return f"{choice.occupation.name} {choice.locked}. Please pick another."
		draft.answers["occupation_id"] = choice.occupation.id
		return None

	# ============================================================
	@staticmethod
	def _answer_method(draft: Drafts, command: str) -> str | None :
		methods = {"1" : POINT_BUY, "buy" : POINT_BUY, "point-buy" : POINT_BUY, "point buy" : POINT_BUY,
		           "2" : ROLLED, "roll" : ROLLED, "rolled" : ROLLED}
		method = methods.get(command)
		if method is None or method not in Special.rules(draft.guild_id).methods :
			return "Type **buy** or **roll**."
		if draft.answers.get("stat_method") != method :
			draft.answers.pop("stats", None)
			draft.answers.pop("stat_work", None)
			draft.answers.pop("stat_assign", None)
		draft.answers["stat_method"] = method
		return None

	# ============================================================
	@staticmethod
	def _answer_stats(draft: Drafts, text: str) -> str | None :
		rules = Special.rules(draft.guild_id)
		method = draft.answers.get("stat_method") or rules.methods[0]
		values = Special.parse(text)
		if values is None :
			return f"Please send exactly seven whole numbers, in this order:\n{STAT_ORDER}"
		limits = Interview._limits(draft)
		if method == ROLLED :
			Interview._ensure_roll(draft)
			problem = Special.check_assignment(values, draft.rolled_values)
			stats = SpeciesRules.apply_modifiers(Special.as_dict(values), limits, Interview._modifiers(draft))
		else :
			problem = Special.check_values(values, rules, Interview._budget(draft), limits)
			stats = Special.as_dict(values)
		if problem is None :
			draft.answers["stat_method"] = method
			draft.answers["stats"] = stats
		return problem

	# ============================================================
	@staticmethod
	def _answer_gear(draft: Drafts, text: str, command: str) -> Reply :
		"""Adds an item to the bag, takes one out (`remove <number or name>`), or moves on (`done` or `skip`).

		The bag holds one of each item: a character starts with a kit, not a stock to trade. An item has to be
		unlocked for the member and, unless gear is free, fit in what is left of the starting currency.
		"""
		answers = draft.answers
		basket = Interview._basket(draft)
		# Items removed from the catalog in the meantime silently leave the bag.
		answers["gear"] = [item.id for item in basket]
		if command in ("done", "skip") :
			Interview._advance(draft)
			return Reply(Interview.prompt(draft))
		shop = Interview._shop(draft)
		removing = command == "remove" or command.startswith("remove ")
		wanted = text[len("remove") :].strip() if removing else text
		entry = Interview._pick(shop, wanted, lambda option : option.item.name)
		if removing :
			item = entry.item if entry else next(
				(picked for picked in basket if picked.name.lower() == wanted.lower()), None)
			if item is None or item.id not in answers["gear"] :
				return Reply("That is not in your bag. Type **remove** with the number or name of an item in it.")
			answers["gear"].remove(item.id)
			message = f"Took **{item.name}** out of your bag."
		else :
			if entry is None :
				return Reply("Please pick an item by its number or name, or type **done** to move on.")
			item = entry.item
			if entry.locked :
				return Reply(f"{item.name} {entry.locked}, so it cannot be picked.")
			if item.id in answers["gear"] :
				return Reply(f"{item.name} is already in your bag; you can take one of each item.")
			left = Interview._money_left(draft, basket)
			if Gear.economy(draft.guild_id) and entry.price > left :
				currency = ConfigData().get_key(draft.guild_id, ConfigMapping.CURRENCY_NAME)
				return Reply(f"{item.name} costs {GearCard.price_text(draft.guild_id, entry.price)}, but you only have "
				             f"{left} {currency} left. Take something out first, or pick something cheaper.")
			answers["gear"].append(item.id)
			message = f"Added **{item.name}** to your bag."
		DraftTransactions().save(draft)
		return Reply(f"{message}\nIn your bag: {Interview._basket_text(draft, Interview._basket(draft))}\n"
		             f"Add another item, **remove** one, or type **done**.")

	# == pasting a whole sheet ==

	# ============================================================
	@staticmethod
	def _builtins(draft: Drafts) -> set[str] :
		"""The interview's own questions a pasted sheet can answer for this draft."""
		builtins = {SheetPaste.NAME, SheetPaste.PROXY, SheetPaste.PREFIX, SheetPaste.SUFFIX}
		if Choices.species(draft.guild_id, Access.from_dict(draft.answers.get("access"))) :
			builtins.add(SheetPaste.SPECIES)
		if OccupationTransactions().get_all(draft.guild_id) :
			builtins.add(SheetPaste.OCCUPATION)
		return builtins

	# ============================================================
	@staticmethod
	def _paste_threshold(draft: Drafts) -> int :
		"""A long answer can mention a label or two in passing, so reading it as a sheet takes one more."""
		if draft.step.startswith("field:") :
			sheet_field = SheetFieldTransactions().get(int(draft.step.split(":", 1)[1]))
			if sheet_field is not None and sheet_field.type == LONG :
				return SheetPaste.SHEET_THRESHOLD + 1
		return SheetPaste.SHEET_THRESHOLD

	# ============================================================
	@staticmethod
	def template(draft: Drafts) -> list[str] :
		"""The server's sheet as blank code blocks to copy, fill in and paste back."""
		return SheetPaste.template(SheetFieldTransactions().get_all(draft.guild_id), Interview._builtins(draft))

	# ============================================================
	@staticmethod
	def _step_done(draft: Drafts, step: str, fields: dict) -> bool :
		"""Whether a step needs no asking after a paste. Optional questions count as done: they can still be
		answered from the summary."""
		answers = draft.answers
		if step == "name" :
			return bool(answers.get("name"))
		if step == "trigger" :
			return bool(answers.get("prefix") or answers.get("suffix"))
		if step == "avatar" :
			return bool(answers.get("avatar_id"))
		if step == "species" :
			return answers.get("species_id") is not None
		if step == "occupation" :
			return answers.get("occupation_id") is not None
		if step.startswith("field:") :
			sheet_field = fields.get(step.split(":", 1)[1])
			return sheet_field is None or not sheet_field.required or bool(answers["fields"].get(str(sheet_field.id)))
		if step == "stat_method" :
			return bool(answers.get("stats"))
		if step == "stats" :
			return bool(answers.get("stats"))
		if step == "gear" :
			return "gear" in answers
		return False

	# ============================================================
	@staticmethod
	async def _paste(draft: Drafts, entries: list, attachments: list, store_image) -> Reply :
		"""Fills the draft from a pasted sheet, then asks only what is still missing.

		Every answer goes through the same checks as when it is typed on its own; one that fails is reported and
		left to be asked.
		"""
		answers = draft.answers
		fields = {str(sheet_field.id) : sheet_field for sheet_field in Sheet.questions(draft.guild_id)}
		filled, refused, extras = [], [], []
		trigger = {}
		for entry in entries :
			if not entry.value :
				continue
			kind = entry.target[0] if entry.target else None
			problem = None
			if kind == SheetPaste.FIELD :
				sheet_field = fields.get(str(entry.target[1]))
				if sheet_field is None :
					continue
				value, problem = SheetPaste.coerce(sheet_field, entry.value)
				if problem is None :
					answers["fields"][str(sheet_field.id)] = value
					filled.append(sheet_field.label)
			elif kind == SheetPaste.NAME :
				problem = Interview._answer_name(draft, " ".join(entry.value.split()))
				if problem is None :
					filled.append("Name")
			elif kind == SheetPaste.SPECIES :
				problem = Interview._answer_species(draft, " ".join(entry.value.split()))
				if problem is None :
					filled.append("Species")
			elif kind == SheetPaste.OCCUPATION :
				problem = Interview._answer_occupation(draft, " ".join(entry.value.split()))
				if problem is None :
					filled.append("Occupation")
			elif kind in (SheetPaste.PROXY, SheetPaste.PREFIX, SheetPaste.SUFFIX) :
				trigger[kind] = (entry.label, " ".join(entry.value.split()))
			elif Interview._is_new(draft) :
				extras.append({"key" : entry.label[:100], "value" : entry.value})
			else :
				refused.append(f"**{entry.label}**: not on this server's sheet. Add it with `/character add_info`.")
			if problem :
				refused.append(f"**{entry.label}**: {problem}")

		if trigger :
			if SheetPaste.PROXY in trigger :
				label, value = trigger[SheetPaste.PROXY]
				parsed, problem = Interview.check_trigger(value, draft.uid, draft.guild_id, draft.target_id)
			else :
				label = "Prefix" if SheetPaste.PREFIX in trigger else "Suffix"
				parsed, problem = Interview.check_trigger_parts(trigger.get(SheetPaste.PREFIX, ("", ""))[1],
				                                                trigger.get(SheetPaste.SUFFIX, ("", ""))[1],
				                                                draft.uid, draft.guild_id, draft.target_id)
			if parsed is not None :
				answers["prefix"], answers["suffix"] = parsed
				filled.append("Proxy")
			else :
				refused.append(f"**{label}**: {problem}")

		if attachments and store_image is not None and not answers.get("avatar_id") and ImageStorage.configured() :
			try :
				answers["avatar_id"] = await store_image(attachments[0])
				filled.append("Picture")
			except ImageError as e :
				refused.append(f"**Picture**: {e}")

		if extras :
			kept = {extra["key"].lower() : extra for extra in answers.get("extras") or []}
			kept |= {extra["key"].lower() : extra for extra in extras}
			answers["extras"] = list(kept.values())

		# Ask only what is still missing, in the usual order, then the stats, gear and summary.
		queue = Interview._queue(draft.guild_id, draft.kind, answers, draft.uid)
		if draft.kind == EDIT and answers.get("stats_required") and not answers.get("stats") :
			queue.insert(len(queue) - 1, "stats")
		answers["queue"] = [step for step in queue
		                    if step == "summary" or not Interview._step_done(draft, step, fields)]
		answers.pop("returning", None)
		draft.step = answers["queue"][0]
		DraftTransactions().save(draft)

		lines = ["**I read your sheet.**"]
		if filled :
			lines.append(f"Filled in {len(filled)} answer{'s' if len(filled) != 1 else ''}: "
			             f"{Interview._shorten(', '.join(filled), 600)}.")
		if extras :
			lines.append(f"Not on this server's sheet, so kept as extra fields: "
			             f"{Interview._shorten(', '.join(extra['key'] for extra in extras), 300)}.")
		if refused :
			lines.append("Couldn't use these, so I'll ask again where it's needed:")
			lines += [f"- {Interview._shorten(line, 300)}" for line in refused]
		if draft.step != "summary" :
			lines.append("A few more questions and you're done. Optional questions you left out can be added from "
			             "the summary.")
		return Reply("\n".join(lines) + "\n\n" + Interview.prompt(draft))

	# == submitting ==

	# ============================================================
	@staticmethod
	def _submit(draft: Drafts) -> Reply :
		problems = Interview._problems(draft)
		if problems :
			return Reply(f"Not everything is filled in yet. Still needed: {', '.join(problems)}.\n\n"
			             + Interview.prompt(draft))
		if Interview._is_new(draft) :
			return Interview._submit_create(draft)
		character = CharacterTransactions().get_by_id(draft.target_id) if draft.target_id else None
		if character is None :
			DraftTransactions().delete(draft.uid)
			return Reply("That character no longer exists, so nothing was changed.", finished=True,
			             outcome=CANCELLED, discard_images=Interview._new_images(draft))
		changes = Interview._changes(draft, character)
		if "occupation_id" in changes and not Choices.room_for(changes["occupation_id"], character.id) :
			return Reply("That occupation filled up in the meantime. Please pick another.\n\n"
			             + Interview.prompt(draft))
		outcome, character, unused = Edits.submit(character, changes)
		DraftTransactions().delete(draft.uid)
		text = {
			"unchanged"   : "Nothing was changed.",
			"applied"     : f"Your changes to {character.name} are saved.",
			"resubmitted" : f"{character.name} was updated and sent to staff for review. I'll message you when they "
			                f"have looked at it.",
			"review"      : f"Your changes to {character.name} were sent to staff for review. Until they are "
			                f"approved, {character.name} stays as it was.",
		}[outcome]
		return Reply(text, finished=True, outcome=outcome, character=character, discard_images=unused)

	# ============================================================
	@staticmethod
	def _changes(draft: Drafts, character: Characters) -> dict :
		"""What the draft's answers change on the character it edits."""
		answers = draft.answers
		if draft.kind == RESPEC :
			current = {stat : getattr(character, stat) for stat in STATS}
			return {"stats" : answers["stats"]} if answers["stats"] != current else {}
		changes = {}
		for key in ("name", "prefix", "suffix", "avatar_id", "species_id", "occupation_id") :
			if answers.get(key) != getattr(character, key) :
				changes[key] = answers.get(key)
		if answers.get("stats_required") and answers.get("stats") :
			changes["stats"] = answers["stats"]
		current = {str(key) : value for key, value in CharacterInfoTransactions().get_answers(character.id).items()}
		fields = {}
		for sheet_field in Sheet.questions(draft.guild_id) :
			key = str(sheet_field.id)
			if answers["fields"].get(key) != current.get(key) :
				fields[key] = answers["fields"].get(key)
		if fields :
			changes["fields"] = fields
		return changes

	# ============================================================
	@staticmethod
	def _submit_create(draft: Drafts) -> Reply :
		answers = draft.answers
		cap = ConfigData().get_int(draft.guild_id, ConfigMapping.CHARACTER_CAP)
		if CharacterTransactions().count_active(draft.uid, draft.guild_id) >= cap :
			return Reply(f"You already have {cap} characters on {answers.get('guild_name', 'this server')}, which is "
			             f"the limit there. Delete one first, then type **submit** again.")
		# Another character can have taken the name or the prefix and suffix since they were answered.
		problem = Interview.check_name(answers["name"], draft.uid, draft.guild_id)
		if problem is None and CharacterTransactions().trigger_taken(draft.uid, draft.guild_id, answers.get("prefix"),
		                                                             answers.get("suffix")) :
			problem = "Another of your characters on this server now uses that prefix and suffix."
		species = Interview._species(draft)
		access = Access.from_dict(answers.get("access"))
		if problem is None and species is not None and species.id not in [
				option.id for option in Interview.species_choices(draft)] :
			problem = f"{species.name} can no longer be picked. Please pick another species."
		if problem is None and not Choices.room_for(answers.get("occupation_id")) :
			problem = "That occupation filled up in the meantime. Please pick another."
		if problem :
			return Reply(f"{problem}\n\n{Interview.prompt(draft)}")
		basket, not_bought = Interview._check_basket(draft, access)
		starting = Interview._starting_currency(draft.guild_id)
		total = sum(Gear.price(item) for item in basket)
		if Gear.economy(draft.guild_id) and total > starting :
			currency = ConfigData().get_key(draft.guild_id, ConfigMapping.CURRENCY_NAME)
			draft.step = "gear"
			answers["returning"] = True
			DraftTransactions().save(draft)
			return Reply(" ".join(not_bought + [
				f"Your starting gear now costs {total} {currency}, more than the {starting} {currency} you start "
				f"with. Please take something out."]) + f"\n\n{Interview.prompt(draft)}")

		stats = answers["stats"]
		leftover = Interview._budget(draft) - sum(stats.values()) if answers.get("stat_method") == POINT_BUY else 0
		character = CharacterTransactions().add(
			draft.uid, draft.guild_id, answers["name"], state=PENDING, prefix=answers.get("prefix"),
			suffix=answers.get("suffix"), avatar_id=answers.get("avatar_id"), species_id=answers.get("species_id"),
			occupation_id=answers.get("occupation_id"), stat_method=answers.get("stat_method"),
			rerolls=draft.rerolls if answers.get("stat_method") == ROLLED else 0, unspent_points=max(0, leftover),
			currency=starting, **stats)
		if character is None :
			return Reply(f"Something went wrong while saving {answers['name']}. Please type **submit** again.")
		if answers.get("imported_from") :
			character = CharacterTransactions().update(character.id, imported_from=answers["imported_from"])
		if answers.get("extras") :
			CharacterInfoTransactions().replace_extras(character.id, answers["extras"])
		if starting :
			CurrencyTransactions().log(character.id, draft.guild_id, starting, START, None)
		labels = {str(sheet_field.id) : sheet_field.label for sheet_field in Sheet.questions(draft.guild_id)}
		for field_id, value in answers["fields"].items() :
			if field_id in labels and value :
				CharacterInfoTransactions().set_answer(character.id, int(field_id), labels[field_id], value)
		not_bought += Interview._buy_starting_gear(character, basket, access, draft.uid)
		# Buying changed the currency, so the review card needs the character as it is now.
		character = CharacterTransactions().get_by_id(character.id) or character
		DraftTransactions().delete(draft.uid)
		text = (f"**{character.name}** was sent to the staff of {answers.get('guild_name', 'the server')} for review. "
		        f"I'll message you when they have looked at it.")
		if not_bought :
			text += "\n\nNot all of your starting gear could be bought: " + " ".join(not_bought)
		return Reply(text, finished=True, outcome=CREATED, character=character)

	# ============================================================
	@staticmethod
	def _check_basket(draft: Drafts, access: Access) -> tuple[list[GearItems], list[str]] :
		"""Takes items out of the bag that left the catalog or became locked since they were picked.

		@return: the items still in the bag, and a sentence for each item taken out.
		"""
		picked = draft.answers.get("gear") or []
		basket = Interview._basket(draft)
		dropped = []
		if len(basket) < len(picked) :
			gone = len(picked) - len(basket)
			dropped.append(f"{gone} item{'s' if gone > 1 else ''} in your bag {'are' if gone > 1 else 'is'} no "
			               f"longer sold.")
		kept = []
		for item in basket :
			locked = Gear.lock_reason(item, access)
			if locked :
				dropped.append(f"{item.name} {locked}.")
			else :
				kept.append(item)
		if len(kept) != len(picked) :
			draft.answers["gear"] = [item.id for item in kept]
			DraftTransactions().save(draft)
		return kept, dropped

	# ============================================================
	@staticmethod
	def _buy_starting_gear(character: Characters, basket: list[GearItems], access: Access, uid: int) -> list[str] :
		"""Buys the bag for a new character and has it wear the most expensive armor bought.

		@return: why items could not be bought, one sentence each.
		"""
		problems, armor = [], []
		for item in basket :
			entry, problem = Gear.buy(character, item, access, uid, source=CREATION)
			if entry is None :
				problems.append(problem)
			elif item.kind == ARMOR :
				armor.append((item.price, entry))
		if armor :
			# The catalog price decides, so free mode picks the same armor as economy mode would.
			Gear.equip(max(armor, key=lambda pair : pair[0])[1])
		return problems
